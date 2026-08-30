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
    pi1mhz_host_clock clock = { 0, 0 };

    /* Elkulator resets its 0..127 instruction-cycle counter only after the
       reset-vector reads. Explicit rebasing at that point must prevent the
       backward jump from becoming a phantom 1 MHz-bus interval. */
    assert(pi1mhz_host_clock_sync(&clock, 120) == 0);
    assert(pi1mhz_host_clock_sync(&clock, 126) == 6);
    pi1mhz_host_clock_rebase(&clock, 0);
    assert(pi1mhz_host_clock_sync(&clock, 0) == 0);
    assert(pi1mhz_host_clock_sync(&clock, 3) == 3);
    assert(pi1mhz_host_clock_sync(&clock, 1) == 126); /* genuine wrap */

    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));

    /* External nOE follows the VPU output-enable bits, not the static callback
       map. Rampage publishes JIM at init; Services publishes command/IRQ only.
       Selector and Services cursor readback become owned after their deferred
       callbacks perform the corresponding MemoryWrite operations. */
    assert(pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_PAGE_BASE));
    assert(pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_PAGE_END));
    assert(pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_COMMAND));
    assert(pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_IRQ));
    assert(!pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_PAGE_HI));
    assert(!pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_PAGE_MID));
    assert(!pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_PAGE_LO));
    assert(!pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_ADDR_LO));
    assert(!pi1mhz_mailbox_profile_read_driven(
        &mailbox, PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_LO, 1));
    assert(pi1mhz_mailbox_profile_read_driven(
        &mailbox, PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_COMMAND, 1));
    assert(pi1mhz_mailbox_profile_read_driven(
        &mailbox, PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_IRQ, 1));
    assert(!pi1mhz_mailbox_profile_read_driven(
        &mailbox, PI1MHZ_BUS_AP5_FULL_FRED, 0xFC40u, 1));
    assert(pi1mhz_mailbox_profile_read_driven(
        &mailbox, PI1MHZ_BUS_AP5_FULL_FRED, 0xFC40u, 0));

    pi1mhz_mailbox_set_timing(&mailbox, 2, 2, 1);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 1);
    assert(!pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_PAGE_LO));
    pi1mhz_mailbox_tick_fiq(&mailbox, 4);
    assert(pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_PAGE_LO));
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x34);
    assert(!pi1mhz_mailbox_read_driven(&mailbox, PI1MHZ_REG_ADDR_LO));
    pi1mhz_mailbox_tick_fiq(&mailbox, 4);
    for (uint16_t address = PI1MHZ_REG_ADDR_LO;
         address <= PI1MHZ_REG_DATA; ++address)
        assert(pi1mhz_mailbox_read_driven(&mailbox, address));
    pi1mhz_mailbox_destroy(&mailbox);
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
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5, PI1MHZ_REG_PAGE_LO, 1));
    assert(!pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5, PI1MHZ_REG_PAGE_LO, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_DIRECT, PI1MHZ_REG_PAGE_LO, 0));
    assert(pi1mhz_mailbox_profile_snoops(PI1MHZ_BUS_DIRECT, 0xFC55u, 0));
    assert(!pi1mhz_mailbox_profile_handles(PI1MHZ_BUS_DIRECT, 0xFC55u, 0));
    assert(pi1mhz_mailbox_profile_handles_mode(
        PI1MHZ_BUS_DIRECT, 0xFC55u, 0, 0));
    assert(pi1mhz_mailbox_profile_snoops(PI1MHZ_BUS_AP5, 0xFC05u, 0));
    assert(!pi1mhz_mailbox_profile_snoops(PI1MHZ_BUS_AP5, 0xFC55u, 0));
    assert(pi1mhz_mailbox_profile_snoops(
        PI1MHZ_BUS_AP5_FULL_FRED, 0xFC55u, 0));
    assert(pi1mhz_mailbox_profile_snoops(
        PI1MHZ_BUS_AP5_EXPANDED_SNOOP, 0xFC55u, 0));
    assert(!pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_EXPANDED_SNOOP, 0xFC55u, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_EXPANDED_SNOOP, PI1MHZ_REG_ADDR_LO, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_ADDR_LO, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_DATA, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_LO, 1));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_LO, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_PAGE_BASE, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_HI, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_HI, 1));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_MID, 0));
    assert(pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, PI1MHZ_REG_PAGE_MID, 1));
    assert(!pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, 0xFC55u, 0));
    assert(pi1mhz_mailbox_profile_handles_mode(
        PI1MHZ_BUS_AP5_FULL_FRED, 0xFC55u, 0, 0));
    assert(!pi1mhz_mailbox_profile_handles_mode(
        PI1MHZ_BUS_AP5_FULL_FRED, 0xFC40u, 0, 1));
    assert(pi1mhz_mailbox_profile_handles_mode(
        PI1MHZ_BUS_AP5_FULL_FRED, 0xFC40u, 0, 0));
    assert(!pi1mhz_mailbox_profile_handles(
        PI1MHZ_BUS_AP5_FULL_FRED, 0xFC55u, 1));
    pi1mhz_mailbox_set_timing(&mailbox, 3, 1, 1);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x44);
    pi1mhz_mailbox_tick_fiq(&mailbox, 1);
    /* Expanded-snoop FC40 is not owned by this device, but Pi observes it and
       its GPIO sample overwrites the still-pending FCA6 write. */
    (void)pi1mhz_mailbox_bus_access(&mailbox, 0xFC40u, 0xFFu, 0);
    assert(mailbox.capture_ticks_remaining == 2);
    assert(mailbox.posted.address == 0xFC40u);
    pi1mhz_mailbox_tick_fiq(&mailbox, 2);
    assert(mailbox.address == 0);
    pi1mhz_mailbox_set_timing(&mailbox, 0, 0, 0);

    /* Services byte offsets are relative to the final 32 MiB workspace;
       public Rampage set zero is a distinct physical region. */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x56);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0x34);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0x12);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_DATA, 0xA5);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_ADDR_LO) == 0x57);

    assert(mailbox.jim[mailbox.services_base + 0x123456u] == 0xA5);
    assert(mailbox.jim[0x123456u] == 0);
    mailbox.jim[0x123456u] = 0xB6;
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_HI, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_MID, 0x12);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 0x34);
    assert(pi1mhz_mailbox_read(&mailbox, 0xFD56) == 0xB6);

    /* Public page writes likewise do not alter the Services-relative byte. */
    pi1mhz_mailbox_write(&mailbox, 0xFD57, 0x5A);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x57);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0x34);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0x12);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_DATA) == 0x00);
    assert(mailbox.jim[0x123457u] == 0x5A);

    /* FCFD selects a 16 MiB set. Pi1MHz clamps unavailable sets to the
       final installed set, so all high selectors alias set zero here. */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0x02);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_DATA, 0xC3);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_HI, 0xFF);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_MID, 0x00);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 0x02);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_PAGE_HI) == 0x02);
    assert(mailbox.jim[mailbox.services_base + 0x200u] == 0xC3);
    assert(pi1mhz_mailbox_read(&mailbox, 0xFD00) == 0x00);

    /* Zero-latency compatibility mode completes synchronously but preserves
       the legacy fixture's single BUSY observation. */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_COMMAND, 0xF3);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_COMMAND) ==
           PI1MHZ_NET_BUSY);
    assert(capture.calls == 1);
    assert(capture.selector == 0xF3);
    assert(capture.command_pointer == mailbox.services_base + 0xFFF300u);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_COMMAND) == 0x42);

    pi1mhz_mailbox_destroy(&mailbox);

    /* Before FIQ captures the VPU word there is only one posted slot. Bus
       accesses sample current state but never advance scheduler time. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    pi1mhz_mailbox_set_timing(&mailbox, 3, 2, 2);
    mailbox.jim[mailbox.services_base] = 0x11;
    mailbox.jim[mailbox.services_base + 0x20u] = 0x22;
    pi1mhz_mailbox_set_timing(&mailbox, 3, 2, 2);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x20);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_DATA) == 0x11);
    assert(mailbox.capture_ticks_remaining == 3);
    assert(mailbox.posted.address == PI1MHZ_REG_DATA);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    assert(mailbox.active.valid);
    pi1mhz_mailbox_tick_fiq(&mailbox, 2);
    assert(mailbox.address == 1); /* selector lost; stale FCA9 read advanced 0 */
    pi1mhz_mailbox_destroy(&mailbox);

    /* Replacing a posted GPIO word must not restart an already-pending
       doorbell countdown. Rapid traffic changes the captured sample but
       cannot postpone FIQ capture indefinitely. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    pi1mhz_mailbox_set_timing(&mailbox, 3, 1, 1);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x10);
    pi1mhz_mailbox_tick_fiq(&mailbox, 2);
    assert(mailbox.capture_ticks_remaining == 1);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x20);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x30);
    assert(mailbox.capture_ticks_remaining == 1);
    pi1mhz_mailbox_tick_fiq(&mailbox, 1);
    assert(mailbox.active.valid);
    assert(mailbox.active.value == 0x30);
    pi1mhz_mailbox_tick_fiq(&mailbox, 1);
    assert(mailbox.address == 0x30);
    pi1mhz_mailbox_destroy(&mailbox);

    /* At the capture/ack boundary the sample becomes private active state.
       A newer VPU sample is retained in the now-free posted slot while the
       first callback runs, rather than replacing the active callback. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    pi1mhz_mailbox_set_timing(&mailbox, 3, 2, 2);
    mailbox.jim[mailbox.services_base] = 0x11;
    mailbox.jim[mailbox.services_base + 0x20u] = 0x22;
    pi1mhz_mailbox_set_timing(&mailbox, 3, 2, 2);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x20);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    assert(mailbox.active.valid);
    assert(mailbox.active.address == PI1MHZ_REG_ADDR_LO);
    assert(mailbox.callback_ticks_remaining == 2);
    assert(!mailbox.posted.valid); /* doorbell acknowledged on capture */
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_DATA) == 0x11);
    assert(mailbox.active.address == PI1MHZ_REG_ADDR_LO);
    assert(mailbox.callback_ticks_remaining == 2); /* bus access is not time */
    assert(mailbox.posted.valid);
    assert(mailbox.posted.address == PI1MHZ_REG_DATA);
    pi1mhz_mailbox_tick_fiq(&mailbox, 2);
    assert(mailbox.address == 0x20);
    assert(mailbox.posted.valid);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    assert(mailbox.active.address == PI1MHZ_REG_DATA);
    pi1mhz_mailbox_tick_fiq(&mailbox, 2);
    assert(mailbox.address == 0x21);
    pi1mhz_mailbox_destroy(&mailbox);

    /* Command routing is driven by consumption of the posted FCAA write, not
       by a later FCAA poll. Host-local time alone must dispatch it, and reads
       after completion must not manufacture another main-loop step. */
    {
        unsigned calls_before = capture.calls;

        assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
        pi1mhz_mailbox_set_timing(&mailbox, 2, 2, 2);
        pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_COMMAND, 0xF3);
        assert(capture.calls == calls_before);
        pi1mhz_mailbox_tick_fiq(&mailbox, 2); /* capture/ack only */
        assert(capture.calls == calls_before);
        assert(mailbox.vpu_registers[4] == 0);
        pi1mhz_mailbox_tick_fiq(&mailbox, 2); /* acceptance publishes BUSY */
        assert(mailbox.vpu_registers[4] == PI1MHZ_NET_BUSY);
        assert(capture.calls == calls_before);
        pi1mhz_mailbox_tick_fiq(&mailbox, 1);
        assert(capture.calls == calls_before);
        pi1mhz_mailbox_tick_fiq(&mailbox, 1); /* foreground completion */
        assert(capture.calls == calls_before + 1u);
        assert(capture.selector == 0xF3);
        assert(capture.command_pointer == mailbox.services_base + 0xFFF300u);
        assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_COMMAND) == 0x42);
        assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_COMMAND) == 0x42);
        assert(capture.calls == calls_before + 1u);
        pi1mhz_mailbox_destroy(&mailbox);
    }

    /* Foreground service latency is configurable rather than asserted as a
       physical constant. Sweep representative scheduler delays. */
    for (unsigned delay = 1; delay <= 8; ++delay) {
        unsigned calls_before = capture.calls;
        assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
        pi1mhz_mailbox_set_timing(&mailbox, 0, 0, delay);
        pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_COMMAND, 0xF3);
        assert(mailbox.vpu_registers[4] == PI1MHZ_NET_BUSY);
        if (delay > 1)
            pi1mhz_mailbox_tick_fiq(&mailbox, delay - 1);
        assert(capture.calls == calls_before);
        pi1mhz_mailbox_tick_fiq(&mailbox, 1);
        assert(capture.calls == calls_before + 1u);
        assert(mailbox.vpu_registers[4] == 0x42);
        pi1mhz_mailbox_destroy(&mailbox);
    }

    /* Reads of FRED are not side-effect-free at the Pi/VPU boundary: every
       one posts a newer GPIO sample. The old settling loop can therefore
       destroy the selector write it is waiting for. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    mailbox.jim[mailbox.services_base] = 0x11;
    mailbox.jim[mailbox.services_base + 0x20u] = 0x22;
    pi1mhz_mailbox_set_timing(&mailbox, 3, 2, 2);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x20);
    for (unsigned i = 0; i < 8; ++i)
        (void)pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_ADDR_LO);
    pi1mhz_mailbox_tick_fiq(&mailbox, 5);
    assert(mailbox.address == 0);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_DATA) == 0x11);
    pi1mhz_mailbox_destroy(&mailbox);

    /* Calibrated HWDTEST schedule. Selector callbacks fit between the setup
       accesses, while the FCA9 write completes after the following low-byte
       read has already sampled zero. This is the physical 00 F0 FF 5E trace. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    pi1mhz_mailbox_set_timing(&mailbox, 1, 2, 1);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x00);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_MID, 0xF0);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_HI, 0xFF);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_DATA, 0x5E);
    pi1mhz_mailbox_tick_fiq(&mailbox, 1); /* capture before later reads */
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_ADDR_LO) == 0x00);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_ADDR_MID) == 0xF0);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_ADDR_HI) == 0xFF);
    pi1mhz_mailbox_tick_fiq(&mailbox, 2); /* finish the FCA9 write */
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_ADDR_LO, 0x00);
    pi1mhz_mailbox_tick_fiq(&mailbox, 3);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_DATA) == 0x5E);
    pi1mhz_mailbox_destroy(&mailbox);

    /* FCFF and FDxx use the same posted FIQ path. Until the FCFF callback has
       copied a page into the VPU window, an immediate JIM read sees the old
       page. A later FD write can likewise be overwritten before backing JIM
       is updated. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    mailbox.jim[0x0000] = 0x31;
    mailbox.jim[0x0100] = 0x42;
    pi1mhz_mailbox_set_timing(&mailbox, 3, 2, 2);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 1);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE) == 0x31);
    pi1mhz_mailbox_tick_fiq(&mailbox, 5); /* read event won; page stayed zero */
    assert(mailbox.page == 0);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 1);
    pi1mhz_mailbox_tick_fiq(&mailbox, 5);
    /* ram_emulator_page_addr_low publishes selector readback only after its
       page-window copy has completed. Both become visible on the same tick. */
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_REG_PAGE_LO) == 1);
    assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE) == 0x42);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_PAGE_BASE + 1u, 0x77);
    (void)pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE + 2u);
    pi1mhz_mailbox_tick_fiq(&mailbox, 5);
    assert(mailbox.jim[0x0101] == 0x00); /* FD read replaced pending write */
    pi1mhz_mailbox_destroy(&mailbox);

    /* FCFF executes a 256-byte MemoryWritePage callback. While that longer
       callback is active, later bus cycles coalesce in the one pending VPU
       slot; only the newest sample is captured after FCFF returns. */
    assert(!pi1mhz_mailbox_init(&mailbox, dispatch, &capture));
    pi1mhz_mailbox_set_timing(&mailbox, 1, 1, 1);
    pi1mhz_mailbox_set_callback_timing(&mailbox, 1, 5, 0);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_REG_PAGE_LO, 1);
    pi1mhz_mailbox_tick_fiq(&mailbox, 1);
    assert(mailbox.active.address == PI1MHZ_REG_PAGE_LO);
    assert(mailbox.callback_ticks_remaining == 5);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_PAGE_BASE + 1u, 0x77);
    pi1mhz_mailbox_write(&mailbox, PI1MHZ_PAGE_BASE + 2u, 0x88);
    assert(mailbox.posted.valid);
    assert(mailbox.posted.address == PI1MHZ_PAGE_BASE + 2u);
    assert(mailbox.capture_ticks_remaining == 1);
    pi1mhz_mailbox_tick_fiq(&mailbox, 5);
    assert(mailbox.page == 1);
    assert(!mailbox.posted.valid);
    assert(mailbox.active.valid);
    assert(mailbox.active.address == PI1MHZ_PAGE_BASE + 2u);
    assert(mailbox.jim[0x0101] == 0);
    assert(mailbox.jim[0x0102] == 0);
    pi1mhz_mailbox_tick_fiq(&mailbox, 1);
    assert(mailbox.jim[0x0101] == 0);
    assert(mailbox.jim[0x0102] == 0x88);

    /* A trampoline mirrored into every page must answer whatever the selector
     * holds, and must not disturb the rest of the window. The host filing
     * vectors can then point into JIM, where no game can overwrite them. */
    {
        static const uint8_t stub[4] = { 0xEE, 0x72, 0x00, 0x60 };
        unsigned pages[3] = { 1u, 0x1Au, 0xFFu };
        unsigned i;

        pi1mhz_mailbox_set_mirror(&mailbox, 0xE0u, stub, sizeof(stub));
        for (i = 0; i < 3; i++) {
            mailbox.page = pages[i];
            assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE + 0xE0u)
                   == 0xEE);
            assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE + 0xE3u)
                   == 0x60);
        }
        /* Offsets below the mirror still read the selected page. */
        mailbox.page_window[0x10] = 0x5A;
        assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE + 0x10u) == 0x5A);
        /* An empty or oversized publication disables the mirror. */
        pi1mhz_mailbox_set_mirror(&mailbox, 0xE0u, stub, 0);
        mailbox.page_window[0xE0] = 0x3C;
        assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE + 0xE0u) == 0x3C);
        pi1mhz_mailbox_set_mirror(&mailbox, 0xF0u, stub, 32);
        assert(pi1mhz_mailbox_read(&mailbox, PI1MHZ_PAGE_BASE + 0xE0u) == 0x3C);
    }

    pi1mhz_mailbox_destroy(&mailbox);
    puts("Pi1MHz mailbox register/JIM coherence: OK");
    return 0;
}
