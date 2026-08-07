#include "pi1mhz_elkulator.h"

#include "pi1mhz_mailbox.h"
#include "pi1mhz_net_backend.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int initialised;
static int enabled;
static pi1mhz_mailbox mailbox;
static pi1mhz_net_backend *backend;

static int preload_jim(void)
{
    const char *path = getenv("PI1MHZ_JIM_IMAGE");
    const char *address_setting = getenv("PI1MHZ_JIM_IMAGE_ADDRESS");
    char *end = NULL;
    unsigned long address = 0;
    FILE *file;
    long length;
    size_t loaded;

    if (!path || !*path)
        return 0;
    if (address_setting && *address_setting) {
        address = strtoul(address_setting, &end, 0);
        if (!end || *end || address >= mailbox.jim_size) {
            fprintf(stderr, "Pi1MHz mailbox: invalid JIM image address %s\n",
                    address_setting);
            return -1;
        }
    }
    file = fopen(path, "rb");
    if (!file) {
        fprintf(stderr, "Pi1MHz mailbox: cannot open JIM image %s\n", path);
        return -1;
    }
    if (fseek(file, 0, SEEK_END) || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET)) {
        fprintf(stderr, "Pi1MHz mailbox: cannot size JIM image %s\n", path);
        fclose(file);
        return -1;
    }
    if ((size_t)length > mailbox.jim_size - (size_t)address) {
        fprintf(stderr, "Pi1MHz mailbox: JIM image exceeds available RAM\n");
        fclose(file);
        return -1;
    }
    loaded = fread(mailbox.jim + address, 1, (size_t)length, file);
    if (loaded != (size_t)length || fclose(file)) {
        fprintf(stderr, "Pi1MHz mailbox: failed reading JIM image %s\n", path);
        return -1;
    }
    fprintf(stderr, "Pi1MHz mailbox: loaded %lu bytes at &%06lX from %s\n",
            (unsigned long)loaded, address, path);
    return 0;
}

static void shutdown_device(void)
{
    pi1mhz_mailbox_destroy(&mailbox);
    pi1mhz_net_backend_destroy(backend);
    backend = NULL;
}

static void initialise_device(void)
{
    const char *mode;
    const char *trace;
    const char *exit_setting;
    if (initialised)
        return;
    initialised = 1;
    mode = getenv("PI1MHZ_MAILBOX");
    if (!mode || (!strcmp(mode, "0") || !strcmp(mode, "off")))
        return;
    trace = getenv("PI1MHZ_TRACE");
    exit_setting = getenv("PI1MHZ_EXIT_ON_CLOSE");
    backend = pi1mhz_net_backend_create(
        mode, trace, exit_setting && strcmp(exit_setting, "0"));
    if (!backend || pi1mhz_mailbox_init(
            &mailbox, pi1mhz_net_backend_dispatch, backend)) {
        fprintf(stderr, "Pi1MHz mailbox: initialisation failed\n");
        pi1mhz_net_backend_destroy(backend);
        backend = NULL;
        return;
    }
    if (preload_jim()) {
        pi1mhz_mailbox_destroy(&mailbox);
        pi1mhz_net_backend_destroy(backend);
        backend = NULL;
        return;
    }
    enabled = 1;
    atexit(shutdown_device);
    fprintf(stderr, "Pi1MHz mailbox: %s backend enabled\n", mode);
}

int pi1mhz_elkulator_enabled(void)
{
    initialise_device();
    return enabled;
}

int pi1mhz_elkulator_handles(uint16_t address)
{
    if (!pi1mhz_elkulator_enabled())
        return 0;

    /* Model the AP5 address decoder, not a Pi1MHz wired directly to a BBC.
       The AP5 forwards &FCFF but not Pi1MHz's extended &FCFD/&FCFE page
       selectors. Let Elkulator handle those two host-side addresses while
       the Pi mailbox retains its high and middle selectors at zero. */
    return pi1mhz_mailbox_ap5_handles(address);
}

uint8_t pi1mhz_elkulator_read(uint16_t address)
{
    return pi1mhz_mailbox_read(&mailbox, address);
}

void pi1mhz_elkulator_write(uint16_t address, uint8_t value)
{
    pi1mhz_mailbox_write(&mailbox, address, value);
}
