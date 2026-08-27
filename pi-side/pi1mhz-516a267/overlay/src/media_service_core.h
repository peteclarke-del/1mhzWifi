#ifndef MEDIA_SERVICE_CORE_H
#define MEDIA_SERVICE_CORE_H

#include <stddef.h>
#include <stdint.h>

#include "media_catalogue.h"

/* Mailbox session for the host `*UEF CAT`, `*UEF EXTRACT`, `*SSD CAT` and
 * `*SSD EXTRACT` commands.
 *
 * The host ROM stays a thin client. It uploads a container image, then asks
 * for catalogue lines, entry metadata and file data one bounded reply at a
 * time. Every parsing decision is made by media_catalogue.c and every session
 * decision is made here, so neither costs host ROM space.
 *
 * This core performs no Pi1MHz register access. media_service.c binds it to
 * the services mailbox, and the unit tests drive it directly. */

enum {
    MEDIA_CMD_OPEN  = 120,   /* identify the uploaded image, return kind/count */
    MEDIA_CMD_CAT   = 121,   /* return one catalogue line, advancing a cursor  */
    MEDIA_CMD_INFO  = 122,   /* return one entry's metadata by index           */
    MEDIA_CMD_READ  = 123,   /* stream one entry's data in bounded windows     */
    MEDIA_CMD_CLOSE = 124,   /* release the session                            */

    MEDIA_SVC_OK        = 0x00,
    MEDIA_SVC_EOF       = 0x20,
    MEDIA_SVC_ERR_PARAM = 0x23,
    MEDIA_SVC_ERR_FORMAT = 0x27,
    MEDIA_SVC_ERR_RANGE = 0x2B
};

/* A reply never exceeds the stock 240-byte services response window. */
#define MEDIA_SVC_REPLY_MAX 240u

typedef struct media_service {
    const uint8_t *image;      /* container supplied by the host, not owned */
    size_t         length;
    media_kind_t   kind;
    media_catalogue_t summary;
    media_entry_t  entries[MEDIA_MAX_ENTRIES];
    size_t         cat_cursor;  /* next catalogue line to return */
    size_t         read_index;  /* entry currently being streamed */
    size_t         read_offset; /* byte offset reached within that entry */
    int            open;
} media_service;

/* Reset a session. Does not free the caller's image. */
void media_service_reset(media_service *service);

/* Bind an uploaded container and decode its catalogue. */
uint8_t media_service_open(media_service *service, const uint8_t *image,
                           size_t length);

/* Dispatch one mailbox command.
 *
 * `command` is the four-byte services command block: command number followed
 * by up to three argument bytes. `reply` receives the response body and
 * `*reply_length` its size, never exceeding MEDIA_SVC_REPLY_MAX. The returned
 * byte is the status the host reads back. */
uint8_t media_service_dispatch(media_service *service, const uint8_t *command,
                               uint8_t *reply, size_t reply_capacity,
                               size_t *reply_length);

#endif
