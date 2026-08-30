/* Interactive FTP client for the Pi1MHz services mailbox.
 *
 * FTP control and passive data sockets live entirely on the Pi. The host ROM
 * sees bounded high-level operations and moves file bytes through the fixed
 * service scratch page. No host or Tube address is ever passed to lwIP.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

#include "Pi1MHz.h"
#include "ftp_service.h"
#include "ram_emulator.h"
#include "services.h"
#include "rpi/asm-helpers.h"
#include "rpi/systimer.h"
#include "wifi/wifi_lwip.h"
#include "lwip/altcp.h"
#include "lwip/dns.h"
#include "lwip/err.h"
#include "lwip/ip_addr.h"
#include "lwip/pbuf.h"

#define FTP_TEXT_MAX 237u
#define FTP_CONTROL_CAPACITY 768u
#define FTP_DATA_CAPACITY 8192u
#define FTP_SCRATCH_OFFSET 0xfff100u
#define FTP_TIMEOUT_MS 30000u

typedef enum {
   FTP_STATE_CLOSED = 0,
   FTP_STATE_DNS,
   FTP_STATE_CONNECTING,
   FTP_STATE_GREETING,
   FTP_STATE_READY,
   FTP_STATE_ERROR
} ftp_state_t;

typedef enum {
   FTP_OP_NONE = 0,
   FTP_OP_OPEN,
   FTP_OP_SIMPLE_SEND,
   FTP_OP_SIMPLE_REPLY,
   FTP_OP_EPSV_SEND,
   FTP_OP_EPSV_REPLY,
   FTP_OP_PASV_SEND,
   FTP_OP_PASV_REPLY,
   FTP_OP_DATA_CONNECT,
   FTP_OP_TRANSFER_SEND,
   FTP_OP_TRANSFER_REPLY,
   FTP_OP_READ,
   FTP_OP_WRITE,
   FTP_OP_WRITE_FINISH,
   FTP_OP_CLOSE
} ftp_operation_t;

static struct {
   ftp_state_t state;
   ftp_operation_t operation;
   struct altcp_pcb *control;
   struct altcp_pcb *data;
   ip_addr_t address;
   bool dns_done;
   bool dns_ok;
   bool control_connected;
   bool control_eof;
   bool data_connected;
   bool data_eof;
   bool data_error;
   uint16_t data_port;
   uint8_t transfer;
   char host[192];
   char request[FTP_TEXT_MAX + 1u];
   char transfer_command[FTP_TEXT_MAX + 8u];
   char control_text[FTP_CONTROL_CAPACITY];
   uint16_t control_length;
   char last_reply[FTP_TEXT_MAX + 1u];
   uint8_t data_buffer[FTP_DATA_CAPACITY];
   uint16_t data_head;
   uint16_t data_tail;
   uint16_t data_count;
   uint32_t deadline_ms;
} ftp;

static volatile bool request_pending;
static volatile bool request_cancel;
static volatile uint32_t request_pointer;
static volatile uint32_t request_status_address;
static bool request_started;
static uint8_t request_command;

static uint32_t ftp_now_ms(void)
{
   return (uint32_t)(RPI_GetSystemTime64() / 1000u);
}

static bool ftp_expired(void)
{
   return (int32_t)(ftp_now_ms() - ftp.deadline_ms) >= 0;
}

static void ftp_set_deadline(void)
{
   ftp.deadline_ms = ftp_now_ms() + FTP_TIMEOUT_MS;
}

static void ftp_detach(struct altcp_pcb **slot, bool abort_connection)
{
   struct altcp_pcb *pcb = *slot;
   if (pcb == NULL)
      return;
   *slot = NULL;
   altcp_arg(pcb, NULL);
   altcp_recv(pcb, NULL);
   altcp_sent(pcb, NULL);
   altcp_poll(pcb, NULL, 0u);
   altcp_err(pcb, NULL);
   if (abort_connection)
      altcp_abort(pcb);
   else if (altcp_close(pcb) != ERR_OK)
      altcp_abort(pcb);
}

static void ftp_reset(bool abort_connections)
{
   ftp_detach(&ftp.data, abort_connections);
   ftp_detach(&ftp.control, abort_connections);
   memset(&ftp, 0, sizeof ftp);
}

static uint8_t ftp_error(uint8_t result)
{
   ftp.state = FTP_STATE_ERROR;
   ftp.operation = FTP_OP_NONE;
   return result;
}

static err_t ftp_sent(void *arg, struct altcp_pcb *pcb, u16_t length)
{
   (void)arg;
   (void)pcb;
   (void)length;
   return ERR_OK;
}

static err_t ftp_poll_callback(void *arg, struct altcp_pcb *pcb)
{
   (void)arg;
   (void)pcb;
   return ERR_OK;
}

static void ftp_control_error(void *arg, err_t error)
{
   (void)arg;
   (void)error;
   ftp.control = NULL;
   ftp.state = FTP_STATE_ERROR;
}

static void ftp_data_error(void *arg, err_t error)
{
   (void)arg;
   (void)error;
   ftp.data = NULL;
   ftp.data_error = true;
}

static err_t ftp_control_receive(void *arg, struct altcp_pcb *pcb,
                                 struct pbuf *p, err_t error)
{
   uint16_t offset = 0u;
   (void)arg;
   if (error != ERR_OK) {
      if (p != NULL)
         pbuf_free(p);
      ftp.state = FTP_STATE_ERROR;
      return ERR_OK;
   }
   if (p == NULL) {
      ftp.control_eof = true;
      return ERR_OK;
   }
   if ((uint32_t)ftp.control_length + p->tot_len >= FTP_CONTROL_CAPACITY) {
      pbuf_free(p);
      ftp.state = FTP_STATE_ERROR;
      return ERR_OK;
   }
   while (offset < p->tot_len) {
      uint16_t available = (uint16_t)(p->tot_len - offset);
      uint16_t copied = pbuf_copy_partial(
         p, ftp.control_text + ftp.control_length, available, offset);
      if (copied == 0u)
         break;
      ftp.control_length = (uint16_t)(ftp.control_length + copied);
      offset = (uint16_t)(offset + copied);
   }
   ftp.control_text[ftp.control_length] = '\0';
   altcp_recved(pcb, p->tot_len);
   pbuf_free(p);
   wifi_lwip_rx_kick();
   return ERR_OK;
}

static err_t ftp_data_receive(void *arg, struct altcp_pcb *pcb,
                              struct pbuf *p, err_t error)
{
   uint16_t offset = 0u;
   (void)arg;
   if (error != ERR_OK) {
      if (p != NULL)
         pbuf_free(p);
      ftp.data_error = true;
      return ERR_OK;
   }
   if (p == NULL) {
      ftp.data_eof = true;
      return ERR_OK;
   }
   if (p->tot_len > (uint16_t)(FTP_DATA_CAPACITY - ftp.data_count))
      return ERR_MEM;
   while (offset < p->tot_len) {
      uint8_t block[128];
      uint16_t wanted = (uint16_t)(p->tot_len - offset);
      uint16_t copied;
      if (wanted > sizeof block)
         wanted = (uint16_t)sizeof block;
      copied = pbuf_copy_partial(p, block, wanted, offset);
      if (copied == 0u)
         break;
      for (uint16_t i = 0u; i < copied; i++) {
         ftp.data_buffer[ftp.data_head] = block[i];
         ftp.data_head = (uint16_t)((ftp.data_head + 1u)
                                   & (FTP_DATA_CAPACITY - 1u));
      }
      ftp.data_count = (uint16_t)(ftp.data_count + copied);
      offset = (uint16_t)(offset + copied);
   }
   altcp_recved(pcb, p->tot_len);
   pbuf_free(p);
   wifi_lwip_rx_kick();
   return ERR_OK;
}

static err_t ftp_control_connected(void *arg, struct altcp_pcb *pcb,
                                   err_t error)
{
   (void)arg;
   (void)pcb;
   if (error == ERR_OK) {
      ftp.control_connected = true;
      ftp.state = FTP_STATE_GREETING;
   } else {
      ftp.control = NULL;
      ftp.state = FTP_STATE_ERROR;
   }
   return ERR_OK;
}

static err_t ftp_data_connected(void *arg, struct altcp_pcb *pcb, err_t error)
{
   (void)arg;
   (void)pcb;
   if (error == ERR_OK)
      ftp.data_connected = true;
   else {
      ftp.data = NULL;
      ftp.data_error = true;
   }
   return ERR_OK;
}

static void ftp_bind_control(struct altcp_pcb *pcb)
{
   altcp_arg(pcb, &ftp);
   altcp_recv(pcb, ftp_control_receive);
   altcp_sent(pcb, ftp_sent);
   altcp_poll(pcb, ftp_poll_callback, 4u);
   altcp_err(pcb, ftp_control_error);
}

static void ftp_bind_data(struct altcp_pcb *pcb)
{
   altcp_arg(pcb, &ftp);
   altcp_recv(pcb, ftp_data_receive);
   altcp_sent(pcb, ftp_sent);
   altcp_poll(pcb, ftp_poll_callback, 4u);
   altcp_err(pcb, ftp_data_error);
}

/* Return a complete final reply line. Multiline opening lines use "ddd-";
 * only a matching conventional "ddd " line completes the reply. */
