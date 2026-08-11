# Elkulator integration technical change record

## Device model

The reusable mailbox component models Pi1MHz service address registers at
`&FCA6-&FCA9`, the service result at `&FCAA`, a 24-bit page selector and the
JIM window at `&FD00-&FDFF`. The AP5 adapter exposes only `&FCFF` from the page
selector group because real AP5 hardware does not forward `&FCFD` or `&FCFE`.
The mailbox and page window share one 16 MiB zero-filled allocation.

A command read returns busy once before deferred dispatch, matching the Pi
FIQ-latch and main-poll ordering. The fixture backend is deterministic. The
live backend uses non-blocking host sockets and can expose a raw FAT SD image
for the Pi1MHz MMFS service. Raw, gzip and ZIP UEF normalization is checked
against the Pi implementation by common fixtures.

## Elkulator patches

`elkulator.patch` adds the generic mailbox hooks, explicit ROM-bank loading
and writable-bank selection. `elkulator-autokeys.patch` adds deterministic
key injection for end-to-end tests. `elkulator-ap5-tube.patch` adds the AP5
Tube ULA and external 3 MHz 65C02. The `*-elkwifi.patch` variants change only
`main.c` context for an Elkulator tree which already has the ElkChat ElkWiFi
options.

The installer extracts per-file sections from the generic patches so it can
compose with existing Elkulator changes. It normalizes CRLF targets before
patching, copies the reusable device sources, appends sources through Automake
`+=` declarations and skips signatures which are already installed.

## ROM and expansion configuration

Explicit `-rom <bank> <file>` selections are applied before the MOS service-ROM
scan and take precedence over the legacy cartridge banks. `-ram <bank>` marks
any sideways bank writable. No ROM or RAM bank number is hardcoded by the
1MHzWifi ROM.

`-tube6502 <rom>` initializes the AP5 Tube ULA and parasite before the MOS
service scan. RH Plus can therefore start the parasite during cold boot as it
does on the photographed hardware. The mailbox adapter and host ROM never use
the Tube for Pi traffic or program transfer. The Tube model exists to expose
coexistence faults and remains available to software which uses it directly.

## Test controls

`-autokeys` accepts delay and keycode pairs. Elkulator's Electron key mapping
uses `@` to type `*`; automated scripts must reproduce that mapping rather than
injecting a host asterisk. `PI1MHZ_TRACE` records backend operations and
`PI1MHZ_EXIT_ON_CLOSE` terminates deterministic network tests after close.

The exact hardware profile should load the same ROM order, RAM banks, AP5/RH
Plus ROM, MMFS or ADFS media, 1MHzWifi ROM and optional Tube boot ROM. A tape
only run is useful for isolating WiCFS but is not evidence for ADFS, DFS or
MMFS coexistence.

## Validation limits

The installer applies cleanly to Elkulator commit `6cab45a`, remains
idempotent on a second invocation, and completes a native x86-64 build with
Allegro 4.4.3, zlib, OpenAL and ALUT on Ubuntu 24.04.

Unit tests cover register coherence, selector clamping, deferred dispatch,
FAT sectors, fragmented network I/O, UEF normalization and managed secure
commands. Live emulator runs can prove that a title reaches visible gameplay
under a reproducible ROM profile.

Elkulator is not a cycle-accurate proof of AP5 electrical timing, Pi SDIO,
CYW43 firmware or physical Tube arbitration. Those remain hardware gates.
