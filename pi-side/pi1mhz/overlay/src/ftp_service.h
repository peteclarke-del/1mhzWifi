#ifndef PI1MHZ_FTP_SERVICE_H
#define PI1MHZ_FTP_SERVICE_H

#include <stdint.h>

/* High-level interactive FTP service on the shared Pi1MHz mailbox. */
#define FTP_CMD_FIRST   128u
#define FTP_CMD_OPEN    128u
#define FTP_CMD_EXEC    129u
#define FTP_CMD_READ    130u
#define FTP_CMD_WRITE   131u
#define FTP_CMD_CLOSE   132u
#define FTP_CMD_CANCEL  133u
#define FTP_CMD_LAST    FTP_CMD_CANCEL

#define FTP_RESULT_OK       0x00u
#define FTP_RESULT_PENDING  0x80u
#define FTP_RESULT_EOF      0x20u
#define FTP_RESULT_PARAM    0x23u
#define FTP_RESULT_DNS      0x24u
#define FTP_RESULT_CONNECT  0x25u
#define FTP_RESULT_TIMEOUT  0x2Bu
#define FTP_RESULT_ABORT    0x2Du

#define FTP_TRANSFER_NONE   0u
#define FTP_TRANSFER_READ   1u
#define FTP_TRANSFER_WRITE  2u
#define FTP_TRANSFER_LIST   3u

void ftp_service_init(void);
void ftp_service_command(uint32_t command_pointer, uint32_t address,
                         uint8_t data);

#endif
