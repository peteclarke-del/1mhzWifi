#include "uef_normalize.h"

#include <stdbool.h>
#include <string.h>

#include "puff.h"

static const uint8_t uef_magic[] = {'U', 'E', 'F', ' ', 'F', 'i', 'l', 'e', '!', 0};

static uint16_t le16(const uint8_t *p)
{
   return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));
}

static uint32_t le32(const uint8_t *p)
{
   return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
        | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint32_t crc32_bytes(const uint8_t *data, size_t length)
{
   uint32_t crc = 0xffffffffu;
   while (length-- != 0u) {
      crc ^= *data++;
      for (unsigned int bit = 0; bit < 8u; bit++)
         crc = (crc >> 1) ^ (0xedb88320u & (uint32_t)-(int32_t)(crc & 1u));
   }
   return ~crc;
}

static bool raw_uef(const uint8_t *data, size_t length)
{
   return length >= sizeof uef_magic
       && memcmp(data, uef_magic, sizeof uef_magic) == 0;
}

size_t uef_wicfs_stream_length(const uint8_t *window, size_t length)
{
   size_t position = 12u;
   size_t effective = length;
   bool saw_data = false;

   if (!raw_uef(window, length) || length < position)
      return length;
   while (position < length) {
      size_t chunk_length;
      uint16_t chunk_type;
      if (length - position < 6u)
         return length;
      chunk_type = le16(window + position);
      chunk_length = (size_t)le32(window + position + 2u);
      position += 6u;
      if (chunk_length > length - position)
         return length;
      position += chunk_length;
      if (chunk_type == 0x0100u) {
         effective = position;
         saw_data = true;
      }
   }
   return saw_data ? effective : length;
}

static bool skip_zero_string(const uint8_t *source, size_t limit, size_t *pos)
{
   while (*pos < limit && source[(*pos)++] != 0u) {}
   return *pos <= limit && *pos != 0u && source[*pos - 1u] == 0u;
}

static bool zip_has_one_entry(const uint8_t *source, size_t length)
{
   size_t pos;
   if (length < 22u)
      return false;
   pos = length - 22u;
   for (;;) {
      if (le32(source + pos) == 0x06054b50u
          && le16(source + pos + 4u) == 0u
          && le16(source + pos + 6u) == 0u
          && le16(source + pos + 8u) == 1u
          && le16(source + pos + 10u) == 1u
          && (size_t)le16(source + pos + 20u) == length - pos - 22u)
         return true;
      if (pos == 0u)
         return false;
      pos--;
   }
}

static uef_normalize_result_t inflate_deflate(uint8_t *window, size_t *length,
                                              size_t capacity,
                                              const uint8_t *source,
                                              size_t source_length)
{
   unsigned long output_length = (unsigned long)capacity;
   unsigned long input_length = (unsigned long)source_length;
   int result = puff(window, &output_length, source, &input_length);
   if (result == 1)
      return UEF_NORMALIZE_TOO_LARGE;
   if (result != 0 || input_length > source_length)
      return UEF_NORMALIZE_INVALID;
   *length = (size_t)output_length;
   return UEF_NORMALIZE_RAW;
}

static uef_normalize_result_t normalize_gzip(uint8_t *window, size_t *length,
                                             size_t capacity,
                                             const uint8_t *source,
                                             size_t source_length)
{
   size_t pos = 10u;
   uint8_t flags;
   uef_normalize_result_t result;
   if (source_length < 18u || source[2] != 8u || (source[3] & 0xe0u) != 0u)
      return UEF_NORMALIZE_INVALID;
   flags = source[3];
   if ((flags & 4u) != 0u) {
      size_t extra;
      if (pos + 2u > source_length - 8u)
         return UEF_NORMALIZE_INVALID;
      extra = le16(source + pos);
      pos += 2u;
      if (extra > source_length - 8u - pos)
         return UEF_NORMALIZE_INVALID;
      pos += extra;
   }
   if ((flags & 8u) != 0u && !skip_zero_string(source, source_length - 8u, &pos))
      return UEF_NORMALIZE_INVALID;
   if ((flags & 16u) != 0u && !skip_zero_string(source, source_length - 8u, &pos))
      return UEF_NORMALIZE_INVALID;
   if ((flags & 2u) != 0u) {
      if (pos + 2u > source_length - 8u)
         return UEF_NORMALIZE_INVALID;
      pos += 2u;
   }
   if (pos >= source_length - 8u)
      return UEF_NORMALIZE_INVALID;
   result = inflate_deflate(window, length, capacity, source + pos,
                            source_length - 8u - pos);
   if (result != UEF_NORMALIZE_RAW || !raw_uef(window, *length))
      return result;
   if (*length != le32(source + source_length - 4u)
       || crc32_bytes(window, *length) != le32(source + source_length - 8u))
      return UEF_NORMALIZE_INVALID;
   return UEF_NORMALIZE_GZIP;
}

static uef_normalize_result_t normalize_zip(uint8_t *window, size_t *length,
                                            size_t capacity,
                                            uint8_t *source,
                                            size_t source_length)
{
   uint16_t flags, method, name_length, extra_length;
   uint32_t expected_crc, compressed_length, output_length;
   size_t data;
   uef_normalize_result_t result;
   if (source_length < 30u || le32(source) != 0x04034b50u
       || !zip_has_one_entry(source, source_length))
      return UEF_NORMALIZE_INVALID;
   flags = le16(source + 6u);
   method = le16(source + 8u);
   expected_crc = le32(source + 14u);
   compressed_length = le32(source + 18u);
   output_length = le32(source + 22u);
   name_length = le16(source + 26u);
   extra_length = le16(source + 28u);
   if ((flags & 9u) != 0u || (method != 0u && method != 8u)
       || output_length > capacity)
      return output_length > capacity ? UEF_NORMALIZE_TOO_LARGE
                                      : UEF_NORMALIZE_INVALID;
   data = 30u + (size_t)name_length + (size_t)extra_length;
   if (data > source_length || compressed_length > source_length - data)
      return UEF_NORMALIZE_INVALID;
   if (method == 0u) {
      if (compressed_length != output_length)
         return UEF_NORMALIZE_INVALID;
      memmove(window, source + data, output_length);
      *length = output_length;
      result = UEF_NORMALIZE_RAW;
   } else {
      result = inflate_deflate(window, length, capacity, source + data,
                               compressed_length);
   }
   if (result != UEF_NORMALIZE_RAW || *length != output_length
       || crc32_bytes(window, *length) != expected_crc)
      return UEF_NORMALIZE_INVALID;
   if (!raw_uef(window, *length)) {
      uef_normalize_result_t inner;
      if (*length < 2u || window[0] != 0x1fu || window[1] != 0x8bu)
         return UEF_NORMALIZE_INVALID;
      memcpy(source, window, *length);
      inner = normalize_gzip(window, length, capacity, source, *length);
      if (inner != UEF_NORMALIZE_GZIP)
         return inner;
   }
   return UEF_NORMALIZE_ZIP;
}

uef_normalize_result_t uef_normalize(uint8_t *window, size_t *length,
                                     size_t capacity, uint8_t *scratch,
                                     size_t scratch_size)
{
   size_t input_length;
   if (window == NULL || length == NULL || scratch == NULL)
      return UEF_NORMALIZE_INVALID;
   input_length = *length;
   if (input_length == 0u || input_length > capacity || input_length > scratch_size)
      return input_length > capacity ? UEF_NORMALIZE_TOO_LARGE
                                     : UEF_NORMALIZE_INVALID;
   if (raw_uef(window, input_length))
      return UEF_NORMALIZE_RAW;
   memcpy(scratch, window, input_length);
   if (input_length >= 2u && scratch[0] == 0x1fu && scratch[1] == 0x8bu)
      return normalize_gzip(window, length, capacity, scratch, input_length);
   if (input_length >= 4u && le32(scratch) == 0x04034b50u)
      return normalize_zip(window, length, capacity, scratch, input_length);
   return UEF_NORMALIZE_INVALID;
}
