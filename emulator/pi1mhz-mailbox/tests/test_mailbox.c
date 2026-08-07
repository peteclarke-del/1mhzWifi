#include "pi1mhz_mailbox.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

typedef struct dispatch_capture {
    uint8_t selector;
    uint32_t command_pointer;
    unsigned calls;
} dispatch_capture;

static uint8_t dispatch(void *opaque, uint8_t selector,
                        uint32_t command_pointer, uint8_t *jim,
                        size_t jim_size)
{
    dispatch_capture *capture = (dispatch_capture *)opaque;
    (void)jim;
    assert(jim_size == PI1MHZ_JIM_SIZE);
    capture->selector = selector;
    capture->command_pointer = command_pointer;
    capture->calls++;
    return 0x42;
}

int main(void)
{
    pi1mhz_mailbox mailbox;
    dispatch_capture capture = { 0, 0, 0 };

    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));

    /* The direct Pi1MHz core exposes all Rampage selectors. The Electron AP5
       bus profile forwards only FCFF and JIM, matching the physical decoder. */
    assert(pi1mhz_mailbox_handles(PI1MHZ_REG_PAGE_HI));
    assert(pi1mhz_mailbox_handles(PI1MHZ_REG_PAGE_MID));
    assert(!pi1mhz_mailbox_ap5_handles(PI1MHZ_REG_PAGE_HI));
    assert(!pi1mhz_mailbox_ap5_handles(PI1MHZ_REG_PAGE_MID));
    assert(pi1mhz_mailbox_ap5_handles(PI1MHZ_REG_PAGE_LO));
    assert(pi1mhz_mailbox_ap5_handles(PI1MHZ_REG_ADDR_LO));
    assert(pi1mhz_mailbox_ap5_handles(PI1MHZ_PAGE_BASE));

    /* Byte-port write, page-aperture read: both must address the same JIM. */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x56);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0x34);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0x12);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_DATA, 0xA5);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_ADDR_LO) == 0x57);

    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_HI, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_MID, 0x12);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 0x34);
    assert(pi1mhz_mailbox_read(&mailbox, 0xFD56) == 0xA5);

    /* Page-aperture write, byte-port read. */
    pi1mhz_mailbox_write(&mailbox, 0xFD57, 0x5A);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x57);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0x34);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0x12);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_DATA) == 0x5A);

    /* FCFD selects a 16 MiB set. Pi1MHz clamps unavailable sets to the
       final installed set, so all high selectors alias set zero here. */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0x02);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_DATA, 0xC3);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_HI, 0xFF);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_MID, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 0x02);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_PAGE_HI) == 0xFF);
    assert(pi1mhz_mailbox_read(&mailbox, 0xFD00) == 0xC3);

    /* Command dispatch is deferred and exposes one BUSY observation. */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_COMMAND, 0xF3);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_COMMAND) ==
           PI1MHZ_NET_BUSY);
    assert(capture.calls == 1);
    assert(capture.selector == 0xF3);
    assert(capture.command_pointer == 0xFFF300u);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_COMMAND) == 0x42);

    pi1mhz_mailbox_destroy(&mailbox);
    puts("Pi1MHz mailbox register/JIM coherence: OK");
    return 0;
}
