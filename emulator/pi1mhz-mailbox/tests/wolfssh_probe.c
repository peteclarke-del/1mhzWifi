#include "pi1mhz_wolfssh.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static void pause_short(void)
{
    const struct timespec delay = { 0, 1000000 };
    nanosleep(&delay, NULL);
}

static unsigned connect_until_done(pi1mhz_wolfssh *provider, const char *url,
                                   int trust, char fingerprint[96])
{
    unsigned result = 1;
    unsigned attempts;
    for (attempts = 0; attempts < 20000 && result == 1; attempts++) {
        result = pi1mhz_wolfssh_open(provider, url, "test", trust, fingerprint);
        if (result == 1) pause_short();
    }
    return result;
}

int main(int argc, char **argv)
{
    pi1mhz_wolfssh *provider;
    char url[128], fingerprint[96] = { 0 };
    uint8_t buffer[256];
    int count = 0;
    unsigned result;
    const char *mode = argc == 4 ? argv[3] : "success";
    if (argc < 3 || argc > 4) return 2;
    snprintf(url, sizeof(url), "TCP://127.0.0.1:%s/", argv[1]);
    provider = pi1mhz_wolfssh_create(argv[2]);
    assert(provider);

    if (!strcmp(mode, "changed-host") || !strcmp(mode, "auth-fail")) {
        result = connect_until_done(provider, url, 1, fingerprint);
        assert(result == (!strcmp(mode, "changed-host") ? 0x2B : 0x2D));
        pi1mhz_wolfssh_destroy(provider);
        printf("Real wolfSSH %s rejection: OK\n", mode);
        return 0;
    }
    assert(!strcmp(mode, "success") || !strcmp(mode, "password"));

    if (!strcmp(mode, "password"))
        assert(pi1mhz_wolfssh_password(
                   provider, (const uint8_t *)"secret", 6) == 0);

    result = connect_until_done(provider, url, 0, fingerprint);
    fprintf(stderr, "first open result=%02X fingerprint=%s\n", result,
            fingerprint);
    assert(result == 0x2C);
    assert(!strncmp(fingerprint, "SHA256:", 7));

    result = connect_until_done(provider, url, 1, fingerprint);
    assert(result == 0);
    while (count == 0) {
        count = pi1mhz_wolfssh_read(provider, buffer, sizeof(buffer));
        assert(count >= 0);
        if (!count) pause_short();
    }
    assert(count < (int)sizeof(buffer));
    buffer[count] = 0;
    assert(strstr((char *)buffer, "REAL SSH OK"));
    assert(pi1mhz_wolfssh_write(provider, (const uint8_t *)"x\r", 2) >= 0);
    pi1mhz_wolfssh_close(provider);
    pi1mhz_wolfssh_destroy(provider);
    printf("Real wolfSSH host-key/%s-auth/PTY/channel probe: OK\n",
           !strcmp(mode, "password") ? "password" : "public-key");
    return 0;
}
