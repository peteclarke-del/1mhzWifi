#ifndef MEDIA_CATALOGUE_H
#define MEDIA_CATALOGUE_H

#include <stddef.h>
#include <stdint.h>

/* Container parsing for the host `*UEF CAT`, `*UEF EXTRACT`, `*SSD CAT` and
 * `*SSD EXTRACT` commands.
 *
 * The host ROM stays a thin client: it supplies a complete container image and
 * renders whatever this module reports. Every catalogue and metadata decision
 * for UEF cassette streams and DFS disc images is made here, on the Pi, where
 * there is room to validate it. Nothing in this file touches Pi1MHz hardware,
 * so it is unit tested on the build host.
 *
 * All entry points treat the image as untrusted input. A truncated or
 * malformed container yields the entries that could be recovered plus a
 * non-zero issue count; it never reads outside the supplied buffer. */

#define MEDIA_NAME_MAX      16u
#define MEDIA_TITLE_MAX     16u
#define MEDIA_MAX_ENTRIES   128u

typedef enum {
    MEDIA_KIND_UNKNOWN = 0,
    MEDIA_KIND_UEF,
    MEDIA_KIND_SSD
} media_kind_t;

typedef enum {
    MEDIA_OK = 0,
    MEDIA_ERR_PARAM,
    MEDIA_ERR_FORMAT,
    MEDIA_ERR_RANGE,
    MEDIA_ERR_TRUNCATED
} media_status_t;

typedef struct {
    char     name[MEDIA_NAME_MAX];  /* NUL terminated; DFS entries are "D.NAME" */
    uint32_t load;                  /* full 32-bit address as recorded */
    uint32_t exec;
    uint32_t length;                /* total data bytes for the file */
    uint32_t offset;                /* byte offset of contiguous data, SSD only */
    uint16_t blocks;                /* CFS blocks that make up a UEF file */
    uint8_t  locked;                /* CFS/DFS lock attribute */
    uint8_t  crc_ok;                /* UEF: every block header and data CRC verified */
} media_entry_t;

typedef struct {
    char        title[MEDIA_TITLE_MAX]; /* DFS disc title; empty for UEF */
    media_kind_t kind;
    size_t      count;                  /* entries written to the caller array */
    size_t      total;                  /* entries present, may exceed `count` */
    uint32_t    issues;                 /* recoverable defects seen while parsing */
    uint8_t     boot_option;            /* DFS *OPT 4 value; 0 for UEF */
} media_catalogue_t;

/* Identify a container from its leading bytes and length. A UEF must carry the
 * "UEF File!" magic; anything else that is a whole number of 256-byte sectors
 * and holds a plausible DFS catalogue is reported as SSD. */
media_kind_t media_identify(const uint8_t *image, size_t length);

/* Decode the catalogue. `entries` may be NULL to count only. */
media_status_t media_catalogue(const uint8_t *image, size_t length,
                               media_kind_t kind, media_entry_t *entries,
                               size_t max_entries, media_catalogue_t *summary);

/* Copy entry `index`'s file data into `out`. UEF data is gathered from its CFS
 * blocks; DFS data is contiguous. `*out_length` receives the byte count. */
media_status_t media_extract(const uint8_t *image, size_t length,
                             media_kind_t kind, size_t index, uint8_t *out,
                             size_t out_capacity, size_t *out_length);

/* Render one catalogue line in the host's 40-column form. Returns the number of
 * characters written excluding the terminator, or 0 if the buffer is too
 * small. */
size_t media_format_entry(const media_entry_t *entry, char *out,
                          size_t capacity);

/* Redirect the published Electron loader idiom which stamps the FILEV vector
 * blind. A large minority of titles contain `?&212=&D6:?&213=&F1`, which
 * overwrites whatever filing system owns the vector - including WiCFS - with
 * the Electron MOS 1.00 cassette entry. Rewriting the address token to
 * &900/&901 leaves the program the same length, so block layout and every
 * stored offset are untouched and only the affected block's data CRC is
 * recomputed. Returns the number of address tokens redirected.
 *
 * This lives beside the container decoder rather than in uef_normalize.c so
 * the Pi and the emulator run the same code instead of two copies. */
unsigned uef_repair_filev_stamp(uint8_t *window, size_t length);

#endif
