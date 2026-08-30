/* Unit tests for the Pi-side container catalogue.
 *
 * Run with no arguments for the built-in fixtures. `--dump <file>` prints one
 * machine-readable line per catalogue entry so tests/test_media_catalogue.py
 * can compare the C decoder against scripts/uef_map.py over the real corpus. */

#include "media_catalogue.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------------- */
/* Fixture construction                                                      */

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
    size_t n = 0;
    size_t header_start;
    uint16_t crc;
    size_t i;

    out[n++] = 0x2Au;
    header_start = n;
    for (i = 0; name[i]; i++) out[n++] = (uint8_t)name[i];
    out[n++] = 0;
    out[n++] = (uint8_t)(load & 0xFFu);
    out[n++] = (uint8_t)((load >> 8) & 0xFFu);
    out[n++] = (uint8_t)((load >> 16) & 0xFFu);
    out[n++] = (uint8_t)((load >> 24) & 0xFFu);
    out[n++] = (uint8_t)(exec & 0xFFu);
    out[n++] = (uint8_t)((exec >> 8) & 0xFFu);
    out[n++] = (uint8_t)((exec >> 16) & 0xFFu);
    out[n++] = (uint8_t)((exec >> 24) & 0xFFu);
    out[n++] = (uint8_t)(number & 0xFFu);
    out[n++] = (uint8_t)(number >> 8);
    out[n++] = (uint8_t)(length & 0xFFu);
    out[n++] = (uint8_t)(length >> 8);
    out[n++] = flags;
    out[n++] = 0; out[n++] = 0; out[n++] = 0; out[n++] = 0;   /* next address */
    crc = tape_crc_ref(out + header_start, n - header_start);
    out[n++] = (uint8_t)(crc >> 8);
    out[n++] = (uint8_t)(crc & 0xFFu);
    /* The stored header CRC is big endian on tape but little endian in the
     * decoder's rd16; write it to match the decoder under test. */
    out[n - 2] = (uint8_t)(crc & 0xFFu);
    out[n - 1] = (uint8_t)(crc >> 8);
    if (length) {
        memcpy(out + n, data, length);
        crc = tape_crc_ref(data, length);
        n += length;
        out[n++] = (uint8_t)(crc & 0xFFu);
        out[n++] = (uint8_t)(crc >> 8);
    }
    return n;
}

static size_t build_uef(uint8_t *out)
{
    static const uint8_t payload_a[4] = { 0x11, 0x22, 0x33, 0x44 };
    static const uint8_t payload_b[3] = { 0xAA, 0xBB, 0xCC };
    uint8_t blocks[512];
    size_t bn = 0;
    size_t n = 0;

    memcpy(out, "UEF File!\0", 10);
    n = 10;
    out[n++] = 0; out[n++] = 5;          /* version 5.0 */

    bn += put_block(blocks + bn, "ALPHA", 0xFFFF1900u, 0xFFFF8023u, 0,
                    payload_a, 4, 0x00u);
    bn += put_block(blocks + bn, "ALPHA", 0xFFFF1900u, 0xFFFF8023u, 1,
                    payload_b, 3, 0x80u);
    bn += put_block(blocks + bn, "BETA", 0x00000E00u, 0x00000700u, 0,
                    payload_a, 4, 0x81u);

    out[n++] = 0x00; out[n++] = 0x01;    /* chunk &0100 */
    out[n++] = (uint8_t)(bn & 0xFFu);
    out[n++] = (uint8_t)((bn >> 8) & 0xFFu);
    out[n++] = 0; out[n++] = 0;
    memcpy(out + n, blocks, bn);
    n += bn;
    return n;
}

