/* Drives media_service.c, the transport binding, off-target.
 *
 * media_service_core.c is already covered by test_media_service_core.c. What
 * is exercised here is only what the binding adds: reading a command block out
 * of JIM, opening whatever the host last uploaded, copying a bounded reply
 * back, and reporting the core's status. The Pi1MHz declarations come from
 * pi-side/tests/stubs, so this proves the transport's own logic and not the
 * kernel build.
 */

#include "media_service.h"
#include "media_service_core.h"
#include "Pi1MHz.h"
#include "ram_emulator.h"
#include "services.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static pi1mhz_stub_t stub_memory;
pi1mhz_stub_t *Pi1MHz = &stub_memory;

static uint8_t written_status;
static uint32_t written_address;
static int write_count;

void Pi1MHz_MemoryWrite(uint32_t address, uint8_t value)
{
    written_address = address;
    written_status = value;
    write_count++;
}

static uint8_t registered_first, registered_last;
static int register_count;

bool services_register(uint8_t first, uint8_t last, service_handler_t handler)
{
    registered_first = first;
    registered_last = last;
    register_count++;
    (void)handler;
    return true;
}

/* The container the binding is expected to open. */
static uint8_t upload[4096];
static size_t upload_length;
static int upload_ready;

const uint8_t *elkwifi_uef_stream_image(size_t *length)
{
    if (!upload_ready) {
        if (length) *length = 0;
        return NULL;
    }
    if (length) *length = upload_length;
    return upload;
}

#define CP_HOST 0xff0000u
#define CP      (CP_HOST - 0xff0000u + DISC_RAM_BASE)
#define STATUS_ADDRESS 0x1234u

static uint8_t call(uint8_t command, uint8_t a1, uint8_t a2, uint8_t a3)
{
    Pi1MHz->JIM_ram[CP] = command;
    Pi1MHz->JIM_ram[CP + 1u] = a1;
    Pi1MHz->JIM_ram[CP + 2u] = a2;
    Pi1MHz->JIM_ram[CP + 3u] = a3;
    media_service_command(CP_HOST, STATUS_ADDRESS, 0);
    return written_status;
}

/* A two-file DFS image: catalogue sectors plus one sector of data. */
static void build_ssd(void)
{
    static const struct { const char *name; uint16_t load, length; } files[] = {
        { "BOOT", 0x1900u, 0x0010u },
        { "GAME", 0x0E00u, 0x0100u },
    };
    size_t i;
    memset(upload, 0, sizeof upload);
    memcpy(upload, "TESTDISC", 8);
    upload[256 + 5] = (uint8_t)(2u * 8u);
    upload[256 + 6] = 0x30u;                 /* *OPT 4,3 */
    upload[256 + 7] = 0x20u;                 /* 800 sectors, low byte */
    for (i = 0; i < 2u; i++) {
        size_t at = 8u + i * 8u;
        memcpy(&upload[at], files[i].name, strlen(files[i].name));
        memset(&upload[at + strlen(files[i].name)], ' ',
               7u - strlen(files[i].name));
        upload[at + 7u] = (uint8_t)'$';
        upload[256u + at + 0u] = (uint8_t)(files[i].load & 0xFFu);
        upload[256u + at + 1u] = (uint8_t)(files[i].load >> 8);
        upload[256u + at + 4u] = (uint8_t)(files[i].length & 0xFFu);
        upload[256u + at + 5u] = (uint8_t)(files[i].length >> 8);
        upload[256u + at + 7u] = 2u;         /* start sector */
    }
    upload_length = sizeof upload;
    upload_ready = 1;
}

int main(void)
{
    uint8_t status;
    size_t lines;

    media_service_init();
    assert(register_count == 1);
    assert(registered_first == MEDIA_SVC_CMD_FIRST);
    assert(registered_last == MEDIA_SVC_CMD_LAST);
    assert(registered_first == MEDIA_CMD_OPEN);
    assert(registered_last == MEDIA_CMD_CLOSE);

    /* Opening with nothing uploaded is a parameter error, not a crash or a
     * stale session from a previous container. */
    upload_ready = 0;
    status = call(MEDIA_CMD_OPEN, 0, 0, 0);
    assert(status == MEDIA_SVC_ERR_PARAM);
    assert(write_count == 1);
    assert(written_address == STATUS_ADDRESS);

    /* A catalogue read before any open is refused by the core. */
    status = call(MEDIA_CMD_CAT, 0, 0, 0);
    assert(status == MEDIA_SVC_ERR_PARAM);

    build_ssd();
    status = call(MEDIA_CMD_OPEN, 0, 0, 0);
    assert(status == MEDIA_SVC_OK);
    /* kind, count, total, boot option, written at cp + 1. */
    assert(Pi1MHz->JIM_ram[CP + 1u] == (uint8_t)MEDIA_KIND_SSD);
    assert(Pi1MHz->JIM_ram[CP + 2u] == 2u);
    assert(Pi1MHz->JIM_ram[CP + 3u] == 2u);

    /* Each catalogue line comes back CR terminated and NUL terminated after
     * it, so the host can print straight from the window. */
    for (lines = 0; lines < 2u; lines++) {
        status = call(MEDIA_CMD_CAT, 0, 0, 0);
        assert(status == MEDIA_SVC_OK);
        assert(strchr((const char *)&Pi1MHz->JIM_ram[CP + 1u], 0x0D) != NULL);
    }
    status = call(MEDIA_CMD_CAT, 0, 0, 0);
    assert(status == MEDIA_SVC_EOF);

    /* Metadata for entry 0 carries the load address the catalogue recorded. */
    status = call(MEDIA_CMD_INFO, 0, 0, 0);
    assert(status == MEDIA_SVC_OK);
    assert(Pi1MHz->JIM_ram[CP + 1u] == 0x00u);
    assert(Pi1MHz->JIM_ram[CP + 2u] == 0x19u);

    status = call(MEDIA_CMD_INFO, 9, 0, 0);
    assert(status == MEDIA_SVC_ERR_RANGE);

    /* A read returns a length-prefixed window. */
    status = call(MEDIA_CMD_READ, 1, 0, 0);
    assert(status == MEDIA_SVC_OK);
    assert(Pi1MHz->JIM_ram[CP + 4u] > 0u);

    status = call(MEDIA_CMD_CLOSE, 0, 0, 0);
    assert(status == MEDIA_SVC_OK);
    status = call(MEDIA_CMD_CAT, 0, 0, 0);
    assert(status == MEDIA_SVC_ERR_PARAM);

    /* An unallocated command in the range is refused rather than dispatched. */
    status = call(199, 0, 0, 0);
    assert(status == MEDIA_SVC_ERR_PARAM);

    printf("media service binding: OK\n");
    return 0;
}
