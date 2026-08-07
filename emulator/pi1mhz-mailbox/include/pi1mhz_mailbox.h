#ifndef PI1MHZ_MAILBOX_H
#define PI1MHZ_MAILBOX_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PI1MHZ_JIM_SIZE       (1u << 24)
#define PI1MHZ_REG_ADDR_LO    0xFCA6u
#define PI1MHZ_REG_ADDR_MID   0xFCA7u
#define PI1MHZ_REG_ADDR_HI    0xFCA8u
#define PI1MHZ_REG_DATA       0xFCA9u
#define PI1MHZ_REG_COMMAND    0xFCAAu
#define PI1MHZ_REG_PAGE_HI    0xFCFDu
#define PI1MHZ_REG_PAGE_MID   0xFCFEu
#define PI1MHZ_REG_PAGE_LO    0xFCFFu
#define PI1MHZ_PAGE_BASE      0xFD00u
#define PI1MHZ_PAGE_END       0xFDFFu

#define PI1MHZ_NET_OK          0x00u
#define PI1MHZ_NET_PENDING     0x01u
#define PI1MHZ_NET_EOF         0x20u
#define PI1MHZ_NET_UNSUPPORTED 0x27u
#define PI1MHZ_NET_BUSY        0x80u

typedef uint8_t (*pi1mhz_dispatch_fn)(void *opaque, uint8_t selector,
                                      uint32_t command_pointer,
                                      uint8_t *jim, size_t jim_size);

typedef struct pi1mhz_mailbox {
    uint8_t *jim;
    size_t jim_size;
    uint32_t address;
    uint32_t page;
    uint8_t result;
    uint8_t selector;
    int pending;
    pi1mhz_dispatch_fn dispatch;
    void *dispatch_opaque;
} pi1mhz_mailbox;

int pi1mhz_mailbox_init(pi1mhz_mailbox *mailbox,
                        pi1mhz_dispatch_fn dispatch, void *opaque);
void pi1mhz_mailbox_destroy(pi1mhz_mailbox *mailbox);
int pi1mhz_mailbox_handles(uint16_t address);
int pi1mhz_mailbox_ap5_handles(uint16_t address);
uint8_t pi1mhz_mailbox_read(pi1mhz_mailbox *mailbox, uint16_t address);
void pi1mhz_mailbox_write(pi1mhz_mailbox *mailbox, uint16_t address,
                          uint8_t value);

#ifdef __cplusplus
}
#endif

#endif
