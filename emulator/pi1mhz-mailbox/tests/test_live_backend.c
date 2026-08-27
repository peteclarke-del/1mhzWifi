#include "pi1mhz_mailbox.h"
#include "pi1mhz_net_backend.h"

#include <arpa/inet.h>
#include <assert.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define COMMAND 0xFFF000u

static const uint8_t raw_uef[] = "UEF File!\0\0\nfixture";
static const uint8_t gzip_uef[] = {
    0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x03,
    0x0b, 0x75, 0x75, 0x53, 0x70, 0xcb, 0xcc, 0x49, 0x55, 0x64,
    0x60, 0xe0, 0x4a, 0xcb, 0xac, 0x28, 0x29, 0x2d, 0x4a, 0x05,
    0x00, 0xe5, 0x5f, 0x9b, 0xa9, 0x13, 0x00, 0x00, 0x00
};
static const uint8_t zip_uef[] = {
    0x50,0x4b,0x03,0x04,0x14,0x00,0x00,0x00,0x08,0x00,0x00,0x00,0x21,0x00,
    0xe5,0x5f,0x9b,0xa9,0x15,0x00,0x00,0x00,0x13,0x00,0x00,0x00,0x08,0x00,
    0x00,0x00,0x74,0x65,0x73,0x74,0x2e,0x75,0x65,0x66,0x0b,0x75,0x75,0x53,
    0x70,0xcb,0xcc,0x49,0x55,0x64,0x60,0xe0,0x4a,0xcb,0xac,0x28,0x29,0x2d,
    0x4a,0x05,0x00,0x50,0x4b,0x01,0x02,0x14,0x03,0x14,0x00,0x00,0x00,0x08,
    0x00,0x00,0x00,0x21,0x00,0xe5,0x5f,0x9b,0xa9,0x15,0x00,0x00,0x00,0x13,
    0x00,0x00,0x00,0x08,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x80,0x01,0x00,0x00,0x00,0x00,0x74,0x65,0x73,0x74,0x2e,0x75,0x65,
    0x66,0x50,0x4b,0x05,0x06,0x00,0x00,0x00,0x00,0x01,0x00,0x01,0x00,0x36,
    0x00,0x00,0x00,0x3b,0x00,0x00,0x00,0x00,0x00
};

static void set_uef_input(pi1mhz_mailbox *mailbox, const uint8_t *input,
                          size_t length)
{
    uint8_t *window = mailbox->jim;
    memcpy(window, input, length);
    window[0xfffeu] = (uint8_t)length;
    window[0xffffu] = (uint8_t)(length >> 8);
}

static void wr24(uint8_t *p, uint32_t value)
{
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
}

static void wr32(uint8_t *p, uint32_t value)
{
    wr24(p, value);
    p[3] = (uint8_t)(value >> 24);
}

static uint8_t issue(pi1mhz_mailbox *mailbox)
{
    pi1mhz_mailbox_write(mailbox, PI1MHZ_REG_COMMAND, 0xF0);
    assert(pi1mhz_mailbox_read(mailbox, PI1MHZ_REG_COMMAND) ==
           PI1MHZ_NET_BUSY);
    return pi1mhz_mailbox_read(mailbox, PI1MHZ_REG_COMMAND);
}

static uint8_t issue_control(pi1mhz_mailbox *mailbox)
{
    pi1mhz_mailbox_write(mailbox, PI1MHZ_REG_COMMAND, 0xFF);
    assert(pi1mhz_mailbox_read(mailbox, PI1MHZ_REG_COMMAND) ==
           PI1MHZ_NET_BUSY);
    return pi1mhz_mailbox_read(mailbox, PI1MHZ_REG_COMMAND);
}

static void short_wait(void)
{
    const struct timespec delay = { 0, 1000000 };
    nanosleep(&delay, NULL);
}

