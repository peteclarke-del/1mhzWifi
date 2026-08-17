# ElkWiFi host ROM technical change record

## Scope and base

The patch set is based on ElkWiFi 0.23 commit
`7bf366c97bec18bd238963c95e6f2aa6893cdb3a`. It retains the public star-command,
driver and OSWORD `&65` entry model while replacing the cartridge UART transport
with the Pi1MHz services and JIM interfaces on the 1 MHz bus.

The ROM identifies as 1MHzWifi. It preserves Roland Leurs' original ElkWiFi
credit in `*VERSION` and adds the 1MHzWifi revision and Pi kernel revision.
The generated image is exactly 16 KiB.

## Transport boundary

The ROM uses `&FCA6-&FCAA` for Pi1MHz service requests, `&FCFF` for the
AP5-visible JIM page selector and `&FD00-&FDFF` for page data. It never falls
through to the original `&FC30` cartridge UART. On Electron, AP5 does not
forward `&FCFD` or `&FCFE`, so public buffers and UEF data stay in the low
64 KiB JIM window without touching those registers. On BBC-family machines,
the ROM detects the platform through OSBYTE `&81` and explicitly selects upper
JIM bank `00:00` before exposing the same public buffer.

Slow work is not performed by the ROM. The ROM writes a bounded command block,
dispatches it, treats every bit-7-set status including the physical selector
echo as busy, yields with OSBYTE `&13`, checks Escape and applies a finite
timeout. Escape sends command 90 so the Pi can invalidate
late DNS, ICMP, NTP and scan callbacks.

After a service completes, the ROM masks interrupts, reselects the complete
`01:FF:FF` service-response cursor and copies the bounded reply before restoring
the previous interrupt state. This prevents IRQ-side MMFS or ADFS activity
from redirecting FCA9 between the completion poll and the response copy.

## Public compatibility surface

The retained driver implements reset, scan, association, leave, TCP open,
single-connection selection, send and receive, close, interface status, paged
receive, channel query and WiFi control. Function 9 validates `0`, CR and
returns an original-style `OK` locally because Pi1MHz exposes one TCP
connection. Function 13 reads the original five-byte zero-page control block,
sends the complete source buffer and gathers the response into sequential JIM
pages. Pi1MHz may accept only part of a TCP write. The ROM advances the caller's
pointer only by the returned queued-byte count and retries zero or partial
writes. Receive polling continues across empty inter-packet gaps until EOF or
the bounded idle deadline.

Function 24 uses a separate internal Pi command from version and status. An
enable request starts radio setup and returns promptly, matching the original
driver contract; later function 18 calls report whether addressing is ready.

Unsupported cartridge-only functions return a MOS `Not implemented` error.
They do not call removed UART, flash, printer or baud-rate code.
The dynamic MOS BRK block is built in the retired network-printer workspace,
not the `&0100` processor stack used by the original ROM.

## Command implementation

`*WIFI`, `*LAP`, `*LAPOPT`, `*JOIN`, `*LEAVE`, `*IFCFG`, `*ONLINE`, `*PING`,
`*DATE`, `*TIME`, `*MENU`, `*MENUSRC`, `*WGET`, `*WICFS`, `*REWIND` and
`*UEF LOAD` use the Pi1MHz transport. `*MENU` uses the built-in Electron menu
URL unless `*MENUSRC` has stored another URL. The built-in payload is rejected
on a non-Electron machine; a custom source remains available.

The published menu contains fixed cartridge bank-selection code. The ROM
validates the downloaded size and instruction signatures, then replaces only
the known byte sequences with AP5 JIM helpers. Unknown payloads are not
patched or executed.

## WiCFS and UEF handling

WiCFS remains an I/O-processor filing system. UEF bytes are read through the
current MOS filing system or downloaded through WGET, normalized by the Pi and
consumed through the low JIM window. The implementation does not access Tube
registers, claim a Tube channel, disable a fitted Tube or copy a title to a
parasite.

WiCFS installs FILEV, FINDV, FSCV and BGETV through MOS extended vectors. It
records displaced vector owners and restores only entries it still owns. A
short RAM tail selects a displaced sideways-ROM owner without fetching the
next instruction from a ROM which has just been paged out. Reset clears
persisted ownership after MOS has rebuilt the vectors, avoiding stale
restoration over ADFS, DFS or MMFS.

The ROM records its service-supplied bank number at installation time and does
not assume a fixed sideways slot. The OSWORD entry is tested with service ROM
numbers 0 through 15. `*WGET -S` uses the bank supplied by the caller and
verifies that the selected bank is writable; it does not search for or reserve
a particular sideways-RAM bank. Optional consumers must use an allocator or
fall back when none is available, because MMFS, language ROMs and user hardware
may occupy any bank.

The OSFILE control-block pointer and X/Y are preserved across a load. Returned
catalogue metadata is taken from the UEF header after the payload has been
placed at the destination selected by the filing-system operation. Zero-length
blocks, final-block lengths, multi-file streams and write-only `&FCFF` are
handled explicitly. Generic responses, local UEF import and WGET finalisation
reselect the page and access JIM with interrupts masked, while MOS filing calls
remain outside those short critical sections.

With an active Tube, the downloaded Electron menu and its cassette loaders
must still run on the I/O processor. The verified menu launch enters the
installed host BASIC ROM from RAM and queues `PAGE=&E00` before the internal
WiCFS launch command. A cold host BASIC otherwise derives PAGE from the active
Tube environment, leaving CHAIN continuation pointers in `&23xx` instead of
the host program at `&0Exx`. The transition does not use the Tube as a
destination. ROM selection uses `&FE05` with the Electron deselect cycle and
`&FE30` on BBC-family machines, selected at runtime through OSBYTE `&81`.

## Code removal and audit notes

The emitted ROM excludes printer, updater, flash programming, UART baud-rate,
AT-command WGET, CRC diagnostic and unused helper paths. Overlay files are the
canonical implementation for replaced modules. Ordered patches contain only
changes which must compose with upstream source. The build script checks every
patch for an already-applied signature before assembly.

The external diagnostic report which proposed 65C816 `PHK`, high JIM selector
`&FFF200` and Tube R3 transfers does not describe this build. The target is a
6502 Electron/BBC host, AP5 exposes only `&FCFF`, and the current loader has no
Tube transfer path.

## Validation status

Automated tests inspect the command table, OSWORD dispatch, JIM page shadow,
removed UART signatures, menu patch signatures, UEF bounds and ROM identity.
Clean upstream builds must reproduce the recorded 16 KiB ROM.

Emulator evidence does not replace hardware acceptance. The open gates are the
full command and OSWORD comparison with an original ElkWiFi cartridge, physical
WiFi association and DHCP, Tube-enabled gameplay, and post-Break ADFS, DFS and
MMFS restoration.
