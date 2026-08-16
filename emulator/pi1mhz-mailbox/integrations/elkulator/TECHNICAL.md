# Elkulator integration technical change record

## Device model

The reusable mailbox component models Pi1MHz service address registers at
`&FCA6-&FCA9`, the service result at `&FCAA`, a 24-bit page selector and the
JIM window at `&FD00-&FDFF`. The AP5 adapter exposes only `&FCFF` from the page
selector group because real AP5 hardware does not forward `&FCFD` or `&FCFE`.
The model allocates 48 MiB. Public Rampage starts in set zero. Services byte
offsets are relative to the final 32 MiB, matching `DISC_RAM_BASE`.

A command read returns busy once before deferred dispatch, matching the Pi
FIQ-latch and main-poll ordering. The fixture backend is deterministic. The
live backend uses non-blocking host sockets and can expose a raw FAT SD image
for the Pi1MHz MMFS service. Raw, gzip and ZIP UEF normalization is checked
against the Pi implementation by common fixtures.

The optional BeebSCSI adapter owns `&FC40-&FC44`. It implements the Acorn host
adapter data, status, select and interrupt registers, six-byte SASI/SCSI
commands used by ADFS, 256-byte sectors and an explicitly supplied LUN 0 image.
The internal REQ state follows the transfer phase and feeds the IRQ latch. The
visible status REQ bit remains high, matching maintained b-em and the behavior
required for Acorn ADFS to enter without locking. This is a compatibility
model, not a cycle-level REQ/ACK simulation. A non-empty short final sector is
zero-padded, matching the established compatibility behavior. MODE
SELECT consumes its parameter bytes as a compatibility no-op in the read-only,
single-LUN test model; it does not rewrite the supplied geometry sidecar.
`&FC43` follows the primary BeebSCSI CPLD equations. D0 controls the first
stage; an asserted REQ sets the second stage, which remains latched after REQ
falls until D0 clears the first stage or reset occurs. Every IRQ-line
transition immediately refreshes Elkulator's ULA IRQ state.
`&FC44` is the BeebSCSI 7 configuration and jukebox register; it is a bounded
no-op in the single-LUN model. An optional `PI1MHZ_BEEBSCSI_DSC` file supplies
the MODE SENSE geometry. Files from 22 through 33 bytes are accepted, matching
current b-em and the 22-byte sidecar supplied with the photographed hardware.
Without an explicit setting, a `.dsc` beside the mounted LUN is selected
automatically. Only a missing sidecar uses geometry derived from image size.
The register allocation and handshake follow the Acorn Winchester host adapter
documentation and the maintained b-em SCSI implementation. Pi1MHz sees these
cycles as snoops without replacing the SCSI read value under the
`expanded-snoop` profile. The NPFC-direct `full` profile also coexists when
external nOE is enabled, because unregistered FC40 reads are not driven.
`PI1MHZ_NOE=0` selects unconditional read drive and requires Pi-side SCSI.
`&FC45-&FC47` remain unclaimed.

`PI1MHZ_FIQ_DELAY_ACCESSES` enables the timing fault model derived from the
physical AP5/Pi1MHz diagnostics.

The default `PI1MHZ_BUS_AP5` profile snoops the original AP5 decode ranges:
`FC00-FC0F`, `FC80-FC8F`, `FCA0-FCAF`, `FCFF`, and `FD00-FDFF`.
`PI1MHZ_AP5_PROFILE=full` models the documented NPFC-direct modification. It
forwards all of `FC00-FDFF` and accepts all three Rampage selector writes.
The staged default leaves external nOE enabled. Read ownership follows a
per-byte VPU output-enable map. Rampage publishes `&FD00-&FDFF` during
initialisation. Services initially publishes only `&FCAA` and `&FCAB`.
Selector and Services cursor bytes become driven only after their deferred
callbacks execute the corresponding `Pi1MHz_MemoryWrite` or
`Pi1MHz_MemoryWritePage` operation. `PI1MHZ_NOE=0` models unconditional read
drive.
`expanded-snoop` widens observation to the
full FRED page while retaining original AP5 ownership, for diagnostic setups
which mirror FC40 traffic without the NPFC-direct electrical behaviour.
`original` is the default. `PI1MHZ_AP5_FULL_FRED=1` remains a compatibility
alias for `full`. Unowned snooped accesses continue to other emulated devices.
`FCFF` reads remain floating only in the original and expanded-snoop profiles.

