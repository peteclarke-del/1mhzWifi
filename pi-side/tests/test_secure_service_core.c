#include "secure_service_core.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct fixture {
    int opened;
    int sftp_opened;
    int transfer;
    char password[128];
    size_t password_length;
} fixture;

static int random_bytes(void *opaque, uint8_t *out, size_t length)
{
    size_t i;
    (void)opaque;
    for (i = 0; i < length; i++) out[i] = (uint8_t)(0xA0u + i);
    return 0;
}

static uint8_t ssh_open(void *opaque, const char *url, const char *username,
                        int trust, char fingerprint[96])
{
    fixture *state = opaque;
    assert(!strcmp(url, "TCP://host:22/"));
    assert(!strcmp(username, "alice"));
    if (!trust) {
        strcpy(fingerprint, "SHA256:test");
        return NTS_HOSTKEY_UNKNOWN;
    }
    state->opened = 1;
    return NTS_OK;
}

static int ssh_read(void *opaque, uint8_t *out, size_t maximum)
{
    fixture *state = opaque;
    assert(state->opened && maximum >= 2);
    memcpy(out, "ok", 2);
    return 2;
}

static int ssh_write(void *opaque, const uint8_t *data, size_t length)
{
    fixture *state = opaque;
    assert(state->opened && length == 1 && data[0] == 'x');
    return 1;
}

static int ssh_password(void *opaque, const uint8_t *password, size_t length)
{
    fixture *state = opaque;
    assert(length == 6 && !memcmp(password, "secret", 6));
    memcpy(state->password, password, length);
    state->password_length = length;
    return 0;
}

static void ssh_close(void *opaque) { ((fixture *)opaque)->opened = 0; }

static uint8_t sftp_open(void *opaque, const char *url, const char *username,
                         int trust, char fingerprint[96])
{
    fixture *state = opaque;
    (void)fingerprint;
    assert(!strcmp(url, "TCP://host:22/") && !strcmp(username, "alice"));
    assert(trust);
    state->sftp_opened = 1;
    return NTS_OK;
}

static int sftp_path(void *opaque, uint8_t operation, const char *path,
                     uint8_t *out, size_t maximum)
{
    fixture *state = opaque;
    assert(state->sftp_opened && maximum >= 4);
    if (operation == NTS_SEC_SFTP_PWD) {
        memcpy(out, "/x\n", 3);
        return 3;
    }
    assert(!strcmp(path, "remote"));
    return 0;
}

static int sftp_get_open(void *opaque, const char *path)
{
    fixture *state = opaque;
    assert(state->sftp_opened && !strcmp(path, "remote"));
    state->transfer = 1;
    return 0;
}

static int sftp_get_read(void *opaque, uint8_t *out, size_t maximum)
{
    fixture *state = opaque;
    assert(state->transfer == 1 && maximum >= 3);
    memcpy(out, "abc", 3);
    return 3;
}

static int sftp_put_open(void *opaque, const char *path)
{
    fixture *state = opaque;
    assert(state->sftp_opened && !strcmp(path, "remote"));
    state->transfer = 2;
    return 0;
}

static int sftp_put_write(void *opaque, const uint8_t *data, size_t length)
{
    fixture *state = opaque;
    assert(state->transfer == 2 && length == 3 && !memcmp(data, "abc", 3));
    return 3;
}

static int sftp_transfer_close(void *opaque)
{
    ((fixture *)opaque)->transfer = 0;
    return 0;
}

static void sftp_close(void *opaque) { ((fixture *)opaque)->sftp_opened = 0; }

static void wr32(uint8_t *p, uint32_t value)
{
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16); p[3] = (uint8_t)(value >> 24);
}

int main(void)
{
    static const nts_secure_port port = {
        random_bytes, ssh_open, ssh_read, ssh_write, ssh_password, ssh_close,
        sftp_open, sftp_path, sftp_get_open, sftp_get_read,
        sftp_put_open, sftp_put_write, sftp_transfer_close, sftp_close
    };
    uint8_t jim[0x20600] = { 0 };
    uint8_t command[32] = { 0 };
    fixture state = { 0 };
    nts_secure_service service = { &port, &state, 1 };

    command[0] = NTS_SEC_CAPS;
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(command[2] == 1 && command[3] == 15 &&
           !memcmp(command + 8, "NTS", 3));

    memset(command, 0, sizeof(command));
    command[0] = NTS_SEC_RANDOM; command[1] = 16;
    wr32(command + 4, 0x20000);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(jim[0x20000] == 0xA0 && jim[0x2000F] == 0xAF);

    strcpy((char *)jim + 0x20300, "TCP://host:22/");
    strcpy((char *)jim + 0x20400, "alice");
    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SSH_OPEN;
    wr32(command + 2, 0x20300); wr32(command + 6, 0x20400);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) ==
           NTS_HOSTKEY_UNKNOWN);
    assert(!strcmp((char *)jim + 0x20500, "SHA256:test"));
    command[1] = 1;
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);

    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SSH_READ;
    command[1] = 8; wr32(command + 4, 0x20000);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(command[1] == 2 && !memcmp(jim + 0x20000, "ok", 2));

    jim[0x20100] = 'x'; memset(command, 0, sizeof(command));
    command[0] = NTS_SEC_SSH_WRITE; command[1] = 1;
    wr32(command + 4, 0x20100);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(command[1] == 1);

    memcpy(jim + 0x20200, "secret", 6);
    memset(command, 0, sizeof(command));
    command[0] = NTS_SEC_SSH_PASSWORD; command[1] = 6;
    wr32(command + 4, 0x20200);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(state.password_length == 6 && !memcmp(state.password, "secret", 6));
    assert(!memcmp(jim + 0x20200, "\0\0\0\0\0\0", 6));

    command[0] = NTS_SEC_SSH_CLOSE;
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(!state.opened);

    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SFTP_OPEN;
    command[1] = 1; wr32(command + 2, 0x20300); wr32(command + 6, 0x20400);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(state.sftp_opened);

    jim[0x20300] = 0;
    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SFTP_PWD;
    command[1] = 8; wr32(command + 4, 0x20300); wr32(command + 8, 0x20000);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(command[1] == 3 && !memcmp(jim + 0x20000, "/x\n", 3));

    strcpy((char *)jim + 0x20300, "remote");
    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SFTP_GET_OPEN;
    wr32(command + 4, 0x20300);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SFTP_GET_READ;
    command[1] = 8; wr32(command + 4, 0x20000);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(command[1] == 3 && !memcmp(jim + 0x20000, "abc", 3));
    command[0] = NTS_SEC_SFTP_TRANSFER_CLOSE;
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);

    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SFTP_PUT_OPEN;
    wr32(command + 4, 0x20300);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    memcpy(jim + 0x20000, "abc", 3);
    memset(command, 0, sizeof(command)); command[0] = NTS_SEC_SFTP_PUT_WRITE;
    command[1] = 3; wr32(command + 4, 0x20000);
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(command[1] == 3);
    command[0] = NTS_SEC_SFTP_TRANSFER_CLOSE;
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    command[0] = NTS_SEC_SFTP_CLOSE;
    assert(nts_secure_dispatch(&service, command, jim, sizeof(jim)) == NTS_OK);
    assert(!state.sftp_opened);
    puts("Pi1MHz secure-service ABI core: OK");
    return 0;
}
