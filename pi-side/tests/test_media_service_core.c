/* Unit tests for the media service session core.
 *
 * With no arguments this runs the built-in fixtures. `--roundtrip <file>`
 * drives a complete host conversation against a real container: open, read
 * every catalogue line, then stream every entry back through bounded windows,
 * printing what was recovered so tests/test_media_catalogue.py can compare it
 * against scripts/uef_map.py. */

#include "media_service_core.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t tape_crc_ref(const uint8_t *data, size_t length)
{
    uint16_t crc = 0;
    size_t i;
    unsigned bit;
    for (i = 0; i < length; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (bit = 0; bit < 8; bit++) {
            if (crc & 0x8000u) {
                crc = (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

static size_t put_block(uint8_t *out, const char *name, uint32_t load,
                        uint32_t exec, uint16_t number, const uint8_t *data,
                        uint16_t length, uint8_t flags)
{
    size_t n = 0, header_start, i;
    uint16_t crc;

    out[n++] = 0x2Au;
    header_start = n;
    for (i = 0; name[i]; i++) out[n++] = (uint8_t)name[i];
    out[n++] = 0;
    for (i = 0; i < 4; i++) out[n++] = (uint8_t)((load >> (8 * i)) & 0xFFu);
    for (i = 0; i < 4; i++) out[n++] = (uint8_t)((exec >> (8 * i)) & 0xFFu);
    out[n++] = (uint8_t)(number & 0xFFu);
    out[n++] = (uint8_t)(number >> 8);
    out[n++] = (uint8_t)(length & 0xFFu);
    out[n++] = (uint8_t)(length >> 8);
    out[n++] = flags;
    out[n++] = 0; out[n++] = 0; out[n++] = 0; out[n++] = 0;
    crc = tape_crc_ref(out + header_start, n - header_start);
    out[n++] = (uint8_t)(crc & 0xFFu);
    out[n++] = (uint8_t)(crc >> 8);
    if (length) {
        memcpy(out + n, data, length);
        crc = tape_crc_ref(data, length);
        n += length;
        out[n++] = (uint8_t)(crc & 0xFFu);
        out[n++] = (uint8_t)(crc >> 8);
    }
    return n;
}

/* A UEF whose single file is large enough to need several read windows. */
static size_t build_uef(uint8_t *out, uint8_t *expect, size_t *expect_length)
{
    uint8_t payload[256];
    uint8_t blocks[4096];
    size_t bn = 0, n = 0, i, b;

    for (i = 0; i < sizeof(payload); i++) payload[i] = (uint8_t)(i ^ 0x5Au);
    memcpy(out, "UEF File!\0", 10);
    n = 10;
    out[n++] = 0; out[n++] = 5;

    *expect_length = 0;
    for (b = 0; b < 3; b++) {
        bn += put_block(blocks + bn, "BIG", 0xFFFF1900u, 0xFFFF8023u,
                        (uint16_t)b, payload, (uint16_t)sizeof(payload),
                        b == 2 ? 0x80u : 0x00u);
        memcpy(expect + *expect_length, payload, sizeof(payload));
        *expect_length += sizeof(payload);
    }
    out[n++] = 0x00; out[n++] = 0x01;
    out[n++] = (uint8_t)(bn & 0xFFu);
    out[n++] = (uint8_t)((bn >> 8) & 0xFFu);
    out[n++] = 0; out[n++] = 0;
    memcpy(out + n, blocks, bn);
    return n + bn;
}

static void test_open_reports_kind_and_count(void)
{
    uint8_t image[8192], expect[4096], reply[MEDIA_SVC_REPLY_MAX];
    uint8_t command[4] = { MEDIA_CMD_OPEN, 0, 0, 0 };
    size_t expect_length, length, reply_length = 0;
    media_service service;

    length = build_uef(image, expect, &expect_length);
    assert(media_service_open(&service, image, length) == MEDIA_SVC_OK);
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_OK);
    assert(reply_length == 4);
    assert(reply[0] == MEDIA_KIND_UEF);
    assert(reply[1] == 1);
    printf("open reports kind and count: OK\n");
}

static void test_cat_walks_every_entry_then_reports_eof(void)
{
    uint8_t image[8192], expect[4096], reply[MEDIA_SVC_REPLY_MAX];
    uint8_t command[4] = { MEDIA_CMD_CAT, 0, 0, 0 };
    size_t expect_length, length, reply_length = 0;
    media_service service;
    unsigned lines = 0;

    length = build_uef(image, expect, &expect_length);
    assert(media_service_open(&service, image, length) == MEDIA_SVC_OK);
    while (media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_OK) {
        assert(reply_length > 1);
        assert(reply[reply_length - 1] == 0x0Du);
        assert(reply_length <= MEDIA_SVC_REPLY_MAX);
        lines++;
        assert(lines < 200);
    }
    assert(lines == 1);
    /* Further calls must keep reporting EOF rather than wrapping. */
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_EOF);
    printf("cat walks entries then reports EOF: OK\n");
}

static void test_read_streams_exact_bytes_across_windows(void)
{
    uint8_t image[8192], expect[4096], reply[MEDIA_SVC_REPLY_MAX];
    uint8_t got[4096];
    uint8_t command[4] = { MEDIA_CMD_READ, 0, 0, 0 };
    size_t expect_length, length, reply_length = 0, total = 0;
    media_service service;
    unsigned windows = 0;
    uint8_t status;

    length = build_uef(image, expect, &expect_length);
    assert(media_service_open(&service, image, length) == MEDIA_SVC_OK);

    while ((status = media_service_dispatch(&service, command, reply,
                                            sizeof(reply), &reply_length))
           == MEDIA_SVC_OK) {
        size_t remaining = (size_t)reply[0] | ((size_t)reply[1] << 8) |
                           ((size_t)reply[2] << 16);
        size_t window = reply[3];
        assert(reply_length == window + 4u);
        assert(remaining == expect_length - total);
        memcpy(got + total, reply + 4, window);
        total += window;
        windows++;
        assert(windows < 200);
    }
    assert(status == MEDIA_SVC_EOF);
    assert(total == expect_length);
    assert(!memcmp(got, expect, expect_length));
    assert(windows > 1);   /* the fixture is deliberately multi-window */
    printf("read streams exact bytes across %u windows: OK\n", windows);
}

static void test_bounds_and_closed_sessions_fail_closed(void)
{
    uint8_t image[8192], expect[4096], reply[MEDIA_SVC_REPLY_MAX];
    uint8_t command[4] = { MEDIA_CMD_INFO, 99, 0, 0 };
    size_t expect_length, length, reply_length = 0;
    media_service service;

    length = build_uef(image, expect, &expect_length);
    assert(media_service_open(&service, image, length) == MEDIA_SVC_OK);
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_ERR_RANGE);

    command[0] = MEDIA_CMD_READ;
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_ERR_RANGE);

    /* An unknown command is refused rather than silently accepted. */
    command[0] = 200;
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_ERR_PARAM);

    /* After close every command must report a parameter error, not read
     * through a dangling image pointer. */
    command[0] = MEDIA_CMD_CLOSE;
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_OK);
    command[0] = MEDIA_CMD_CAT;
    assert(media_service_dispatch(&service, command, reply, sizeof(reply),
                                  &reply_length) == MEDIA_SVC_ERR_PARAM);

    /* A container that is neither UEF nor DFS is refused. */
    memset(image, 0x99, sizeof(image));
    assert(media_service_open(&service, image, sizeof(image))
           == MEDIA_SVC_ERR_FORMAT);
    printf("bounds and closed sessions fail closed: OK\n");
}

