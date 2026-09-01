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

static uint16_t tape_crc(const uint8_t *data, size_t length)
{
   uint16_t crc = 0u;
   while (length-- != 0u) {
      crc ^= (uint16_t)((uint16_t)*data++ << 8);
      for (unsigned int bit = 0; bit < 8u; bit++)
         crc = (crc & 0x8000u) ? (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u)
                               : (uint16_t)(crc << 1);
   }
   return crc;
}

static bool hex_digit(uint8_t c)
{
   return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F')
       || (c >= 'a' && c <= 'f');
}

/* Rewrite `&212`/`&213` address tokens in one block's payload. BBC BASIC
 * tokenises keywords but leaves `&` and digits as ASCII, so the address
 * survives verbatim and a three-digit substitution is exact. A following hex
 * digit means the token is really a longer address such as &2120, which must
 * be left alone. Both `?` and `!` forms are redirected: a loader which saves
 * and restores the vector then does both through scratch and leaves ours
 * untouched. */
static unsigned repair_block_payload(uint8_t *data, size_t length)
{
   unsigned repaired = 0u;
   if (length < 4u) return 0u;
   for (size_t at = 0u; at + 4u <= length; at++) {
      if (data[at] != '&' || data[at + 1] != '2' || data[at + 2] != '1')
         continue;
      if (data[at + 3] != '2' && data[at + 3] != '3')
         continue;
      if (at + 4u < length && hex_digit(data[at + 4]))
         continue;
      if (at == 0u || (data[at - 1] != '?' && data[at - 1] != '!'))
         continue;
      data[at + 1] = '9';
      data[at + 2] = '0';
      data[at + 3] = (data[at + 3] == '2') ? '0' : '1';
      repaired++;
   }
   return repaired;
}

unsigned uef_repair_filev_stamp(uint8_t *window, size_t length)
{
   size_t position = 12u;
   unsigned repaired = 0u;
   if (window == NULL || length < position) return 0u;
   while (position + 6u <= length) {
      uint16_t chunk = le16(&window[position]);
      uint32_t chunk_length = le32(&window[position + 2]);
      size_t start = position + 6u;
      if (chunk_length > length || start + chunk_length > length)
         break;
      if (chunk == 0x0100u && chunk_length > 1u
          && window[start] == (uint8_t)'*') {
         /* Standard cassette block: '*', NUL-terminated name of 1 to 10
          * characters, 17-byte descriptor, header CRC, payload, payload CRC. */
         size_t name_end = start + 1u;
         size_t limit = start + chunk_length;
         while (name_end < limit && name_end - start <= 11u
                && window[name_end] != 0u)
            name_end++;
         if (name_end < limit && window[name_end] == 0u) {
            size_t descriptor = name_end + 1u;
            size_t header_crc = descriptor + 17u;
            size_t data_at = header_crc + 2u;
            if (data_at <= limit && descriptor + 13u <= limit) {
               uint16_t data_length = le16(&window[descriptor + 10]);
               size_t data_crc = data_at + data_length;
               /* A zero-length catalogue marker carries no payload CRC. */
               if (data_length != 0u && data_crc + 2u <= limit) {
                  unsigned hits = repair_block_payload(&window[data_at],
                                                       data_length);
                  if (hits != 0u) {
                     uint16_t crc = tape_crc(&window[data_at], data_length);
                     window[data_crc] = (uint8_t)(crc >> 8);
                     window[data_crc + 1u] = (uint8_t)(crc & 0xffu);
                     repaired += hits;
                  }
               }
            }
         }
      }
      position = start + chunk_length;
   }
   return repaired;
}

size_t uef_legacy_trim_length(const uint8_t *window, size_t length)
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