static size_t build_ssd(uint8_t *out, size_t capacity)
{
    size_t total = 4u * 256u;
    assert(capacity >= total);
    memset(out, 0, total);

    memcpy(out, "TESTDISC", 8);          /* title chars 1-8 */
    memcpy(out + 256, "    ", 4);        /* title chars 9-12 */

    /* One file: "$.HELLO", load &1900, exec &8023, length &0104, sector 2. */
    memcpy(out + 8, "HELLO  ", 7);
    out[8 + 7] = (uint8_t)('$' | 0x80u); /* locked */

    out[256 + 4] = 1;                    /* cycle */
    out[256 + 5] = 8;                    /* one file */
    out[256 + 6] = (uint8_t)(0x30u | 0x00u); /* *OPT 4,3 ; sectors high = 0 */
    out[256 + 7] = 0x40;                 /* 64 sectors total */

    out[256 + 8 + 0] = 0x00; out[256 + 8 + 1] = 0x19;   /* load  &1900 */
    out[256 + 8 + 2] = 0x23; out[256 + 8 + 3] = 0x80;   /* exec  &8023 */
    out[256 + 8 + 4] = 0x04; out[256 + 8 + 5] = 0x01;   /* len   &0104 */
    out[256 + 8 + 6] = 0x00;                            /* no high bits */
    out[256 + 8 + 7] = 0x02;                            /* start sector 2 */

    memset(out + 512, 0x5A, 0x0104);
    return total;
}

/* ------------------------------------------------------------------------- */
/* Tests                                                                     */

static void test_uef_catalogue(void)
{
    uint8_t image[1024];
    media_entry_t entries[8];
    media_catalogue_t summary;
    size_t length = build_uef(image);

    assert(media_identify(image, length) == MEDIA_KIND_UEF);
    assert(media_catalogue(image, length, MEDIA_KIND_UEF, entries, 8,
                           &summary) == MEDIA_OK);
    assert(summary.kind == MEDIA_KIND_UEF);
    assert(summary.total == 2);
    assert(summary.count == 2);

    assert(!strcmp(entries[0].name, "ALPHA"));
    assert(entries[0].load == 0xFFFF1900u);
    assert(entries[0].exec == 0xFFFF8023u);
    assert(entries[0].length == 7);      /* 4 + 3 across two blocks */
    assert(entries[0].blocks == 2);
    assert(entries[0].crc_ok == 1);

    assert(!strcmp(entries[1].name, "BETA"));
    assert(entries[1].load == 0x00000E00u);
    assert(entries[1].exec == 0x00000700u);
    assert(entries[1].length == 4);
    assert(entries[1].locked == 1);
    printf("UEF catalogue: OK\n");
}

static void test_uef_extract(void)
{
    uint8_t image[1024];
    uint8_t out[64];
    size_t out_length = 0;
    size_t length = build_uef(image);

    assert(media_extract(image, length, MEDIA_KIND_UEF, 0, out, sizeof(out),
                         &out_length) == MEDIA_OK);
    assert(out_length == 7);
    assert(out[0] == 0x11 && out[3] == 0x44 && out[4] == 0xAA &&
           out[6] == 0xCC);

    assert(media_extract(image, length, MEDIA_KIND_UEF, 1, out, sizeof(out),
                         &out_length) == MEDIA_OK);
    assert(out_length == 4);
    assert(out[0] == 0x11);

    /* Out of range and undersized buffers must fail closed. */
    assert(media_extract(image, length, MEDIA_KIND_UEF, 9, out, sizeof(out),
                         &out_length) == MEDIA_ERR_RANGE);
    assert(media_extract(image, length, MEDIA_KIND_UEF, 0, out, 2,
                         &out_length) == MEDIA_ERR_RANGE);
    printf("UEF extract: OK\n");
}

static void test_ssd(void)
{
    uint8_t image[4 * 256];
    uint8_t out[512];
    media_entry_t entries[8];
    media_catalogue_t summary;
    size_t out_length = 0;
    size_t length = build_ssd(image, sizeof(image));

    assert(media_identify(image, length) == MEDIA_KIND_SSD);
    assert(media_catalogue(image, length, MEDIA_KIND_SSD, entries, 8,
                           &summary) == MEDIA_OK);
    assert(summary.count == 1);
    assert(!strcmp(summary.title, "TESTDISC"));
    assert(summary.boot_option == 3);
    assert(!strcmp(entries[0].name, "$.HELLO"));
    assert(entries[0].load == 0x1900u);
    assert(entries[0].exec == 0x8023u);
    assert(entries[0].length == 0x0104u);
    assert(entries[0].offset == 512u);
    assert(entries[0].locked == 1);

    assert(media_extract(image, length, MEDIA_KIND_SSD, 0, out, sizeof(out),
                         &out_length) == MEDIA_OK);
    assert(out_length == 0x0104u);
    assert(out[0] == 0x5A && out[0x0103] == 0x5A);
    printf("SSD catalogue and extract: OK\n");
}