static bool ftp_reply(unsigned int *code)
{
   uint16_t line_start = 0u;
   uint16_t i;
   unsigned int multiline = 0u;
   for (i = 0u; i + 1u < ftp.control_length; i++) {
      if (ftp.control_text[i] != '\r' || ftp.control_text[i + 1u] != '\n')
         continue;
      if (i >= line_start + 4u
          && ftp.control_text[line_start] >= '1'
          && ftp.control_text[line_start] <= '5'
          && ftp.control_text[line_start + 1u] >= '0'
          && ftp.control_text[line_start + 1u] <= '9'
          && ftp.control_text[line_start + 2u] >= '0'
          && ftp.control_text[line_start + 2u] <= '9') {
         unsigned int line_code =
              (unsigned int)(ftp.control_text[line_start] - '0') * 100u
            + (unsigned int)(ftp.control_text[line_start + 1u] - '0') * 10u
            + (unsigned int)(ftp.control_text[line_start + 2u] - '0');
         if (line_start == 0u && ftp.control_text[line_start + 3u] == '-')
            multiline = line_code;
         if (ftp.control_text[line_start + 3u] != ' '
             || (multiline != 0u && line_code != multiline))
            goto next_line;
         size_t reply_length = (size_t)(i + 2u);
         size_t copy = reply_length < FTP_TEXT_MAX ? reply_length : FTP_TEXT_MAX;
         memcpy(ftp.last_reply, ftp.control_text, copy);
         ftp.last_reply[copy] = '\0';
         *code = line_code;
         memmove(ftp.control_text, ftp.control_text + reply_length,
                 ftp.control_length - reply_length);
         ftp.control_length = (uint16_t)(ftp.control_length - reply_length);
         ftp.control_text[ftp.control_length] = '\0';
         return true;
      }
next_line:
      line_start = (uint16_t)(i + 2u);
      i++;
   }
   return false;
}

