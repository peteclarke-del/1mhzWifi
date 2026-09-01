#ifndef UEF_NORMALIZE_H
#define UEF_NORMALIZE_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
   UEF_NORMALIZE_RAW = 0,
   UEF_NORMALIZE_GZIP,
   UEF_NORMALIZE_ZIP,
   UEF_NORMALIZE_INVALID,
   UEF_NORMALIZE_TOO_LARGE
} uef_normalize_result_t;

uef_normalize_result_t uef_normalize(uint8_t *window, size_t *length,
                                     size_t capacity, uint8_t *scratch,
                                     size_t scratch_size);

/* Reproduce the pre-candidate experiment which stopped after the last
 * complete &0100 chunk. Normal compatibility mode does not call this helper. */
size_t uef_legacy_trim_length(const uint8_t *window, size_t length);

/* Redirect the published Electron loader idiom which stamps the FILEV vector
 * blind. A large minority of titles contain `?&212=&D6:?&213=&F1`, which
 * overwrites whatever filing system owns the vector - including WiCFS - with
 * the Electron MOS 1.00 cassette entry, sending the loader's next CHAIN"" to
 * real cassette code. Rewriting the address token to &900/&901 leaves the
 * program syntactically identical and the same length, so block layout and
 * every stored offset are untouched; only the affected block's data CRC is
 * recomputed. &900 is inside the &0900-&10FF range cassette loaders already
 * overwrite, so the redirected pokes land on scratch.
 * Returns the number of address tokens redirected. */
unsigned uef_repair_filev_stamp(uint8_t *window, size_t length);

#endif
