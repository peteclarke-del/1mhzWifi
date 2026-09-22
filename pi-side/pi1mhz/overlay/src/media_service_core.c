#include "media_service_core.h"

#include <string.h>

/* The read window is the reply window less the four-byte header the host
 * expects: remaining length high/low and the byte count in this window. */
#define MEDIA_SVC_READ_WINDOW (MEDIA_SVC_REPLY_MAX - 4u)

void media_service_reset(media_service *service)
{
    if (!service) return;
    memset(service, 0, sizeof(*service));
}

uint8_t media_service_open(media_service *service, const uint8_t *image,
                           size_t length)
{
    media_status_t status;

    if (!service) return MEDIA_SVC_ERR_PARAM;
    media_service_reset(service);
    if (!image || length == 0) return MEDIA_SVC_ERR_PARAM;

    service->kind = media_identify(image, length);
    if (service->kind == MEDIA_KIND_UNKNOWN) return MEDIA_SVC_ERR_FORMAT;

    status = media_catalogue(image, length, service->kind, service->entries,
                             MEDIA_MAX_ENTRIES, &service->summary);
    if (status != MEDIA_OK) return MEDIA_SVC_ERR_FORMAT;

    service->image = image;
    service->length = length;
    service->open = 1;
    return MEDIA_SVC_OK;
}

static uint8_t dispatch_open(media_service *service, uint8_t *reply,
                             size_t capacity, size_t *reply_length)
{
    /* The host uploads the image separately and opens it with a bare command,
     * so an open here only reports what the already-bound image contains. */
    if (!service->open) return MEDIA_SVC_ERR_PARAM;
    if (capacity < 4u) return MEDIA_SVC_ERR_RANGE;
    reply[0] = (uint8_t)service->kind;
    reply[1] = (uint8_t)(service->summary.count & 0xFFu);
    reply[2] = (uint8_t)(service->summary.total & 0xFFu);
    reply[3] = service->summary.boot_option;
    *reply_length = 4u;
    return MEDIA_SVC_OK;
}

static uint8_t dispatch_cat(media_service *service, uint8_t *reply,
                            size_t capacity, size_t *reply_length)
{
    char line[64];
    size_t n;

    if (!service->open) return MEDIA_SVC_ERR_PARAM;
    if (service->cat_cursor >= service->summary.count) return MEDIA_SVC_EOF;

    n = media_format_entry(&service->entries[service->cat_cursor], line,
                           sizeof(line));
    if (n == 0) return MEDIA_SVC_ERR_RANGE;
    if (n + 1u > capacity || n + 1u > MEDIA_SVC_REPLY_MAX) {
        return MEDIA_SVC_ERR_RANGE;
    }
    memcpy(reply, line, n);
    reply[n] = 0x0Du;              /* host prints a CR-terminated line */
    *reply_length = n + 1u;
    service->cat_cursor++;
    return MEDIA_SVC_OK;
}

static uint8_t dispatch_info(media_service *service, const uint8_t *command,
                             uint8_t *reply, size_t capacity,
                             size_t *reply_length)
{
    size_t index;
    const media_entry_t *entry;
    size_t n = 0;
    size_t i;

    if (!service->open) return MEDIA_SVC_ERR_PARAM;
    index = command[1];
    if (index >= service->summary.count) return MEDIA_SVC_ERR_RANGE;
    entry = &service->entries[index];

    /* load(4) exec(4) length(4) flags(1) then the NUL terminated name. */
    if (capacity < 13u + MEDIA_NAME_MAX) return MEDIA_SVC_ERR_RANGE;
    reply[n++] = (uint8_t)(entry->load & 0xFFu);
    reply[n++] = (uint8_t)((entry->load >> 8) & 0xFFu);
    reply[n++] = (uint8_t)((entry->load >> 16) & 0xFFu);
    reply[n++] = (uint8_t)((entry->load >> 24) & 0xFFu);
    reply[n++] = (uint8_t)(entry->exec & 0xFFu);
    reply[n++] = (uint8_t)((entry->exec >> 8) & 0xFFu);
    reply[n++] = (uint8_t)((entry->exec >> 16) & 0xFFu);
    reply[n++] = (uint8_t)((entry->exec >> 24) & 0xFFu);
    reply[n++] = (uint8_t)(entry->length & 0xFFu);
    reply[n++] = (uint8_t)((entry->length >> 8) & 0xFFu);
    reply[n++] = (uint8_t)((entry->length >> 16) & 0xFFu);
    reply[n++] = (uint8_t)((entry->length >> 24) & 0xFFu);
    reply[n++] = (uint8_t)((entry->locked ? 1u : 0u) |
                           (entry->crc_ok ? 0u : 2u));
    for (i = 0; i < MEDIA_NAME_MAX && entry->name[i]; i++) {
        reply[n++] = (uint8_t)entry->name[i];
    }
    reply[n++] = 0;
    *reply_length = n;
    return MEDIA_SVC_OK;
}