static bool ftp_send(const char *command)
{
   size_t length = strlen(command);
   if (ftp.control == NULL || length > 0xffffu
       || altcp_sndbuf(ftp.control) < length)
      return false;
   if (altcp_write(ftp.control, command, (u16_t)length,
                   TCP_WRITE_FLAG_COPY) != ERR_OK)
      return false;
   altcp_output(ftp.control);
   wifi_lwip_rx_kick();
   ftp_set_deadline();
   return true;
}

static bool ftp_parse_url(const char *url, char *host, size_t host_size,
                          uint16_t *port)
{
   const char *start = url;
   const char *end;
   const char *colon = NULL;
   size_t length;
   if (!strncasecmp(start, "ftp://", 6u))
      start += 6;
   end = start;
   while (*end != '\0' && *end != '/') {
      if (*end == ':')
         colon = end;
      if ((unsigned char)*end < 0x21u || *end == '@')
         return false;
      end++;
   }
   if (colon != NULL) {
      uint32_t value = 0u;
      const char *p = colon + 1;
      if (p == end)
         return false;
      while (p != end) {
         if (*p < '0' || *p > '9')
            return false;
         value = value * 10u + (uint32_t)(*p++ - '0');
         if (value > 65535u)
            return false;
      }
      *port = (uint16_t)value;
      end = colon;
   } else {
      *port = 21u;
   }
   length = (size_t)(end - start);
   if (length == 0u || length >= host_size)
      return false;
   memcpy(host, start, length);
   host[length] = '\0';
   return true;
}