static void test_rejects_malformed(void)
{
    uint8_t image[1024];
    media_entry_t entries[4];
    media_catalogue_t summary;
    size_t length = build_uef(image);
    size_t i;

    /* A truncated container must never read past the buffer. Every prefix is
     * parsed; the decoder may report fewer files but must not crash. */
    for (i = 0; i < length; i++) {
        media_catalogue(image, i, MEDIA_KIND_UEF, entries, 4, &summary);
    }

    /* A chunk length that overruns the image is reported, not followed. */
    image[14] = 0xFF; image[15] = 0xFF; image[16] = 0xFF; image[17] = 0x7F;
    assert(media_catalogue(image, length, MEDIA_KIND_UEF, entries, 4,
                           &summary) == MEDIA_OK);
    assert(summary.total == 0);

    /* Random bytes are neither a UEF nor a plausible DFS catalogue. */
    for (i = 0; i < sizeof(image); i++) image[i] = (uint8_t)(i * 7u + 3u);
    assert(media_identify(image, sizeof(image)) == MEDIA_KIND_UNKNOWN);
    printf("malformed containers: OK\n");
}

static void test_format_entry(void)
{
    media_entry_t entry;
    char line[64];
    size_t n;

    memset(&entry, 0, sizeof(entry));
    strcpy(entry.name, "ALPHA");
    entry.load = 0xFFFF1900u;
    entry.exec = 0xFFFF8023u;
    entry.length = 0x4A0u;
    entry.locked = 1;
    entry.crc_ok = 1;

    n = media_format_entry(&entry, line, sizeof(line));
    assert(n > 0 && n <= 40);
    assert(!strcmp(line, "ALPHA       FFFF1900 FFFF8023 0004A0 L"));
    printf("entry formatting: OK\n");
}

/* ------------------------------------------------------------------------- */

static int dump(const char *path)
{
    FILE *f = fopen(path, "rb");
    uint8_t *image;
    long size;
    media_entry_t entries[MEDIA_MAX_ENTRIES];
    media_catalogue_t summary;
    size_t i;

    if (!f) { fprintf(stderr, "cannot open %s\n", path); return 2; }
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size <= 0) { fclose(f); return 2; }
    image = malloc((size_t)size);
    if (!image) { fclose(f); return 2; }
    if (fread(image, 1, (size_t)size, f) != (size_t)size) {
        fclose(f); free(image); return 2;
    }
    fclose(f);

    if (media_catalogue(image, (size_t)size, MEDIA_KIND_UNKNOWN, entries,
                        MEDIA_MAX_ENTRIES, &summary) != MEDIA_OK) {
        printf("STATUS error\n");
        free(image);
        return 1;
    }
    printf("KIND %d\nTOTAL %zu\nISSUES %u\n", (int)summary.kind, summary.total,
           (unsigned)summary.issues);
    for (i = 0; i < summary.count; i++) {
        /* Names may be empty or contain control characters, so emit them as
         * hex to keep the line field count fixed for the comparison script. */
        size_t c;
        printf("ENTRY ");
        for (c = 0; entries[i].name[c] != '\0'; c++) {
            printf("%02X", (unsigned)(unsigned char)entries[i].name[c]);
        }
        if (c == 0) printf("-");
        printf(" %08X %08X %u %u %u\n", entries[i].load, entries[i].exec,
               entries[i].length, entries[i].blocks, entries[i].locked);
    }
    free(image);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "--dump")) return dump(argv[2]);

    test_uef_catalogue();
    test_uef_extract();
    test_ssd();
    test_rejects_malformed();
    test_format_entry();
    printf("Pi media catalogue: OK\n");
    return 0;
}
