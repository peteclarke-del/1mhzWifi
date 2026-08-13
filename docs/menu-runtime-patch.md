# ElkWiFi MENU runtime adaptation

## Purpose

The menu published at `http://acornelectron.nl/uefarchive/MENU` is a valid
2,907-byte executable for the original ElkWiFi cartridge. It is not directly
compatible with an Electron Plus 5 and Pi1MHz because it contains an inlined
access to the cartridge UART modem-control register at `&FC34`.

The payload used for this adaptation has SHA-256
`68cf0cc8b05c50c26b22e5580dc310e1e111502d3467ca3090b55d28624fd1a0`.

The menu uses that register to select the cartridge's second 64K paged-RAM bank
before loading its title index. The AP5 does not forward the ElkWiFi UART
register. It also forwards only `&FCFF` from Pi1MHz's three-byte Rampage
selector, exposing the standard 64K JIM window to the Electron.

## Compatibility rule

The pinned ElkWiFi source and published MENU payload define the visible
behavior. This project preserves their command order, filenames, filing-system
calls and launch semantics. An internal alteration is permitted only when an
original cartridge hardware assumption cannot operate through Pi1MHz/AP5, or
when it would conflict with other fitted Acorn hardware.

| Original mechanism | Pi1MHz adaptation | Required reason |
| --- | --- | --- |
| ElkWiFi UART and cartridge RAM banking at `&FC30-&FC34` | Pi1MHz services at `&FCA6-&FCAA` and the AP5-visible `&FCFF` JIM selector | AP5 forwards the services block and `&FCFF`, but not the cartridge UART or `&FCFD-&FCFE` |
| ROM queues BASIC `CALL &E00` after downloading MENU | Enter host `&E00` through a RAM return trampoline | The downloaded bytes are in I/O-processor RAM; a second processor must not become an accidental destination |
| MENU is entered while another filing system may own Electron workspace | Select `*TAPE` before constructing the download command | Reproduces the required cassette environment and avoids the observed ADFS workspace collision |
| Menu assumes its selected RAM bank remains active | Select the `&FCFF` page at each patched catalogue access | Pi1MHz services and other fitted ROMs share the JIM aperture |
| WiCFS copies a ROM switcher into `&0400-&07FF` | MOS extended filing vectors | That RAM is not private WiCFS workspace and can conflict with fitted hardware |
| `*REWIND` rereads length metadata through JIM | Retained | The JIM trailer is authoritative; caching it in volatile `&0900` heap corrupts later title loads |
| Key 0 runs `*REWIND`, then `CHAIN ""` | Unchanged | This is the official menu launch contract |

The rewind patch preserves the upstream `cfsinit` call and documents that the
length comes from the Pi1MHz JIM trailer. It does not introduce a second host
copy of that state.

## Download and execution sequence

`*MENU` performs these steps:

1. Execute host `*TAPE` through OSCLI before touching `&0900`, which overlaps
   Electron ADFS workspace.
2. Resolve the active URL through `*MENUSRC` configuration precedence.
3. Construct `*WGET <url> E00` in ROM workspace.
4. Clear byte `&E00` and the internal WGET completion flag.
5. Execute WGET synchronously through OSCLI.
6. Require both a completed, non-empty WGET result and a non-zero byte at `&E00`.
7. Scan `&0E00-&1FFF` for the published menu's cartridge bank-select sequence.
8. Replace that sequence in place when present.
9. Copy a return trampoline to host RAM and enter host `&E00`.

The menu then invokes `*WGET -U` for the TITLES index. Network waits call MOS
polling services, so the active JIM page and offset are held in ROM heap while
the transfer is in progress. The original ElkWiFi zero-page locations are
populated only after the download, before WiCFS starts. This prevents MOS
workspace use during a network wait from corrupting the page pointer and
raising a false `Buffer full` error on a small TITLES file.

`-U` selects the 64 KiB paged-RAM destination; it does not assert that the
download is a UEF image. The published TITLES index is raw catalogue data.
1MHzWifi therefore invokes Pi-side decompression only when the downloaded bytes
carry a gzip or ZIP signature. Raw title data and raw UEF files remain untouched.

The AP5/Pi1MHz `&FCFF` page register is treated as write-only. Its selected
page is shadowed in ROM workspace and incremented there. Reading the register
through this hardware path can return the floating-bus value `&FF`; using that
readback as the next page would falsely report a full 64 KiB window at the
first 256-byte boundary.