static void ftp_dns_found(const char *name, const ip_addr_t *address,
                          void *argument)
{
   (void)name;
   (void)argument;
   ftp.dns_done = true;
   if (address != NULL) {
      ftp.address = *address;
      ftp.dns_ok = true;
   }
   wifi_lwip_rx_kick();
}

static uint8_t ftp_start_control(uint16_t port)
{
   err_t error;
   ftp.control = altcp_new_ip_type(NULL, IPADDR_TYPE_V4);
   if (ftp.control == NULL)
      return ftp_error(FTP_RESULT_CONNECT);
   ftp_bind_control(ftp.control);
   error = altcp_connect(ftp.control, &ftp.address, port,
                         ftp_control_connected);
   if (error != ERR_OK) {
      ftp_detach(&ftp.control, true);
      return ftp_error(FTP_RESULT_CONNECT);
   }
   ftp.state = FTP_STATE_CONNECTING;
   ftp_set_deadline();
   return FTP_RESULT_PENDING;
}

static uint8_t ftp_open_poll(void)
{
   static uint16_t control_port;
   unsigned int code;
   if (ftp.state == FTP_STATE_ERROR)
      return FTP_RESULT_CONNECT;
   if (ftp.state == FTP_STATE_CLOSED) {
      err_t result;
      if (!ftp_parse_url(ftp.request, ftp.host, sizeof ftp.host,
                         &control_port))
         return FTP_RESULT_PARAM;
      if (!wifi_lwip_get_context()->address_ready)
         return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
      ftp.state = FTP_STATE_DNS;
      result = dns_gethostbyname(ftp.host, &ftp.address, ftp_dns_found, NULL);
      if (result == ERR_OK) {
         ftp.dns_done = true;
         ftp.dns_ok = true;
      } else if (result != ERR_INPROGRESS) {
         return ftp_error(FTP_RESULT_DNS);
      }
      ftp_set_deadline();
   }
   if (ftp.state == FTP_STATE_DNS) {
      if (!ftp.dns_done)
         return ftp_expired() ? ftp_error(FTP_RESULT_TIMEOUT)
                              : FTP_RESULT_PENDING;
      if (!ftp.dns_ok)
         return ftp_error(FTP_RESULT_DNS);
      return ftp_start_control(control_port);
   }
   if (ftp.state == FTP_STATE_CONNECTING)
      return ftp_expired() ? ftp_error(FTP_RESULT_TIMEOUT)
                           : FTP_RESULT_PENDING;
   if (ftp.state == FTP_STATE_GREETING) {
      if (!ftp_reply(&code))
         return ftp_expired() ? ftp_error(FTP_RESULT_TIMEOUT)
                              : FTP_RESULT_PENDING;
      if (code != 220u)
         return ftp_error(FTP_RESULT_CONNECT);
      ftp.state = FTP_STATE_READY;
      ftp.operation = FTP_OP_NONE;
      return FTP_RESULT_OK;
   }
   return ftp.state == FTP_STATE_READY ? FTP_RESULT_OK : FTP_RESULT_CONNECT;
}

static void ftp_upper_word(char *text)
{
   while (*text != '\0' && *text != ' ') {
      if (*text >= 'a' && *text <= 'z')
         *text = (char)(*text - 32);
      text++;
   }
}

