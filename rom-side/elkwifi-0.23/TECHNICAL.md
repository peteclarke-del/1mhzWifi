# ElkWiFi host ROM technical change record

## Scope and base

The patch set is based on ElkWiFi 0.23 commit
`7bf366c97bec18bd238963c95e6f2aa6893cdb3a`. It retains the public star-command,
driver and OSWORD `&65` entry model while replacing the cartridge UART transport
with the Pi1MHz services and JIM interfaces on the 1 MHz bus.

The ROM identifies as 1MHz-WiFi. It preserves Roland Leurs' original ElkWiFi
credit in `*VERSION` and adds the 1MHz-WiFi revision and Pi kernel revision.
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

The retained driver implements reset, scan, association, leave, TCP and UDP open,
single-connection selection, send and receive, close, interface status, paged
receive, channel query and WiFi control. Function 9 validates `0`, CR and
returns an original-style `OK` locally because Pi1MHz exposes one TCP
connection. Function 8 accepts the original `TCP` and `UDP` protocol fields
case-insensitively. Unsupported `SSL` fails closed and is never converted to
plaintext TCP. Function 13 reads the original five-byte zero-page control block,
sends the complete source buffer and gathers the response into sequential JIM
pages. Pi1MHz may accept only part of a TCP write. The ROM advances the caller's
pointer only by the returned queued-byte count and retries zero or partial
writes. Receive polling continues across empty inter-packet gaps until EOF or
the bounded idle deadline.

Function 24 uses a separate internal Pi command from version and status. An
enable request starts radio setup and returns promptly, matching the original
driver contract; later function 18 calls report whether addressing is ready.
Functions 29 to 31 remain reserved in the pinned ElkWiFi 0.23 contract. The
timeout setter sometimes associated with function 29 was added in ElkWiFi
0.32 and is not part of this ROM's compatibility baseline.
The DATE, TIME and ONLINE star-command extensions use private ROM selectors
32-34 and therefore do not overwrite an original driver-table entry.

Functions 6, 10 to 12, 15 to 17, 21 to 23, 26 and 27 preserve the observable
0.23 compatibility behavior without calling the removed UART. Function 19 and
reserved functions 29 to 31 return a MOS `Not implemented` error. The removed
flash, printer and baud-setting paths cannot be entered.
The dynamic MOS BRK block is built in the retired network-printer workspace,
not the `&0100` processor stack used by the original ROM.

## Command implementation

`*WIFI`, `*LAP`, `*LAPOPT`, `*JOIN`, `*LEAVE`, `*IFCFG`, `*ONLINE`, `*PING`,
`*NSLOOK`, `*DATE`, `*TIME`, `*WGET`, `*FTP`, `*WICFS`, `*REWIND` and `*UEF LOAD` use
the Pi1MHz transport. ROM 0.1.63 removes `*MENU`, `*MENUSRC`, the downloaded
menu patcher and the corresponding Pi cache. Generic HTTP and UEF behavior is
unchanged. ROM 0.1.64 makes ordinary `*WGET <url> <filename>` write through
MOS OSFIND and OSBPUT to the active filing system. JIM output is retained only
for the explicit `-U` and `-S` modes consumed by WiCFS and sideways RAM.
ROM 0.1.65 adds interactive FTP commands 114 to 119. The Pi owns both sockets;
the ROM moves local bytes only through OSFIND, OSBGET and OSBPUT. The fixed
private JIM scratch address contains at most 240 bytes and is never interpreted
as a host or Tube address.

ROM 0.1.66 replaces the public function comparison chain and FTP keyword chain
with explicit tables, shares repeated diagnostics and removes the obsolete ROM
end marker. Its maintained PRD implementation never reads a JIM selector,
reasserts selectors before each byte, and restores public bank `00:00`.

ROM 0.1.67 puts the four filing vectors on the JIM guard the Pi serves at
`romsel`, which is `&FD00+jim_page_usable` and so `&FD97`. The guard body is
stamped into every JIM page, and the ROM verifies its signature at two
different selector values before moving any vector, so the selector may hold
anything when one fires. The RAM guard below `&0800` is the fallback, used when
no mirror answers, which is what an older kernel gives. Confirmed on the
running machine: a write watch over `&0212-&0213` shows FILEV set to `&FD97`
from PC `&9D44` in the ROM's own bank.

Nothing of ours therefore sits in host RAM for a loader to overwrite, which is
what the earlier Pi-mirrored trampoline was for. That trampoline was built and
withdrawn: pointing the vectors at it broke the `*/` handover every multi-file
cassette loader ends with, because `actioned` transfers to the loaded program
by unwinding the MOS extended-vector dispatch frame and the mirrored entry
supplied its own frame instead. Every multi-file title failed after its first
file. It was removed outright rather than left unreachable, and the guard
introduced afterwards supersedes it: the guard repairs the MOS extended-vector
entry and then dispatches through MOS, so the frame stays intact and `*RUN` and
`*/` are unaffected.

Two things survive from that work. `cfsinit` starts the read cursor at JIM
page 1, because page 0 is the service reply buffer that OSWORD `&65` clients
read in full and a reply landing there used to corrupt the stream. The vector
ownership test and both vector installers became table walks instead of
unrolled comparison and store chains, which returned about ninety bytes. The
ceiling stands at `&BF00`; it was moved for the trampoline and has not been
moved back, so the reserve is larger than the minimum rather than smaller.
Any future move should carry the same justification.

## WiCFS and UEF handling

WiCFS remains an I/O-processor filing system. UEF bytes are read through the
current MOS filing system or downloaded through `*WGET -U`, normalized by the Pi and
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

A cassette file may legally load over the MOS cassette workspace at `&0380`.
WiCFS must not rewrite that range immediately after OSFILE because the loaded
file may execute there. The corpus contains one such case, Shark's `PATCH`
file. Its post-Break lifecycle remains an explicit hardware acceptance item;
the ROM does not contain a speculative recovery path which would corrupt the
loaded payload.

Tube-off OSBGET uses a direct RAM guard, following the original WiCFS shape,
instead of rebuilding and traversing the MOS extended-vector tuple for every
byte. The guard is patched once at installation for `&FE05` on Electron or
`&FE30` on BBC-family hosts. Hardware detection for JIM page selection occurs
once per 256-byte sequential buffer refill, not once per returned byte.

The generic UEF launch transition runs on the I/O processor and does not use
the Tube as a destination. ROM selection uses `&FE05` with the Electron
deselect cycle and `&FE30` on BBC-family machines, selected at runtime through
OSBYTE `&81`.

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