The same rule applies to `*WGET -S`: the 16 KiB sideways-RAM copy advances its
JIM source page through the WGET shadow and never reads or modifies `&FCFF`
in place.

WiCFS uses the same shadow rule while consuming the downloaded UEF. At a page
boundary it increments `pr_r` and writes that value to `&FCFF`; it never reads
the hardware register back. Without this second fix, downloading a title can
succeed but WiCFS loses its position after 256 bytes and never reaches the
program stored later in the UEF stream.

The MOS keyboard command queue occupies `&03E0-&03FF`, so the ROM never uses
that range for WiCFS state. Stream state uses the original WiCFS cassette
zero-page ABI. Saved filing-vector and BYTEV predecessor state is persisted
through the Pi1MHz byte port at services-buffer address `&FFEF00`, immediately
below the command pages, and mirrored in ROM heap only during install and
reset. The public-driver page shadow is also transient in ROM heap.

When `*QUPCFS` runs, WiCFS installs MOS extended vectors without copying a ROM
switcher into language or Tube workspace. The installed filing vectors do not
claim ADFS workspace after the queued `*TAPE`, `PAGE` and `NEW` commands have
completed. WiCFS also restores the JIM page register to zero after reading the
downloaded length metadata. These changes preserve the exact address of the
catalogue-working MENU code. Screen output remains enabled so queue, filing
and UEF errors are visible on real hardware.

On reset, MOS has already rebuilt the standard and extended vector tables.
WiCFS clears its persisted ownership marker and leaves those new tables alone.
It must not write the saved cassette predecessors over a filing system which
has already reclaimed its vectors during the same reset pass.

The MOS direct vector can already point at its extended-vector dispatcher when
WiCFS starts. WiCFS therefore saves the previous handler address and owning ROM
from the extended-vector table before replacing it. An unclaimed FSCV request,
including the OSCLI pass that precedes the ROM's own `*REWIND` command, is
forwarded to that saved handler. Redispatching it through `&FF2D` would select
WiCFS again and recurse indefinitely. The saved ROM identifiers occupy the
same cassette filing-system workspace as the saved vector addresses, so a
later handler cannot erase them through shared zero-page workspace.

When the previous handler belongs to a sideways ROM, WiCFS copies a short
tail-call into host filing workspace. That code selects the recorded owner and
jumps to its handler without fetching another instruction from the now-paged
out 1MHzWifi ROM. It returns through the existing MOS extended-vector frame.
The path uses no private code in `&0400-&07FF` and does not access a Tube.

WiCFS claims `*REWIND` directly when it is the active filing system. It leaves
`*TAPE` functional, allowing every `*MENU` invocation to return to cassette
state before reusing filing workspace. The successful `CHAIN` execution path
copies its final ROM selection and execution jump to filing-system RAM. The
trampoline removes the five dispatcher bytes installed above the real caller
return address by the Electron MOS extended-vector path: the cleanup address,
saved ROM and dispatcher JSR return. It then jumps through the cassette
execution address at `&03C2`, leaving the loaded stage's caller return intact.

The stock menu installs key 0 as `*REWIND|MCHAIN ""|M` and later inserts that
key into the keyboard buffer after a selected UEF has downloaded. The ROM does
not alter this launch contract. OSFILE requires X and Y to be preserved across
the `CHAIN` load. WiCFS saves the OSFILE control-block pointer on the active
6502 stack before parsing the UEF and restores X and Y on return. This is
intentionally not host heap: first-stage files such as Zalaga and Chuckie Egg
can overwrite the old `&09DA/&09DB` save area while loading. Forwarded FILEV
calls retain their separate vector-chain state. OSBGET similarly preserves X
and Y while returning the byte in A.

WiCFS returns the cassette catalogue metadata through the caller's 18-byte
OSFILE block, including portable host load and execution addresses and the
file length. This matches MOS OSFILE action `&FF` and gives BASIC CHAIN the
execution metadata it requires. The found result in A and the caller's X/Y
pointer are preserved.

WiCFS receives every UEF byte from Pi1MHz through the 1MHz bus and JIM and
writes it to Electron I/O-processor memory. The launcher queries Tube presence
with MOS OSBYTE `&EA` so it can keep command interpretation on the host. It
does not access Tube registers, transfer data to the Tube, or disable it. A
fitted Tube remains active for software which deliberately uses it.