static bool ftp_is_transfer(const char *command, uint8_t *transfer,
                            const char **verb)
{
   if (!strncmp(command, "GET ", 4u)) {
      *transfer = FTP_TRANSFER_READ;
      *verb = "RETR";
      return true;
   }
   if (!strncmp(command, "PUT ", 4u)) {
      *transfer = FTP_TRANSFER_WRITE;
      *verb = "STOR";
      return true;
   }
   if (!strcmp(command, "DIR") || !strncmp(command, "DIR ", 4u)) {
      *transfer = FTP_TRANSFER_LIST;
      *verb = "LIST";
      return true;
   }
   if (!strcmp(command, "LS") || !strncmp(command, "LS ", 3u)) {
      *transfer = FTP_TRANSFER_LIST;
      *verb = "NLST";
      return true;
   }
   return false;
}

static bool ftp_make_command(char *output, size_t output_size,
                             const char *input)
{
   const char *argument = strchr(input, ' ');
   const char *verb = input;
   size_t word = argument != NULL ? (size_t)(argument - input) : strlen(input);
   if (word == 2u && !strncmp(input, "CD", 2u))
      verb = "CWD";
   else if (word == 6u && !strncmp(input, "DELETE", 6u))
      verb = "DELE";
   else if (word == 5u && !strncmp(input, "MKDIR", 5u))
      verb = "MKD";
   else if (word == 5u && !strncmp(input, "RMDIR", 5u))
      verb = "RMD";
   else if (word == 6u && !strncmp(input, "BINARY", 6u)) {
      verb = "TYPE";
      argument = " I";
   } else if (word == 5u && !strncmp(input, "ASCII", 5u)) {
      verb = "TYPE";
      argument = " A";
   }
   if (verb == input) {
      if (snprintf(output, output_size, "%s\r\n", input) >= (int)output_size)
         return false;
   } else {
      if (snprintf(output, output_size, "%s%s\r\n", verb,
                   argument != NULL ? argument : "") >= (int)output_size)
         return false;
   }
   return true;
}

static bool ftp_parse_epsv(const char *reply, uint16_t *port)
{
   const char *open = strchr(reply, '(');
   const char *close = open != NULL ? strchr(open, ')') : NULL;
   const char *p;
   char delimiter;
   uint32_t value = 0u;
   if (open == NULL || close == NULL || close - open < 6)
      return false;
   delimiter = open[1];
   if (open[2] != delimiter || open[3] != delimiter)
      return false;
   p = open + 4;
   if (p == close || *p < '0' || *p > '9')
      return false;
   while (p < close && *p >= '0' && *p <= '9') {
      value = value * 10u + (uint32_t)(*p++ - '0');
      if (value > 65535u)
         return false;
   }
   if (p >= close || *p != delimiter || value == 0u)
      return false;
   *port = (uint16_t)value;
   return true;
}

static bool ftp_parse_pasv(const char *reply, uint16_t *port)
{
   const char *p = strchr(reply, '(');
   unsigned int values[6];
   if (p == NULL)
      return false;
   p++;
   for (unsigned int i = 0u; i < 6u; i++) {
      unsigned int value = 0u;
      if (*p < '0' || *p > '9')
         return false;
      while (*p >= '0' && *p <= '9') {
         value = value * 10u + (unsigned int)(*p++ - '0');
         if (value > 255u)
            return false;
      }
      values[i] = value;
      if (i != 5u) {
         if (*p++ != ',')
            return false;
      }
   }
   *port = (uint16_t)(values[4] * 256u + values[5]);
   return *port != 0u;
}

static uint8_t ftp_start_data(void)
{
   err_t error;
   ftp_detach(&ftp.data, true);
   ftp.data_connected = false;
   ftp.data_eof = false;
   ftp.data_error = false;
   ftp.data_head = 0u;
   ftp.data_tail = 0u;
   ftp.data_count = 0u;
   ftp.data = altcp_new_ip_type(NULL, IPADDR_TYPE_V4);
   if (ftp.data == NULL)
      return FTP_RESULT_CONNECT;
   ftp_bind_data(ftp.data);
   error = altcp_connect(ftp.data, &ftp.address, ftp.data_port,
                         ftp_data_connected);
   if (error != ERR_OK) {
      ftp_detach(&ftp.data, true);
      return FTP_RESULT_CONNECT;
   }
   ftp_set_deadline();
   return FTP_RESULT_PENDING;
}