static void test_wifi_lifecycle(void)
{
    char profile_path[] = "/tmp/pi1mhz-wifi-test-XXXXXX";
    char persisted[128];
    int profile_fd = mkstemp(profile_path);
    pi1mhz_net_backend *backend;
    pi1mhz_mailbox mailbox;
    uint8_t *command;
    ssize_t length;

    assert(profile_fd >= 0);
    assert(!close(profile_fd));
    assert(!unlink(profile_path));
    assert(!setenv("PI1MHZ_WIFI_PROFILE", profile_path, 1));
    assert(!setenv("PI1MHZ_WIFI_ASSOCIATE_MS", "1000", 1));
    assert(!setenv("PI1MHZ_WIFI_DHCP_MS", "1000", 1));

    backend = pi1mhz_net_backend_create("fixture", NULL, 0);
    assert(backend);
    assert(!pi1mhz_mailbox_init(&mailbox, pi1mhz_net_backend_dispatch, backend));
    command = mailbox.jim + mailbox.services_base + 0xFFFF00u;
    command[0] = 91;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1, "OK\r\n"));

    command[0] = 83;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(strstr((const char *)command + 1, "+CIFSR:STAIP,\"0.0.0.0\""));

    memset(command, 0, 224u);
    command[0] = 82;
    command[1] = 1;
    strcpy((char *)command + 2, "Lifecycle-AP");
    strcpy((char *)command + 2 + strlen("Lifecycle-AP") + 1u,
           "WPA2:eightchars");
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1,
                   "WIFI CONNECTING WPA2\r\n\r\nOK\r\n"));

    command[0] = 82;
    command[1] = 0;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1,
                   "WIFI CONNECTING\r\n\r\nOK\r\n"));
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);

    profile_fd = open(profile_path, O_RDONLY);
    assert(profile_fd >= 0);
    length = read(profile_fd, persisted, sizeof(persisted) - 1u);
    assert(length > 0);
    persisted[length] = 0;
    assert(!close(profile_fd));
    assert(!strcmp(persisted,
                   "ELKWIFI1\nWPA2\nLifecycle-AP\neightchars\n"));

    /* A new Pi process reloads the persisted profile, associates, then gets
       its DHCP address. Zero delays make both transitions deterministic. */
    assert(!setenv("PI1MHZ_WIFI_ASSOCIATE_MS", "0", 1));
    assert(!setenv("PI1MHZ_WIFI_DHCP_MS", "0", 1));
    backend = pi1mhz_net_backend_create("fixture", NULL, 0);
    assert(backend);
    assert(!pi1mhz_mailbox_init(&mailbox, pi1mhz_net_backend_dispatch, backend));
    command = mailbox.jim + mailbox.services_base + 0xFFFF00u;
    command[0] = 83;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(strstr((const char *)command + 1,
                  "+CIFSR:STAIP,\"192.168.0.2\""));
    command[0] = 92;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1, "ONLINE 192.168.0.2\r\n"));
    command[0] = 82;
    command[1] = 2;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    command[0] = 83;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(strstr((const char *)command + 1, "+CIFSR:STAIP,\"0.0.0.0\""));
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);

    /* A syntactically valid profile with an invalid WPA2 key must not be
       treated as a bootable saved association. */
    profile_fd = open(profile_path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    assert(profile_fd >= 0);
    {
        static const char invalid_profile[] =
            "ELKWIFI1\nWPA2\nLifecycle-AP\nshort\n";
        assert(write(profile_fd, invalid_profile,
                     sizeof(invalid_profile) - 1u) ==
               (ssize_t)(sizeof(invalid_profile) - 1u));
    }
    assert(!close(profile_fd));
    backend = pi1mhz_net_backend_create("fixture", NULL, 0);
    assert(backend);
    assert(!pi1mhz_mailbox_init(&mailbox, pi1mhz_net_backend_dispatch, backend));
    command = mailbox.jim + mailbox.services_base + 0xFFFF00u;
    command[0] = 83;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(strstr((const char *)command + 1,
                  "+CIFSR:STAIP,\"0.0.0.0\""));
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);

    assert(!setenv("PI1MHZ_WIFI_PRESENT", "0", 1));
    backend = pi1mhz_net_backend_create("fixture", NULL, 0);
    assert(backend);
    assert(!pi1mhz_mailbox_init(&mailbox, pi1mhz_net_backend_dispatch, backend));
    command = mailbox.jim + mailbox.services_base + 0xFFFF00u;
    command[0] = 91;
    assert(issue_control(&mailbox) == 0x44u);
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);

    assert(!unsetenv("PI1MHZ_WIFI_PRESENT"));
    assert(!unsetenv("PI1MHZ_WIFI_PROFILE"));
    assert(!unsetenv("PI1MHZ_WIFI_ASSOCIATE_MS"));
    assert(!unsetenv("PI1MHZ_WIFI_DHCP_MS"));
    assert(!unlink(profile_path));
}

