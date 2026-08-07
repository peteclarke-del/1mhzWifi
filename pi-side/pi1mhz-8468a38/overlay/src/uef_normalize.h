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

#endif