static uint8_t ftp_exec_poll(void)
{
   unsigned int code;
   const char *verb;
   if (ftp.state != FTP_STATE_READY)
      return FTP_RESULT_CONNECT;
   switch (ftp.operation) {
      case FTP_OP_NONE:
         ftp_upper_word(ftp.request);
         if (ftp_is_transfer(ftp.request, &ftp.transfer, &verb)) {
            const char *argument = strchr(ftp.request, ' ');
            if ((ftp.transfer == FTP_TRANSFER_READ
                 || ftp.transfer == FTP_TRANSFER_WRITE)
                && (argument == NULL || argument[1] == '\0'))
               return FTP_RESULT_PARAM;
            if (snprintf(ftp.transfer_command, sizeof ftp.transfer_command,
                         "%s%s\r\n", verb,
                         argument != NULL ? argument : "")
                >= (int)sizeof ftp.transfer_command)
               return FTP_RESULT_PARAM;
            ftp.operation = FTP_OP_EPSV_SEND;
         } else {
            if (!ftp_make_command(ftp.transfer_command,
                                  sizeof ftp.transfer_command, ftp.request))
               return FTP_RESULT_PARAM;
            ftp.transfer = FTP_TRANSFER_NONE;
            ftp.operation = FTP_OP_SIMPLE_SEND;
         }
         /* fall through */
      case FTP_OP_SIMPLE_SEND:
         if (!ftp_send(ftp.transfer_command))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         ftp.operation = FTP_OP_SIMPLE_REPLY;
         return FTP_RESULT_PENDING;
      case FTP_OP_SIMPLE_REPLY:
         if (!ftp_reply(&code))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         ftp.operation = FTP_OP_NONE;
         /* A syntactically valid FTP rejection is a server reply, not a
          * transport failure. Return it to the interactive client verbatim. */
         return FTP_RESULT_OK;
      case FTP_OP_EPSV_SEND:
         if (!ftp_send("EPSV\r\n"))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         ftp.operation = FTP_OP_EPSV_REPLY;
         return FTP_RESULT_PENDING;
      case FTP_OP_EPSV_REPLY:
         if (!ftp_reply(&code))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         if (code == 229u && ftp_parse_epsv(ftp.last_reply, &ftp.data_port)) {
            ftp.operation = FTP_OP_DATA_CONNECT;
            return ftp_start_data();
         }
         if (code >= 400u) {
            ftp.operation = FTP_OP_PASV_SEND;
            return FTP_RESULT_PENDING;
         }
         return FTP_RESULT_CONNECT;
      case FTP_OP_PASV_SEND:
         if (!ftp_send("PASV\r\n"))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         ftp.operation = FTP_OP_PASV_REPLY;
         return FTP_RESULT_PENDING;
      case FTP_OP_PASV_REPLY:
         if (!ftp_reply(&code))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         if (code != 227u || !ftp_parse_pasv(ftp.last_reply, &ftp.data_port))
            return FTP_RESULT_CONNECT;
         ftp.operation = FTP_OP_DATA_CONNECT;
         return ftp_start_data();
      case FTP_OP_DATA_CONNECT:
         if (ftp.data_error)
            return FTP_RESULT_CONNECT;
         if (!ftp.data_connected)
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         ftp.operation = FTP_OP_TRANSFER_SEND;
         /* fall through */
      case FTP_OP_TRANSFER_SEND:
         if (!ftp_send(ftp.transfer_command))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         ftp.operation = FTP_OP_TRANSFER_REPLY;
         return FTP_RESULT_PENDING;
      case FTP_OP_TRANSFER_REPLY:
         if (!ftp_reply(&code))
            return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
         if (code != 125u && code != 150u) {
            ftp_detach(&ftp.data, true);
            ftp.operation = FTP_OP_NONE;
            ftp.transfer = FTP_TRANSFER_NONE;
            return FTP_RESULT_OK;
         }
         ftp.operation = ftp.transfer == FTP_TRANSFER_WRITE
                       ? FTP_OP_WRITE : FTP_OP_READ;
         return FTP_RESULT_OK;
      default:
         return FTP_RESULT_PARAM;
   }
}