static void test_ftp_fixture_roundtrip(void)
{
    pi1mhz_net_backend *backend =
        pi1mhz_net_backend_create("fixture", NULL, 0);
    pi1mhz_mailbox mailbox;
    uint8_t *command;
    uint8_t *scratch;
    assert(backend);
    assert(!pi1mhz_mailbox_init(&mailbox, pi1mhz_net_backend_dispatch, backend));
    command = mailbox.jim + mailbox.services_base + COMMAND;
    scratch = mailbox.jim + mailbox.services_base + 0xFFF100u;

    memset(command, 0, 224u);
    command[0] = 114;
    strcpy((char *)command + 1, "ftp://fixture:21");
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(strstr((char *)command + 2, "220 "));

    memset(command, 0, 224u);
    command[0] = 115;
    strcpy((char *)command + 1, "PUT roundtrip.bin");
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(command[1] == 2u);
    memcpy(scratch, "roundtrip", 9u);
    command[0] = 117;
    command[1] = 9u;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    command[0] = 117;
    command[1] = 0u;
    assert(issue(&mailbox) == 0x20u);
    assert(strstr((char *)command + 2, "226 "));

    memset(command, 0, 224u);
    command[0] = 115;
    strcpy((char *)command + 1, "GET roundtrip.bin");
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    command[0] = 116;
    command[1] = 240u;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(command[1] == 9u);
    assert(!memcmp(scratch, "roundtrip", 9u));
    command[0] = 116;
    command[1] = 240u;
    assert(issue(&mailbox) == 0x20u);
    assert(strstr((char *)command + 2, "226 "));

    command[0] = 118;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);
}

