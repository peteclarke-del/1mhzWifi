#include "pi1mhz_mailbox.h"

#include <stdlib.h>
#include <string.h>

#define PI1MHZ_JIM_SET_SIZE (1u << 24)

static size_t page_window_address(const pi1mhz_mailbox *mailbox,
                                  uint16_t address)
{
    size_t set = (size_t)(mailbox->page >> 16) * PI1MHZ_JIM_SET_SIZE;

    /* Pi1MHz clamps an unavailable FCFD set selector to the final
       installed 16 MiB JIM set. A one-set configuration therefore aliases
       every FCFD value to set zero while preserving selector readback. */
    if (set >= mailbox->jim_size)
        set = ((mailbox->jim_size - 1u) / PI1MHZ_JIM_SET_SIZE) *
              PI1MHZ_JIM_SET_SIZE;
    return set + ((size_t)(mailbox->page & 0xFFFFu) << 8) +
           (address & 0xFFu);
}

int pi1mhz_mailbox_init(pi1mhz_mailbox *mailbox,
                        pi1mhz_dispatch_fn dispatch, void *opaque)
{
    if (!mailbox || !dispatch)
        return -1;
    memset(mailbox, 0, sizeof(*mailbox));
    mailbox->jim = (uint8_t *)calloc(PI1MHZ_JIM_SIZE, 1);
    if (!mailbox->jim)
        return -1;
    mailbox->jim_size = PI1MHZ_JIM_SIZE;
    mailbox->dispatch = dispatch;
    mailbox->dispatch_opaque = opaque;
    return 0;
}

void pi1mhz_mailbox_destroy(pi1mhz_mailbox *mailbox)
{
    if (!mailbox)
        return;
    free(mailbox->jim);
    memset(mailbox, 0, sizeof(*mailbox));
}

int pi1mhz_mailbox_handles(uint16_t address)
{
    return (address >= PI1MHZ_REG_ADDR_LO &&
            address <= PI1MHZ_REG_COMMAND) ||
           (address >= PI1MHZ_REG_PAGE_HI &&
            address <= PI1MHZ_REG_PAGE_LO) ||
           (address >= PI1MHZ_PAGE_BASE && address <= PI1MHZ_PAGE_END);
}

int pi1mhz_mailbox_ap5_handles(uint16_t address)
{
    /* ACP/Pres decoded only &FCFF from the JIM selector group onto the AP5
       1MHz connector. A direct BBC connection can expose all three selectors,
       which is why this is a separate bus-profile predicate. */
    if (address == PI1MHZ_REG_PAGE_HI || address == PI1MHZ_REG_PAGE_MID)
        return 0;
    return pi1mhz_mailbox_handles(address);
}

uint8_t pi1mhz_mailbox_read(pi1mhz_mailbox *mailbox, uint16_t address)
{
    uint8_t value;
    if (!mailbox || !mailbox->jim)
        return 0xFFu;
    if (address >= PI1MHZ_PAGE_BASE && address <= PI1MHZ_PAGE_END) {
        size_t jim_address = page_window_address(mailbox, address);
        return jim_address < mailbox->jim_size
                   ? mailbox->jim[jim_address] : 0xFFu;
    }
    switch (address) {
    case PI1MHZ_REG_ADDR_LO:  return (uint8_t)mailbox->address;
    case PI1MHZ_REG_ADDR_MID: return (uint8_t)(mailbox->address >> 8);
    case PI1MHZ_REG_ADDR_HI:  return (uint8_t)(mailbox->address >> 16);
    case PI1MHZ_REG_DATA:
        value = mailbox->jim[mailbox->address];
        mailbox->address = (mailbox->address + 1u) & 0xFFFFFFu;
        return value;
    case PI1MHZ_REG_COMMAND:
        /* Return BUSY once, then perform the deferred poll. This preserves
           the real FIQ-latch/main-loop ordering without coupling the reusable
           device to an emulator's scheduler. */
        value = mailbox->result;
        if (mailbox->pending) {
            uint32_t cp = 0xFF0000u | ((uint32_t)mailbox->selector << 8);
            mailbox->pending = 0;
            mailbox->result = mailbox->dispatch(
                mailbox->dispatch_opaque, mailbox->selector, cp,
                mailbox->jim, mailbox->jim_size);
        }
        return value;
    case PI1MHZ_REG_PAGE_HI:  return (uint8_t)(mailbox->page >> 16);
    case PI1MHZ_REG_PAGE_MID: return (uint8_t)(mailbox->page >> 8);
    case PI1MHZ_REG_PAGE_LO:  return (uint8_t)mailbox->page;
    default:
        return 0xFFu;
    }
}

void pi1mhz_mailbox_write(pi1mhz_mailbox *mailbox, uint16_t address,
                          uint8_t value)
{
    if (!mailbox || !mailbox->jim)
        return;
    if (address >= PI1MHZ_PAGE_BASE && address <= PI1MHZ_PAGE_END) {
        size_t jim_address = page_window_address(mailbox, address);
        if (jim_address < mailbox->jim_size)
            mailbox->jim[jim_address] = value;
        return;
    }
    switch (address) {
    case PI1MHZ_REG_ADDR_LO:
        mailbox->address = (mailbox->address & 0xFFFF00u) | value;
        break;
    case PI1MHZ_REG_ADDR_MID:
        mailbox->address = (mailbox->address & 0xFF00FFu) |
                           ((uint32_t)value << 8);
        break;
    case PI1MHZ_REG_ADDR_HI:
        mailbox->address = (mailbox->address & 0x00FFFFu) |
                           ((uint32_t)value << 16);
        break;
    case PI1MHZ_REG_DATA:
        mailbox->jim[mailbox->address] = value;
        mailbox->address = (mailbox->address + 1u) & 0xFFFFFFu;
        break;
    case PI1MHZ_REG_COMMAND:
        if (value >= 0xF0u) {
            mailbox->selector = value;
            mailbox->result = PI1MHZ_NET_BUSY;
            mailbox->pending = 1;
        } else {
            mailbox->result = value;
        }
        break;
    case PI1MHZ_REG_PAGE_HI:
        mailbox->page = (mailbox->page & 0x00FFFFu) |
                        ((uint32_t)value << 16);
        break;
    case PI1MHZ_REG_PAGE_MID:
        mailbox->page = (mailbox->page & 0xFF00FFu) |
                        ((uint32_t)value << 8);
        break;
    case PI1MHZ_REG_PAGE_LO:
        mailbox->page = (mailbox->page & 0xFFFF00u) | value;
        break;
    default:
        break;
    }
}