static uint8_t ftp_transfer_reply(void)
{
   unsigned int code;
   if (!ftp_reply(&code))
      return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
   ftp.operation = FTP_OP_NONE;
   ftp.transfer = FTP_TRANSFER_NONE;
   return FTP_RESULT_EOF;
}

static uint8_t ftp_read_poll(uint32_t cp)
{
   uint8_t maximum = Pi1MHz->JIM_ram[cp + 1u];
   uint8_t count = maximum < ftp.data_count ? maximum
                                            : (uint8_t)ftp.data_count;
   uint8_t *destination = &Pi1MHz->JIM_ram[DISC_RAM_BASE + FTP_SCRATCH_OFFSET];
   if (ftp.operation != FTP_OP_READ || ftp.transfer == FTP_TRANSFER_WRITE)
      return FTP_RESULT_PARAM;
   for (uint8_t i = 0u; i < count; i++) {
      destination[i] = ftp.data_buffer[ftp.data_tail];
      ftp.data_tail = (uint16_t)((ftp.data_tail + 1u)
                                 & (FTP_DATA_CAPACITY - 1u));
   }
   ftp.data_count = (uint16_t)(ftp.data_count - count);
   Pi1MHz->JIM_ram[cp + 1u] = count;
   if (count != 0u) {
      ftp_set_deadline();
      return FTP_RESULT_OK;
   }
   if (ftp.data_error)
      return FTP_RESULT_CONNECT;
   if (!ftp.data_eof)
      return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
   ftp_detach(&ftp.data, false);
   return ftp_transfer_reply();
}

static uint8_t ftp_write_poll(uint32_t cp)
{
   uint8_t count = Pi1MHz->JIM_ram[cp + 1u];
   const uint8_t *source = &Pi1MHz->JIM_ram[DISC_RAM_BASE + FTP_SCRATCH_OFFSET];
   if (ftp.operation == FTP_OP_WRITE_FINISH)
      return ftp_transfer_reply();
   if (ftp.operation != FTP_OP_WRITE || ftp.transfer != FTP_TRANSFER_WRITE
       || ftp.data == NULL)
      return FTP_RESULT_PARAM;
   if (count == 0u) {
      /* altcp_close can return ERR_MEM while previously queued payload is
       * still being acknowledged. Retry it instead of aborting the socket,
       * otherwise a nominally successful PUT can be truncated. */
      if (altcp_close(ftp.data) != ERR_OK)
         return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
      ftp.data = NULL;
      ftp.operation = FTP_OP_WRITE_FINISH;
      ftp_set_deadline();
      return FTP_RESULT_PENDING;
   }
   if (altcp_sndbuf(ftp.data) < count)
      return ftp_expired() ? FTP_RESULT_TIMEOUT : FTP_RESULT_PENDING;
   if (altcp_write(ftp.data, source, count, TCP_WRITE_FLAG_COPY) != ERR_OK)
      return FTP_RESULT_PENDING;
   altcp_output(ftp.data);
   wifi_lwip_rx_kick();
   Pi1MHz->JIM_ram[cp + 1u] = count;
   ftp_set_deadline();
   return FTP_RESULT_OK;
}

static void ftp_response(uint32_t cp)
{
   size_t length = strnlen(ftp.last_reply, FTP_TEXT_MAX);
   Pi1MHz->JIM_ram[cp + 1u] = ftp.transfer;
   memcpy(&Pi1MHz->JIM_ram[cp + 2u], ftp.last_reply, length);
   Pi1MHz->JIM_ram[cp + 2u + length] = '\0';
}