int main(void)
{
    char sd_path[] = "/tmp/pi1mhz-sd-test-XXXXXX";
    test_ftp_fixture_roundtrip();
    uint8_t sector_data[512];
    int sd_fd;
    int listener;
    int udp_listener;
    struct sockaddr_in address;
    socklen_t address_size = sizeof(address);
    pid_t child;
    pi1mhz_net_backend *backend;
    pi1mhz_mailbox mailbox;
    uint8_t *command;
    uint8_t result;
    unsigned attempts;
    char url[96];
    int status;

    for (unsigned i = 0; i < sizeof(sector_data); i++)
        sector_data[i] = (uint8_t)i;
    sd_fd = mkstemp(sd_path);
    assert(sd_fd >= 0);
    assert(write(sd_fd, sector_data, sizeof(sector_data)) ==
           (ssize_t)sizeof(sector_data));
    memset(sector_data, 0xA5, sizeof(sector_data));
    assert(write(sd_fd, sector_data, sizeof(sector_data)) ==
           (ssize_t)sizeof(sector_data));
    assert(!close(sd_fd));
    assert(!setenv("PI1MHZ_SD_IMAGE", sd_path, 1));

    listener = socket(AF_INET, SOCK_STREAM, 0);
    assert(listener >= 0);
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;
    assert(!bind(listener, (struct sockaddr *)&address, sizeof(address)));
    assert(!getsockname(listener, (struct sockaddr *)&address, &address_size));
    assert(!listen(listener, 1));
    udp_listener = socket(AF_INET, SOCK_DGRAM, 0);
    assert(udp_listener >= 0);
    assert(!bind(udp_listener, (struct sockaddr *)&address, sizeof(address)));

    child = fork();
    assert(child >= 0);
    if (!child) {
        for (unsigned connection = 0; connection < 2; connection++) {
            int client = accept(listener, NULL, NULL);
            char received[5];
            if (client < 0 || read(client, received, sizeof(received)) != 5 ||
                memcmp(received, "hello", 5) ||
                write(client, "world", 5) != 5)
                _exit(1);
            close(client);
        }
        {
            char received[5];
            struct sockaddr_in peer;
            socklen_t peer_size = sizeof(peer);
            if (recvfrom(udp_listener, received, sizeof(received), 0,
                         (struct sockaddr *)&peer, &peer_size) != 5 ||
                memcmp(received, "hello", 5) ||
                sendto(udp_listener, "world", 5, 0,
                       (struct sockaddr *)&peer, peer_size) != 5)
                _exit(1);
        }
        close(listener);
        close(udp_listener);
        _exit(0);
    }

    backend = pi1mhz_net_backend_create("live", NULL, 0);
    assert(backend);
    assert(!pi1mhz_mailbox_init(
        &mailbox, pi1mhz_net_backend_dispatch, backend));
    command = mailbox.jim + mailbox.services_base + COMMAND;

    /* Upstream MMFS uses commands 0/1 on this same services mailbox. */
    memset(mailbox.jim + mailbox.services_base + 0x030000u, 0, 512u);
    memset(command, 0, 16u);
    command[0] = 0;
    wr32(command + 4, 0x030000u);
    wr32(command + 8, 1u);
    wr32(command + 12, 1u);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    for (unsigned i = 0; i < 512u; i++)
        assert(mailbox.jim[mailbox.services_base + 0x030000u + i] == 0xA5u);

    memset(mailbox.jim + mailbox.services_base + 0x030000u, 0x3C, 512u);
    command[0] = 1;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);

    /* Exercise the raw socket ABI used by ElkWiFi functions 8, 13 and 14. */
    command[0] = 45;
    command[1] = 0;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    command[0] = 46;
    memcpy(command + 1, "127.0.0.1", 10);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(command[4] == 127 && command[5] == 0 &&
           command[6] == 0 && command[7] == 1);
    command[0] = 47;
    command[1] = 127;
    command[2] = 0;
    command[3] = 0;
    command[4] = 1;
    command[5] = (uint8_t)ntohs(address.sin_port);
    command[6] = (uint8_t)(ntohs(address.sin_port) >> 8);
    for (attempts = 0; attempts < 1000; attempts++) {
        result = issue(&mailbox);
        if (result != PI1MHZ_NET_PENDING)
            break;
        short_wait();
    }
    assert(result == PI1MHZ_NET_OK);
    memcpy(mailbox.jim + mailbox.services_base + 0x020100u, "hello", 5);
    command[0] = 50;
    wr24(command + 1, 5);
    wr32(command + 4, 0x020100u);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    for (attempts = 0; attempts < 1000; attempts++) {
        command[0] = 51;
        wr24(command + 1, 5);
        wr32(command + 4, 0x020000u);
        result = issue(&mailbox);
        if (result == PI1MHZ_NET_OK && command[1] == 5)
            break;
        assert(result == PI1MHZ_NET_OK);
        short_wait();
    }
    assert(attempts < 1000);
    assert(!memcmp(mailbox.jim + mailbox.services_base + 0x020000u, "world", 5));
    command[0] = 53;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);

    /* Pi control services use selector &FF and page &FFFF00, not a socket
       handle. */
    command = mailbox.jim + mailbox.services_base + 0xFFFF00u;
    command[0] = 83;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(strstr((const char *)command + 1, "+CIFSR:STAIP,\"192.168.0.2\""));
    assert(strstr((const char *)command + 1, "+CIFSR:STAMAC,"));

    command[0] = 82;
    command[1] = 0;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1,
                   "+CWJAP:\"Pi1MHz-Fixture\"\r\n\r\nOK\r\n"));

    set_uef_input(&mailbox, gzip_uef, sizeof(gzip_uef));
    command[0] = 93;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1, "GZIP\r\n"));
    assert(!memcmp(mailbox.jim, raw_uef,
                   sizeof(raw_uef) - 1u));

    set_uef_input(&mailbox, zip_uef, sizeof(zip_uef));
    command[0] = 93;
    assert(issue_control(&mailbox) == PI1MHZ_NET_OK);
    assert(!strcmp((const char *)command + 1, "ZIP\r\n"));
    assert(!memcmp(mailbox.jim, raw_uef,
                   sizeof(raw_uef) - 1u));
    command = mailbox.jim + mailbox.services_base + COMMAND;

    snprintf(url, sizeof(url), "TCP://127.0.0.1:%u/",
             (unsigned)ntohs(address.sin_port));
    command[0] = 60;
    command[1] = 0;
    memcpy(command + 2, url, strlen(url) + 1);
    for (attempts = 0; attempts < 1000; attempts++) {
        result = issue(&mailbox);
        if (result != PI1MHZ_NET_PENDING)
            break;
        short_wait();
    }
    assert(result == PI1MHZ_NET_OK);

    memcpy(mailbox.jim + mailbox.services_base + 0x020100u, "hello", 5);
    command[0] = 62;
    wr24(command + 1, 5);
    wr32(command + 4, 0x020100u);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(command[1] == 5 && command[2] == 0 && command[3] == 0);

    for (attempts = 0; attempts < 1000; attempts++) {
        command[0] = 61;
        wr24(command + 1, 5);
        wr32(command + 4, 0x020000u);
        result = issue(&mailbox);
        if (result == PI1MHZ_NET_OK && command[1] == 5)
            break;
        assert(result == PI1MHZ_NET_OK);
        short_wait();
    }
    assert(attempts < 1000);
    assert(!memcmp(mailbox.jim + mailbox.services_base + 0x020000u, "world", 5));

    command[0] = 63;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);

    /* The emulator must model the connected UDP route used by ElkWiFi
       function 8, not accept only the TCP subset. */
    command[0] = 45;
    command[1] = 1;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    command[0] = 46;
    memcpy(command + 1, "127.0.0.1", 10);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    command[0] = 47;
    command[1] = 127;
    command[2] = 0;
    command[3] = 0;
    command[4] = 1;
    command[5] = (uint8_t)ntohs(address.sin_port);
    command[6] = (uint8_t)(ntohs(address.sin_port) >> 8);
    for (attempts = 0; attempts < 1000; attempts++) {
        result = issue(&mailbox);
        if (result != PI1MHZ_NET_PENDING)
            break;
        short_wait();
    }
    assert(result == PI1MHZ_NET_OK);
    memcpy(mailbox.jim + mailbox.services_base + 0x020100u, "hello", 5);
    command[0] = 50;
    wr24(command + 1, 5);
    wr32(command + 4, 0x020100u);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    for (attempts = 0; attempts < 1000; attempts++) {
        command[0] = 51;
        wr24(command + 1, 5);
        wr32(command + 4, 0x020000u);
        result = issue(&mailbox);
        if (result == PI1MHZ_NET_OK && command[1] == 5)
            break;
        assert(result == PI1MHZ_NET_OK);
        short_wait();
    }
    assert(attempts < 1000);
    assert(!memcmp(mailbox.jim + mailbox.services_base + 0x020000u, "world", 5));
    command[0] = 53;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);

    command[0] = 94;
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(command[1] == 1 && command[3] & 1);
    assert(!memcmp(command + 8, "NTS", 3));

    memset(mailbox.jim + mailbox.services_base + 0x020200u, 0, 16);
    command[0] = 95;
    command[1] = 16;
    command[2] = 0;
    command[3] = 0;
    wr32(command + 4, 0x020200u);
    assert(issue(&mailbox) == PI1MHZ_NET_OK);
    assert(memcmp(mailbox.jim + mailbox.services_base + 0x020200u,
                  "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 16));
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);
    assert(!unsetenv("PI1MHZ_SD_IMAGE"));
    sd_fd = open(sd_path, O_RDONLY);
    assert(sd_fd >= 0);
    assert(lseek(sd_fd, 512, SEEK_SET) == 512);
    assert(read(sd_fd, sector_data, sizeof(sector_data)) ==
           (ssize_t)sizeof(sector_data));
    assert(!close(sd_fd));
    for (unsigned i = 0; i < sizeof(sector_data); i++)
        assert(sector_data[i] == 0x3Cu);
    assert(!unlink(sd_path));
    close(listener);
    close(udp_listener);
    assert(waitpid(child, &status, 0) == child);
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    test_wifi_lifecycle();
    puts("Pi1MHz live loopback backend: OK");
    return 0;
}