/* Extracted file data for the entry currently being streamed. Extraction
 * gathers a UEF file from its CFS blocks, so it is done once when a stream
 * starts rather than on every window. */
static uint8_t  stream_data[65536];
static size_t   stream_length;
static size_t   stream_index;
static int      stream_valid;

static uint8_t dispatch_read(media_service *service, const uint8_t *command,
                             uint8_t *reply, size_t capacity,
                             size_t *reply_length)
{
    size_t index;
    size_t remaining;
    size_t window;

    if (!service->open) return MEDIA_SVC_ERR_PARAM;
    index = command[1];
    if (index >= service->summary.count) return MEDIA_SVC_ERR_RANGE;
    if (capacity < 4u) return MEDIA_SVC_ERR_RANGE;

    /* A different index, or no live stream, starts a new one. */
    if (!stream_valid || stream_index != index ||
        service->read_index != index) {
        media_status_t status = media_extract(service->image, service->length,
                                              service->kind, index,
                                              stream_data,
                                              sizeof(stream_data),
                                              &stream_length);
        if (status == MEDIA_ERR_RANGE) return MEDIA_SVC_ERR_RANGE;
        if (status != MEDIA_OK) return MEDIA_SVC_ERR_FORMAT;
        stream_index = index;
        stream_valid = 1;
        service->read_index = index;
        service->read_offset = 0;
    }

    if (service->read_offset >= stream_length) {
        service->read_offset = 0;
        stream_valid = 0;
        *reply_length = 0;
        return MEDIA_SVC_EOF;
    }

    remaining = stream_length - service->read_offset;
    window = remaining < MEDIA_SVC_READ_WINDOW ? remaining
                                               : MEDIA_SVC_READ_WINDOW;
    if (window + 4u > capacity) window = capacity - 4u;

    /* Three little-endian bytes of remaining length, then this window's size,
     * matching the byte order the host already uses for stream lengths. */
    reply[0] = (uint8_t)(remaining & 0xFFu);
    reply[1] = (uint8_t)((remaining >> 8) & 0xFFu);
    reply[2] = (uint8_t)((remaining >> 16) & 0xFFu);
    reply[3] = (uint8_t)window;
    memcpy(reply + 4, stream_data + service->read_offset, window);
    service->read_offset += window;
    *reply_length = window + 4u;
    return MEDIA_SVC_OK;
}

uint8_t media_service_dispatch(media_service *service, const uint8_t *command,
                               uint8_t *reply, size_t reply_capacity,
                               size_t *reply_length)
{
    size_t local_length = 0;

    if (!service || !command || !reply || !reply_length) {
        return MEDIA_SVC_ERR_PARAM;
    }
    *reply_length = 0;
    if (reply_capacity > MEDIA_SVC_REPLY_MAX) {
        reply_capacity = MEDIA_SVC_REPLY_MAX;
    }

    switch (command[0]) {
    case MEDIA_CMD_OPEN:
        return dispatch_open(service, reply, reply_capacity, reply_length);
    case MEDIA_CMD_CAT:
        return dispatch_cat(service, reply, reply_capacity, reply_length);
    case MEDIA_CMD_INFO:
        return dispatch_info(service, command, reply, reply_capacity,
                             reply_length);
    case MEDIA_CMD_READ:
        return dispatch_read(service, command, reply, reply_capacity,
                             reply_length);
    case MEDIA_CMD_CLOSE:
        stream_valid = 0;
        media_service_reset(service);
        *reply_length = local_length;
        return MEDIA_SVC_OK;
    default:
        return MEDIA_SVC_ERR_PARAM;
    }
}