Multi-stage loaders can later issue `BASIC` themselves. MOS normally relocates
that language to an active parasite before the service-ROM command pass. A
successful WiCFS `*RUN` arms a one-shot host continuation. While that token is
armed, the FSCV reason-8 handler recognises only the complete `BASIC` command.
If OSBYTE `&EA` reports a Tube, it consumes the token and enters the installed
BASIC ROM directly on the Electron. Installation, rewind and a consumed
handoff clear the token. Any manual or unrelated `BASIC` command follows the
normal MOS path. This boundary allows Thrust to pass its `THRUST1` stage
without using the Tube as a destination.

The extended-vector and successful-run ROM switches use 26-byte and 25-byte
RAM trampolines at `&03A0-&03B9` and `&03A0-&03B8`. Assembly-time bounds
prevent either trampoline from reaching private state at `&03BD`. Their
parameters are held in cassette zero page and
the one-shot continuation byte is at `&03BD`; the OSFILE metadata block begins
at `&03BE`. The regions do not overlap. The trampoline preserves interrupt
state, writes both the MOS ROM shadow and the machine-specific ROMSEL register,
and preselects AP5 slot 12 before an Electron low-slot selection.

The downloaded image is in I/O processor memory. Queuing BASIC `CALL &E00`
would execute parasite memory when a Tube processor is active, so it is not a
safe launch mechanism. The ROM enters `&E00` on the I/O processor instead.

The published program exits through a tail-called MOS routine and may change
ROMSEL while running. Before entry, the ROM copies a short return trampoline
to `&1FD0` and pushes that RAM address as the program's return target. The
trampoline restores the service-call registers and returns cleanly to MOS
without relying on the ElkWiFi sideways ROM still being selected.

The published title-launch key expansion contains `*REWIND`, then `CHAIN ""`.
The ROM leaves that exact expansion unchanged. It does not disable or use the
Tube and does not invent a different game command.

## Byte-level replacement

The published menu contains this eight-byte sequence:

```text
AD 34 FC    LDA &FC34
09 08       ORA #&08
8D 34 FC    STA &FC34
```

The ROM replaces it with an equal-length sequence:

```text
20 C5 1F    JSR &1FC5
EA EA EA EA EA
```

The helper at `&1FC5` leaves A set to one, as the original sequence did, but
does not attempt to select a cartridge-only bank:

```text
A9 01       LDA #&01
EA EA EA EA EA EA EA EA
60          RTS
```

Keeping the replaced sequence and helper layout unchanged preserves every
address and relative branch in the downloaded program.

The stock payload also assumes that this selection remains active for its
entire lifetime. That is not a safe assumption on Pi1MHz because the JIM
aperture is shared by firmware services. For the known 2,907-byte payload, the
ROM replaces its three `LDA &FD00,Y` catalogue reads with calls to a small
trampoline at `&1FF0`. The trampoline reads the current AP5-visible JIM page.
Its title-selection page write similarly calls a trampoline at `&1FE0`. The
patch is applied only after the payload size and all four original instruction
sites have been verified.

The base-address helper is stored at `&1FC5`, immediately after the temporary
TAPE command. The I/O-processor return trampoline is at `&1FD0`, and the
catalogue helpers are at `&1FE0` and `&1FF0`. These fixed blocks do not overlap.
None is stored at `&0900`, which belongs to filing-system and ROM workspace
when ADFS is present.

The exact byte arrays are defined in
`rom-side/elkwifi-0.23/overlay/menusrc.asm`. The download and validation path
is in `rom-side/elkwifi-0.23/overlay/menu.asm`.

## Custom menu payloads

A custom payload that does not contain the exact cartridge sequence is left
unchanged. A custom payload that contains the same eight bytes is treated as
using the stock cartridge bank-selection idiom and is adapted in the same way.

The runtime adaptation is intentionally narrow. It does not rewrite arbitrary
UART access or make other cartridge binaries Pi1MHz compatible. A future menu
format should expose a versioned header or capability declaration instead of
depending on signature matching.

## Failure behavior

The ROM does not enter `&E00` when WGET fails, is cancelled, returns an empty
body, or leaves `&E00` unchanged. It prints `Menu download failed` for a
completed transfer that does not produce an executable candidate at `&E00`.

Real-hardware validation must confirm that the published menu starts, downloads
`TITLES` through `*WGET -U`, uses the AP5-visible JIM window, enters WiCFS, and
launches a title without accessing `&FC34`.