Selector writes update their readable echo, but FCA9 continues to use the
previously published address until the bounded
delay expires. FCA9 auto-increment is published through the same delayed
path. Release smoke tests use a delay of five selector reads, so code which
works only against an immediate emulator callback now fails in Elkulator.
Service-poll latency is not a fixed physical constant. The default profile
uses four host cycles and `PI1MHZ_SERVICE_DELAY_CYCLES` permits alternative and
stress-sweep values without claiming cycle-exact foreground scheduling.
Elkulator resets its bounded host cycle counter after reading the reset vector.
The Tube and mailbox clocks are explicitly rebased at that assignment, so the
backward discontinuity cannot be mistaken for a 128-cycle counter wrap.

## Elkulator patches

`elkulator.patch` adds the generic mailbox hooks, explicit ROM-bank loading
and writable-bank selection. `elkulator-autokeys.patch` adds deterministic
key injection for end-to-end tests. `elkulator-ap5-tube.patch` adds the AP5
Tube ULA and external 3 MHz 65C02. The `*-elkwifi.patch` variants change only
`main.c` context for an Elkulator tree which already has the ElkChat ElkWiFi
options.
`elkulator-clock-rebase-upgrade.patch` updates an already-integrated tree with
the reset-counter rebase hook; clean trees receive the same hook from the main
AP5 Tube patch.
`elkulator-beebscsi.patch` connects the standalone BeebSCSI device after the
Pi1MHz snoop hook and before Elkulator's open-bus fallback. The installer does
not select a user LUN unless one is supplied explicitly.

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
injecting a host asterisk. Scripted logical keys pass through `keylookup`, so a
saved or platform-specific host key map cannot silently change the command.
The installer upgrades ElkChat's older raw-key injector to this behaviour.
`PI1MHZ_TRACE` records backend operations and
`PI1MHZ_EXIT_ON_CLOSE` terminates deterministic network tests after close.

The `adfs-beebscsi` profile proves only the ADFS and BeebSCSI subset. A full
photographed-hardware run must separately supply the same ROM order, RAM
banks, AP5/RH Plus ROM, MMFS media, 1MHzWifi ROM and optional Tube boot ROM.
A tape-only run is useful for isolating WiCFS but is not evidence for ADFS,
DFS or MMFS coexistence.

## Validation limits

The installer applies cleanly to Elkulator commit `6cab45a`, remains
idempotent on a second invocation, and completes a native x86-64 build with
Allegro 4.4.3, zlib, OpenAL and ALUT on Ubuntu 24.04.

Unit tests cover BeebSCSI register selection and sector read/write, register
coherence, delayed FIQ publication, selector
clamping, deferred dispatch, FAT sectors, fragmented network I/O, UEF
normalization and managed secure commands. Live emulator runs can prove that
a title reaches visible gameplay under a reproducible ROM profile.

Elkulator is not a cycle-accurate proof of AP5 electrical timing, Pi SDIO,
CYW43 firmware or physical Tube arbitration. Those remain hardware gates.
The BeebSCSI model currently supports one raw SCSI-format LUN and one optional
`.dsc` geometry sidecar. It does not implement jukebox switching, padded IDE
images or format-unit creation. Those features are outside the LUN 0 gate.
It remains a separate synchronous Elkulator device and does not reproduce
contention between Pi1MHz foreground work, SD access, WiFi and the Pi-side
hard-disc service. A passing emulator run cannot close that physical timing
gate.

## BeebSCSI references

- Acorn ACW service manual, host adapter register allocation and SEL/BSY test:
  <https://mdfs.net/Docs/Books/32016CoPro/ACWService.pdf>
- Acorn host adapter signal and REQ/ACK description:
  <https://www.domesday86.com/?page_id=64>
- Pi1MHz hard-disc adapter integration:
  <https://github.com/dp111/Pi1MHz/blob/master/src/harddisc_emulator.c>
- b-em SCSI device and raw LUN implementation:
  <https://github.com/stardot/b-em/blob/master/src/scsi.c>
