#include "media_catalogue.h"

#include <string.h>

/* ------------------------------------------------------------------------- */
/* Shared helpers                                                            */

static uint16_t rd16(const uint8_t *p)
{
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Acorn cassette CRC: CCITT with the polynomial applied high byte first. */
static uint16_t tape_crc(const uint8_t *data, size_t length)
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

/* ------------------------------------------------------------------------- */
/* UEF cassette streams                                                      */

#define UEF_MAGIC       "UEF File!"
#define UEF_MAGIC_LEN   10u     /* includes the terminating NUL */
#define UEF_HEADER_LEN  12u     /* magic plus two version bytes */
#define UEF_CHUNK_DATA  0x0100u

/* One decoded CFS block header. `data_offset` is relative to the image. */
typedef struct {
    char     name[MEDIA_NAME_MAX];
    uint32_t load;
    uint32_t exec;
    uint16_t block;
    uint16_t data_length;
    uint8_t  flags;
    size_t   data_offset;
    int      crc_ok;
} cfs_block_t;

/* Decode the CFS block starting at `image[pos]`. Returns the offset just past
 * the block, or 0 if the block is malformed or runs off the end. */
static size_t cfs_decode_block(const uint8_t *image, size_t chunk_end,
                               size_t pos, cfs_block_t *out)
{
    size_t name_start;
    size_t name_len = 0;
    size_t header_start;
    size_t header_len;
    uint16_t stored_crc;
    uint16_t computed;

    if (pos >= chunk_end || image[pos] != 0x2Au) return 0;
    pos++;

    /* Filename: up to ten characters then a NUL. */
    name_start = pos;
    while (pos < chunk_end && image[pos] != 0 && name_len < MEDIA_NAME_MAX - 1) {
        name_len++;
        pos++;
    }
    if (pos >= chunk_end || image[pos] != 0) return 0;
    pos++;   /* consume the NUL */

    /* Fixed header: load(4) exec(4) block(2) length(2) flags(1) next(4)
     * followed by the header CRC(2). The CRC covers the name, its NUL and the
     * nineteen fixed bytes. */
    header_start = name_start;
    if (pos + 17u + 2u > chunk_end) return 0;

    memset(out, 0, sizeof(*out));
    memcpy(out->name, image + name_start, name_len);
    out->name[name_len] = '\0';
    out->load        = rd32(image + pos);
    out->exec        = rd32(image + pos + 4);
    out->block       = rd16(image + pos + 8);
    out->data_length = rd16(image + pos + 10);
    out->flags       = image[pos + 12];
    pos += 17u;

    header_len = pos - header_start;
    stored_crc = rd16(image + pos);
    computed   = tape_crc(image + header_start, header_len);
    out->crc_ok = (stored_crc == computed);
    pos += 2u;

    if (out->data_length == 0) {
        out->data_offset = pos;
        return pos;
    }

    if (pos + out->data_length + 2u > chunk_end) return 0;
    out->data_offset = pos;
    computed   = tape_crc(image + pos, out->data_length);
    stored_crc = rd16(image + pos + out->data_length);
    if (stored_crc != computed) out->crc_ok = 0;
    pos += (size_t)out->data_length + 2u;
    return pos;
}

/* Walk every &0100 chunk, decode its CFS blocks and group them into files.
 * `visit` is called once per block in stream order. */
typedef void (*cfs_visitor)(void *opaque, const cfs_block_t *block);

static media_status_t uef_walk(const uint8_t *image, size_t length,
                               cfs_visitor visit, void *opaque,
                               uint32_t *issues)
{
    size_t pos;

    if (length < UEF_HEADER_LEN) return MEDIA_ERR_FORMAT;
    if (memcmp(image, UEF_MAGIC, UEF_MAGIC_LEN) != 0) return MEDIA_ERR_FORMAT;

    pos = UEF_HEADER_LEN;
    while (pos + 6u <= length) {
        uint16_t type = rd16(image + pos);
        uint32_t clen = rd32(image + pos + 2);
        size_t data = pos + 6u;
        size_t end;

        if (clen > length || data + clen > length) {
            (*issues)++;
            return MEDIA_ERR_TRUNCATED;
        }
        end = data + clen;

        if (type == UEF_CHUNK_DATA) {
            size_t bp = data;
            while (bp < end) {
                cfs_block_t block;
                size_t next = cfs_decode_block(image, end, bp, &block);
                if (next == 0) {
                    /* Legal residual bytes after a block CRC are skipped by the
                     * original WiCFS, so stop scanning this chunk rather than
                     * rejecting the whole stream. */
                    if (bp != data) (*issues)++;
                    break;
                }
                visit(opaque, &block);
                bp = next;
            }
        }
        pos = end;
    }
    return MEDIA_OK;
}

typedef struct {
    media_entry_t *entries;
    size_t         max_entries;
    size_t         count;
    size_t         total;
    char           current[MEDIA_NAME_MAX];
    int            have_current;
    media_entry_t *open_entry;  /* entry receiving continuation blocks, or NULL */
    uint32_t       issues;
} uef_group_t;

static void uef_group_block(void *opaque, const cfs_block_t *block)
{
    uef_group_t *g = opaque;
    int is_new;

    is_new = !g->have_current || strcmp(g->current, block->name) != 0 ||
             block->block == 0;

    if (is_new) {
        g->total++;
        memcpy(g->current, block->name, MEDIA_NAME_MAX);
        g->have_current = 1;
        g->open_entry = NULL;
        if (g->entries && g->count < g->max_entries) {
            media_entry_t *e = &g->entries[g->count];
            memset(e, 0, sizeof(*e));
            memcpy(e->name, block->name, MEDIA_NAME_MAX);
            e->load   = block->load;
            e->exec   = block->exec;
            e->length = block->data_length;
            e->blocks = 1;
            e->locked = (uint8_t)(block->flags & 0x01u);
            e->crc_ok = (uint8_t)(block->crc_ok ? 1 : 0);
            g->count++;
            g->open_entry = e;
        }
        /* Beyond `max_entries` the file is still counted in `total`, but no
         * entry stays open, so its continuation blocks cannot be added to the
         * previous file's length. */
        return;
    }

    if (g->open_entry) {
        g->open_entry->length += block->data_length;
        g->open_entry->blocks++;
        if (!block->crc_ok) g->open_entry->crc_ok = 0;
    }
}

/* ------------------------------------------------------------------------- */
/* DFS disc images                                                           */

#define DFS_SECTOR        256u
#define DFS_MAX_FILES     31u

static int dfs_plausible(const uint8_t *image, size_t length)
{
    uint8_t file_bytes;
    unsigned files;
    unsigned i;

    if (length < 2u * DFS_SECTOR) return 0;
    if (length % DFS_SECTOR != 0) return 0;

    file_bytes = image[DFS_SECTOR + 5u];
    if (file_bytes % 8u != 0) return 0;
    files = file_bytes / 8u;
    if (files > DFS_MAX_FILES) return 0;

    /* Catalogue names are printable and the directory byte's low seven bits
     * must also be printable. A blank disc has zero files and still passes. */
    for (i = 0; i < files; i++) {
        const uint8_t *name = image + 8u + (size_t)i * 8u;
        unsigned c;
        for (c = 0; c < 8u; c++) {
            uint8_t ch = (uint8_t)(name[c] & 0x7Fu);
            if (ch < 0x20u || ch > 0x7Eu) return 0;
        }
    }
    return 1;
}

static media_status_t dfs_catalogue(const uint8_t *image, size_t length,
                                    media_entry_t *entries, size_t max_entries,
                                    media_catalogue_t *summary)
{
    unsigned files;
    unsigned i;
    size_t sectors_total;

    if (!dfs_plausible(image, length)) return MEDIA_ERR_FORMAT;

    files = image[DFS_SECTOR + 5u] / 8u;
    sectors_total = (size_t)image[DFS_SECTOR + 7u] |
                    ((size_t)(image[DFS_SECTOR + 6u] & 0x03u) << 8);
    summary->boot_option = (uint8_t)((image[DFS_SECTOR + 6u] >> 4) & 0x0Fu);

    /* Title is eight bytes in sector 0 followed by four in sector 1. */
    {
        char title[MEDIA_TITLE_MAX];
        size_t n = 0;
        unsigned c;
        for (c = 0; c < 8u && n < MEDIA_TITLE_MAX - 1u; c++) {
            uint8_t ch = (uint8_t)(image[c] & 0x7Fu);
            if (ch == 0 || ch == 0x20u) continue;
            title[n++] = (char)ch;
        }
        for (c = 0; c < 4u && n < MEDIA_TITLE_MAX - 1u; c++) {
            uint8_t ch = (uint8_t)(image[DFS_SECTOR + c] & 0x7Fu);
            if (ch == 0 || ch == 0x20u) continue;
            title[n++] = (char)ch;
        }
        title[n] = '\0';
        memcpy(summary->title, title, n + 1u);
    }

    summary->total = files;
    for (i = 0; i < files; i++) {
        const uint8_t *nm = image + 8u + (size_t)i * 8u;
        const uint8_t *md = image + DFS_SECTOR + 8u + (size_t)i * 8u;
        media_entry_t entry;
        uint8_t extra = md[6];
        size_t start_sector;
        size_t n = 0;
        unsigned c;

        memset(&entry, 0, sizeof(entry));
        entry.name[n++] = (char)(nm[7] & 0x7Fu);   /* directory */
        entry.name[n++] = '.';
        for (c = 0; c < 7u; c++) {
            uint8_t ch = (uint8_t)(nm[c] & 0x7Fu);
            if (ch == 0x20u) break;
            entry.name[n++] = (char)ch;
        }
        entry.name[n] = '\0';
        entry.locked = (uint8_t)((nm[7] & 0x80u) ? 1u : 0u);

        entry.load   = (uint32_t)rd16(md) |
                       ((uint32_t)((extra >> 2) & 0x03u) << 16);
        entry.exec   = (uint32_t)rd16(md + 2) |
                       ((uint32_t)((extra >> 6) & 0x03u) << 16);
        entry.length = (uint32_t)rd16(md + 4) |
                       ((uint32_t)((extra >> 4) & 0x03u) << 16);
        start_sector = (size_t)md[7] | ((size_t)(extra & 0x03u) << 8);
        entry.offset = (uint32_t)(start_sector * DFS_SECTOR);
        entry.crc_ok = 1u;

        /* Sign extend the Acorn 18-bit host addresses the way DFS does. */
        if ((entry.load & 0x30000u) == 0x30000u) entry.load |= 0xFFFC0000u;
        if ((entry.exec & 0x30000u) == 0x30000u) entry.exec |= 0xFFFC0000u;

        if ((size_t)entry.offset + entry.length > length) {
            summary->issues++;
            entry.crc_ok = 0u;
        }
        if (sectors_total && start_sector > sectors_total) summary->issues++;

        if (entries && summary->count < max_entries) {
            entries[summary->count++] = entry;
        }
    }
    return MEDIA_OK;
}

/* ------------------------------------------------------------------------- */
/* Public entry points                                                       */

media_kind_t media_identify(const uint8_t *image, size_t length)
{
    if (!image) return MEDIA_KIND_UNKNOWN;
    if (length >= UEF_HEADER_LEN &&
        memcmp(image, UEF_MAGIC, UEF_MAGIC_LEN) == 0) {
        return MEDIA_KIND_UEF;
    }
    if (dfs_plausible(image, length)) return MEDIA_KIND_SSD;
    return MEDIA_KIND_UNKNOWN;
}

media_status_t media_catalogue(const uint8_t *image, size_t length,
                               media_kind_t kind, media_entry_t *entries,
                               size_t max_entries, media_catalogue_t *summary)
{
    if (!image || !summary) return MEDIA_ERR_PARAM;
    if (entries && max_entries == 0) return MEDIA_ERR_PARAM;

    memset(summary, 0, sizeof(*summary));
    if (kind == MEDIA_KIND_UNKNOWN) kind = media_identify(image, length);
    summary->kind = kind;

    if (kind == MEDIA_KIND_UEF) {
        uef_group_t group;
        media_status_t status;

        memset(&group, 0, sizeof(group));
        group.entries = entries;
        group.max_entries = entries ? max_entries : 0;

        status = uef_walk(image, length, uef_group_block, &group,
                          &group.issues);
        summary->count  = group.count;
        summary->total  = group.total;
        summary->issues = group.issues;
        if (status == MEDIA_ERR_FORMAT) return status;
        return MEDIA_OK;
    }

    if (kind == MEDIA_KIND_SSD) return dfs_catalogue(image, length, entries,
                                                     max_entries, summary);
    return MEDIA_ERR_FORMAT;
}

typedef struct {
    size_t   want;
    size_t   seen;
    char     current[MEDIA_NAME_MAX];
    int      have_current;
    uint8_t *out;
    size_t   capacity;
    size_t   written;
    int      overflow;
    const uint8_t *image;
} uef_copy_t;

static void uef_copy_block(void *opaque, const cfs_block_t *block)
{
    uef_copy_t *c = opaque;
    int is_new = !c->have_current || strcmp(c->current, block->name) != 0 ||
                 block->block == 0;

    if (is_new) {
        if (c->have_current) c->seen++;
        memcpy(c->current, block->name, MEDIA_NAME_MAX);
        c->have_current = 1;
    }
    if (c->seen != c->want || !c->have_current) return;
    if (block->data_length == 0) return;
    if (c->written + block->data_length > c->capacity) {
        c->overflow = 1;
        return;
    }
    memcpy(c->out + c->written, c->image + block->data_offset,
           block->data_length);
    c->written += block->data_length;
}

media_status_t media_extract(const uint8_t *image, size_t length,
                             media_kind_t kind, size_t index, uint8_t *out,
                             size_t out_capacity, size_t *out_length)
{
    if (!image || !out || !out_length) return MEDIA_ERR_PARAM;
    *out_length = 0;
    if (kind == MEDIA_KIND_UNKNOWN) kind = media_identify(image, length);

    if (kind == MEDIA_KIND_UEF) {
        uef_copy_t copy;
        uint32_t issues = 0;
        media_status_t status;

        memset(&copy, 0, sizeof(copy));
        copy.want = index;
        copy.out = out;
        copy.capacity = out_capacity;
        copy.image = image;

        status = uef_walk(image, length, uef_copy_block, &copy, &issues);
        if (status == MEDIA_ERR_FORMAT) return status;
        if (copy.overflow) return MEDIA_ERR_RANGE;
        if (!copy.have_current || copy.seen < index) return MEDIA_ERR_RANGE;
        *out_length = copy.written;
        return MEDIA_OK;
    }

    if (kind == MEDIA_KIND_SSD) {
        media_entry_t entries[MEDIA_MAX_ENTRIES];
        media_catalogue_t summary;
        media_status_t status;
        const media_entry_t *e;

        status = media_catalogue(image, length, kind, entries,
                                 MEDIA_MAX_ENTRIES, &summary);
        if (status != MEDIA_OK) return status;
        if (index >= summary.count) return MEDIA_ERR_RANGE;
        e = &entries[index];
        if ((size_t)e->offset + e->length > length) return MEDIA_ERR_TRUNCATED;
        if (e->length > out_capacity) return MEDIA_ERR_RANGE;
        memcpy(out, image + e->offset, e->length);
        *out_length = e->length;
        return MEDIA_OK;
    }
    return MEDIA_ERR_FORMAT;
}

static char hex_digit(unsigned value)
{
    return (char)(value < 10u ? '0' + (int)value : 'A' + (int)value - 10);
}

static size_t put_hex(char *out, uint32_t value, unsigned digits)
{
    unsigned i;
    for (i = 0; i < digits; i++) {
        out[i] = hex_digit((value >> ((digits - 1u - i) * 4u)) & 0x0Fu);
    }
    return digits;
}

size_t media_format_entry(const media_entry_t *entry, char *out,
                          size_t capacity)
{
    /* "NAME        FFFF1900 FFFF8023 0004A0 L" fits inside forty columns. */
    size_t n = 0;
    size_t i;

    if (!entry || !out || capacity < 40u) return 0;

    for (i = 0; i < 11u; i++) {
        char ch = entry->name[i];
        if (ch == '\0') break;
        out[n++] = ch;
    }
    while (n < 12u) out[n++] = ' ';

    n += put_hex(out + n, entry->load, 8);
    out[n++] = ' ';
    n += put_hex(out + n, entry->exec, 8);
    out[n++] = ' ';
    n += put_hex(out + n, entry->length, 6);
    if (entry->locked) {
        out[n++] = ' ';
        out[n++] = 'L';
    }
    if (!entry->crc_ok) {
        out[n++] = ' ';
        out[n++] = '?';
    }
    out[n] = '\0';
    return n;
}

/* ------------------------------------------------------------------------ */
/* DFS rendered as a cassette stream                                         */

#define UEF_CHUNK_HEADER 6u
#define CFS_BLOCK_DATA   256u

static size_t emit_bytes(uint8_t *out, size_t capacity, size_t at,
                         const uint8_t *data, size_t count)
{
    if (out != NULL && at + count <= capacity) {
        memcpy(out + at, data, count);
    }
    return at + count;
}

static size_t emit_byte(uint8_t *out, size_t capacity, size_t at, uint8_t value)
{
    return emit_bytes(out, capacity, at, &value, 1u);
}

/* One standard Acorn cassette block wrapped in its own &0100 chunk. */
static size_t emit_block(uint8_t *out, size_t capacity, size_t at,
                         const media_entry_t *entry, uint16_t block_number,
                         const uint8_t *data, size_t data_length, int last)
{
    uint8_t header[32];
    size_t name_length = 0;
    size_t n = 0;
    size_t payload;
    uint16_t crc;
    const char *name = entry->name;

    /* DFS names arrive as "D.NAME". The cassette form carries the leaf only. */
    if (name[0] != '\0' && name[1] == '.') name += 2;
    while (name[name_length] != '\0' && name_length < 10u) name_length++;

    memcpy(header, name, name_length);
    n = name_length;
    header[n++] = 0;
    header[n++] = (uint8_t)(entry->load & 0xFFu);
    header[n++] = (uint8_t)((entry->load >> 8) & 0xFFu);
    header[n++] = (uint8_t)((entry->load >> 16) & 0xFFu);
    header[n++] = (uint8_t)((entry->load >> 24) & 0xFFu);
    header[n++] = (uint8_t)(entry->exec & 0xFFu);
    header[n++] = (uint8_t)((entry->exec >> 8) & 0xFFu);
    header[n++] = (uint8_t)((entry->exec >> 16) & 0xFFu);
    header[n++] = (uint8_t)((entry->exec >> 24) & 0xFFu);
    header[n++] = (uint8_t)(block_number & 0xFFu);
    header[n++] = (uint8_t)(block_number >> 8);
    header[n++] = (uint8_t)(data_length & 0xFFu);
    header[n++] = (uint8_t)(data_length >> 8);
    header[n++] = (uint8_t)(last ? 0x80u : 0x00u);
    header[n++] = 0; header[n++] = 0; header[n++] = 0; header[n++] = 0;

    payload = 1u + n + 2u + data_length + (data_length ? 2u : 0u);

    /* &0100 chunk header, then the block. */
    at = emit_byte(out, capacity, at, 0x00u);
    at = emit_byte(out, capacity, at, 0x01u);
    at = emit_byte(out, capacity, at, (uint8_t)(payload & 0xFFu));
    at = emit_byte(out, capacity, at, (uint8_t)((payload >> 8) & 0xFFu));
    at = emit_byte(out, capacity, at, (uint8_t)((payload >> 16) & 0xFFu));
    at = emit_byte(out, capacity, at, (uint8_t)((payload >> 24) & 0xFFu));

    at = emit_byte(out, capacity, at, 0x2Au);
    at = emit_bytes(out, capacity, at, header, n);
    crc = tape_crc(header, n);
    at = emit_byte(out, capacity, at, (uint8_t)(crc >> 8));
    at = emit_byte(out, capacity, at, (uint8_t)(crc & 0xFFu));
    if (data_length != 0u) {
        at = emit_bytes(out, capacity, at, data, data_length);
        crc = tape_crc(data, data_length);
        at = emit_byte(out, capacity, at, (uint8_t)(crc >> 8));
        at = emit_byte(out, capacity, at, (uint8_t)(crc & 0xFFu));
    }
    return at;
}

static size_t emit_entry(uint8_t *out, size_t capacity, size_t at,
                         const uint8_t *image, size_t length,
                         const media_entry_t *entry)
{
    size_t offset = 0;
    uint16_t block = 0;

    if (entry->length == 0u) {
        return emit_block(out, capacity, at, entry, 0, NULL, 0u, 1);
    }
    while (offset < entry->length) {
        size_t remaining = entry->length - offset;
        size_t take = remaining < CFS_BLOCK_DATA ? remaining : CFS_BLOCK_DATA;
        const uint8_t *data = NULL;
        /* A truncated image yields short blocks rather than reading past it. */
        if ((size_t)entry->offset + offset + take <= length) {
            data = image + entry->offset + offset;
        } else {
            take = 0u;
        }
        at = emit_block(out, capacity, at, entry, block, data, take,
                        offset + take >= entry->length);
        if (take == 0u) break;
        offset += take;
        block++;
    }
    return at;
}

media_status_t media_ssd_to_uef(const uint8_t *image, size_t length,
                                unsigned passes, uint8_t *out,
                                size_t out_capacity, size_t *out_length)
{
    static const uint8_t magic[12] = {
        'U','E','F',' ','F','i','l','e','!', 0, 0, 10
    };
    media_entry_t entries[MEDIA_MAX_ENTRIES];
    media_catalogue_t summary;
    media_status_t status;
    size_t at = 0;
    size_t i;
    unsigned pass;
    size_t boot = (size_t)-1;

    if (image == NULL || out_length == NULL || passes == 0u) {
        return MEDIA_ERR_PARAM;
    }
    status = media_catalogue(image, length, MEDIA_KIND_SSD, entries,
                             MEDIA_MAX_ENTRIES, &summary);
    if (status != MEDIA_OK && status != MEDIA_ERR_TRUNCATED) return status;

    for (i = 0; i < summary.count; i++) {
        const char *name = entries[i].name;
        if (name[0] != '\0' && name[1] == '.') name += 2;
        if (name[0] == '!' && (name[1] == 'B' || name[1] == 'b')) {
            boot = i;
            break;
        }
    }

    at = emit_bytes(out, out_capacity, at, magic, sizeof magic);
    for (pass = 0; pass < passes; pass++) {
        if (boot != (size_t)-1) {
            at = emit_entry(out, out_capacity, at, image, length,
                            &entries[boot]);
        }
        for (i = 0; i < summary.count; i++) {
            if (i == boot) continue;
            at = emit_entry(out, out_capacity, at, image, length, &entries[i]);
        }
    }
    *out_length = at;
    if (out != NULL && at > out_capacity) return MEDIA_ERR_RANGE;
    return MEDIA_OK;
}
