#ifndef NETTOOLS_SECURE_SERVICE_CORE_H
#define NETTOOLS_SECURE_SERVICE_CORE_H

#include <stddef.h>
#include <stdint.h>

enum {
    NTS_SEC_CAPS = 94,
    NTS_SEC_RANDOM = 95,
    NTS_SEC_SSH_OPEN = 96,
    NTS_SEC_SSH_READ = 97,
    NTS_SEC_SSH_WRITE = 98,
    NTS_SEC_SSH_CLOSE = 99,
    NTS_SEC_SSH_PASSWORD = 100,
    NTS_OK = 0,
    NTS_PENDING = 1,
    NTS_EOF = 0x20,
    NTS_ERR_PARAM = 0x23,
    NTS_ERR_UNSUPPORTED = 0x27,
    NTS_HOSTKEY_UNKNOWN = 0x2C,
    NTS_AUTH_FAILED = 0x2D
};

typedef struct nts_secure_port {
    int (*random)(void *opaque, uint8_t *out, size_t length);
    uint8_t (*ssh_open)(void *opaque, const char *url, const char *username,
                        int trust_unknown, char fingerprint[96]);
    int (*ssh_read)(void *opaque, uint8_t *out, size_t maximum);
    int (*ssh_write)(void *opaque, const uint8_t *data, size_t length);
    int (*ssh_password)(void *opaque, const uint8_t *password, size_t length);
    void (*ssh_close)(void *opaque);
} nts_secure_port;

typedef struct nts_secure_service {
    const nts_secure_port *port;
    void *opaque;
    int managed_ssh;
} nts_secure_service;

uint8_t nts_secure_dispatch(nts_secure_service *service, uint8_t *command,
                            uint8_t *jim, size_t jim_size);

#endif