static bool ftp_copy_request(uint32_t cp)
{
   size_t length = 0u;
   while (length <= FTP_TEXT_MAX
          && Pi1MHz->JIM_ram[cp + 1u + length] != '\0')
      length++;
   if (length > FTP_TEXT_MAX)
      return false;
   memcpy(ftp.request, &Pi1MHz->JIM_ram[cp + 1u], length);
   ftp.request[length] = '\0';
   return length != 0u;
}

static uint8_t ftp_process(uint32_t cp)
{
   uint8_t result;
   if (!request_started) {
      request_started = true;
      if ((request_command == FTP_CMD_OPEN || request_command == FTP_CMD_EXEC)
          && !ftp_copy_request(cp))
         return FTP_RESULT_PARAM;
      if (request_command == FTP_CMD_OPEN) {
         /* OPEN always starts a new session so a failed connection can be
          * retried without rebooting the Pi. Preserve the copied target
          * across the connection teardown. */
         char target[sizeof ftp.request];
         memcpy(target, ftp.request, sizeof target);
         ftp_reset(true);
         memcpy(ftp.request, target, sizeof ftp.request);
      }
      if (request_command == FTP_CMD_EXEC)
         ftp.operation = FTP_OP_NONE;
      ftp_set_deadline();
   }
   switch (request_command) {
      case FTP_CMD_OPEN:
         result = ftp_open_poll();
         break;
      case FTP_CMD_EXEC:
         result = ftp_exec_poll();
         break;
      case FTP_CMD_READ:
         result = ftp_read_poll(cp);
         break;
      case FTP_CMD_WRITE:
         result = ftp_write_poll(cp);
         break;
      case FTP_CMD_CLOSE:
         if (ftp.control != NULL && ftp.state == FTP_STATE_READY)
            (void)ftp_send("QUIT\r\n");
         ftp_reset(false);
         strcpy(ftp.last_reply, "221 Closed\r\n");
         result = FTP_RESULT_OK;
         break;
      default:
         result = FTP_RESULT_PARAM;
         break;
   }
   if (result != FTP_RESULT_PENDING
       && ((request_command != FTP_CMD_READ && request_command != FTP_CMD_WRITE)
           || result == FTP_RESULT_EOF))
      ftp_response(cp);
   return result;
}

static void ftp_service_poll(void)
{
   uint32_t cp;
   uint32_t address;
   uint8_t result;
   if (request_cancel) {
      ftp_reset(true);
      request_pending = false;
      request_cancel = false;
      request_started = false;
      Pi1MHz_MemoryWrite(request_status_address, FTP_RESULT_ABORT);
      return;
   }
   if (!request_pending)
      return;
   cp = request_pointer;
   address = request_status_address;
   result = ftp_process(cp);
   if (result == FTP_RESULT_PENDING)
      return;
   request_pending = false;
   request_started = false;
   Pi1MHz_MemoryWrite(address, result);
}

void ftp_service_command(uint32_t command_pointer, uint32_t address,
                         uint8_t data)
{
   uint32_t cp = command_pointer - 0xff0000u + DISC_RAM_BASE;
   uint8_t command = Pi1MHz->JIM_ram[cp];
   (void)data;
   if (command == FTP_CMD_CANCEL) {
      if (!request_pending) {
         ftp_reset(true);
         Pi1MHz_MemoryWrite(address, FTP_RESULT_ABORT);
         return;
      }
      request_cancel = true;
      Pi1MHz_MemoryWrite(address, FTP_RESULT_PENDING);
      return;
   }
   if (request_pending) {
      Pi1MHz_MemoryWrite(address, FTP_RESULT_PENDING);
      return;
   }
   request_pointer = cp;
   request_status_address = address;
   request_command = command;
   request_started = false;
   request_pending = true;
   Pi1MHz_MemoryWrite(address, FTP_RESULT_PENDING);
}

void ftp_service_init(void)
{
   static bool initialised;
   if (!initialised) {
      memset(&ftp, 0, sizeof ftp);
      initialised = true;
   }
   (void)services_register(FTP_CMD_FIRST, FTP_CMD_LAST, ftp_service_command);
   request_pending = false;
   request_cancel = false;
   request_started = false;
   Pi1MHz_Register_Poll(ftp_service_poll, "ftp");
}