static int roundtrip(const char *path)
{
    FILE *f = fopen(path, "rb");
    uint8_t *image;
    long size;
    media_service service;
    uint8_t reply[MEDIA_SVC_REPLY_MAX];
    uint8_t command[4] = { 0, 0, 0, 0 };
    size_t reply_length = 0;
    unsigned index;

    if (!f) return 2;
    fseek(f, 0, SEEK_END); size = ftell(f); fseek(f, 0, SEEK_SET);
    if (size <= 0) { fclose(f); return 2; }
    image = malloc((size_t)size);
    if (!image || fread(image, 1, (size_t)size, f) != (size_t)size) {
        fclose(f); free(image); return 2;
    }
    fclose(f);

    if (media_service_open(&service, image, (size_t)size) != MEDIA_SVC_OK) {
        printf("STATUS open-failed\n"); free(image); return 1;
    }
    printf("COUNT %zu\n", service.summary.count);
    for (index = 0; index < service.summary.count; index++) {
        size_t total = 0;
        unsigned windows = 0;
        uint8_t status;
        command[0] = MEDIA_CMD_READ;
        command[1] = (uint8_t)index;
        while ((status = media_service_dispatch(&service, command, reply,
                                                sizeof(reply), &reply_length))
               == MEDIA_SVC_OK) {
            total += reply[3];
            if (++windows > 20000) break;
        }
        printf("STREAM %u %zu %s\n", index, total,
               status == MEDIA_SVC_EOF ? "eof" : "error");
    }
    free(image);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "--roundtrip")) return roundtrip(argv[2]);

    test_open_reports_kind_and_count();
    test_cat_walks_every_entry_then_reports_eof();
    test_read_streams_exact_bytes_across_windows();
    test_bounds_and_closed_sessions_fail_closed();
    printf("Pi media service core: OK\n");
    return 0;
}
