# ElkWiFi MENU runtime adaptation

## Purpose

The menu published at `http://acornelectron.nl/uefarchive/MENU` is a valid
2,907-byte executable for the original ElkWiFi cartridge. It is not directly
compatible with an Electron Plus 5 and Pi1MHz because it contains an inlined
access to the cartridge UART modem-control register at `&FC34`.

The payload used for this adaptation has SHA-256
`68cf0cc8b05c50c26b22e5580dc310e1e111502d3467ca3090b55d28624fd1a0`.

The menu uses that register to select the second 64 KiB paged-RAM bank before
loading its title index. The Plus 5 does not forward the ElkWiFi UART register.
Pi1MHz uses `&FCFD`, `&FCFE`, and `&FCFF` as the high, middle, and low bytes
of its JIM page address.

## Compatibility rule

The pinned ElkWiFi source and published MENU payload define the visible
behavior. This project preserves their command order, filenames, filing-system
calls and launch semantics. An internal alteration is permitted only when an
original cartridge hardware assumption cannot operate through Pi1MHz/AP5, or
when it would conflict with other fitted Acorn hardware.

| Original mechanism | Pi1MHz adaptation | Required reason |
| --- | --- | --- |
| ElkWiFi UART and cartridge RAM banking at `&FC30-&FC34` | Pi1MHz services at `&FCA6-&FCAA` and full JIM selection at `&FCFD-&FCFF` | AP5 does not forward the cartridge UART; Pi1MHz exposes its service on the 1MHz bus |
| ROM queues BASIC `CALL &E00` after downloading MENU | Enter host `&E00` through a RAM return trampoline | The downloaded bytes are in I/O-processor RAM; a second processor must not become an accidental destination |
| MENU is entered while another filing system may own Electron workspace | Select `*TAPE` before constructing the download command | Reproduces the required cassette environment and avoids the observed ADFS workspace collision |
| Menu assumes its selected RAM bank remains active | Select JIM address `00:01:page` at each patched catalogue access | Pi1MHz services and other fitted ROMs share the JIM aperture |
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
zero-page ABI. Saved filing-vector and BYTEV predecessor state is persisted on
page `&FFF200`, reserved by this integration in Pi1MHz top service RAM, and
mirrored in ROM heap only during install and reset. The public-driver page
shadow is also transient in ROM heap.

When `*QUPCFS` runs, WiCFS installs MOS extended vectors without copying a ROM
switcher into language or Tube workspace. The installed filing vectors do not
claim ADFS workspace after the queued `*TAPE`, `PAGE` and `NEW` commands have
completed. WiCFS also restores the JIM page register to zero after reading the
downloaded length metadata. These changes preserve the exact address of the
catalogue-working MENU code. Screen output remains enabled so queue, filing
and UEF errors are visible on real hardware.

On reset, WiCFS checks the address and ROM owner of every entry before
restoring its predecessor. This removes the virtual cassette claim and its
`*TAPE` OSBYTE trap without overwriting ADFS, DFS or another later filing-system
claim.

The MOS direct vector can already point at its extended-vector dispatcher when
WiCFS starts. WiCFS therefore saves the previous handler address and owning ROM
from the extended-vector table before replacing it. An unclaimed FSCV request,
including the OSCLI pass that precedes the ROM's own `*REWIND` command, is
forwarded to that saved handler. Redispatching it through `&FF2D` would select
WiCFS again and recurse indefinitely. The saved ROM identifiers occupy the
same cassette filing-system workspace as the saved vector addresses, so a
later handler cannot erase them through shared zero-page workspace.

When the previous handler belongs to a sideways ROM, WiCFS tail-calls it
through a short trampoline copied into ordinary filing-system workspace. The
ROM switch is the trampoline's final setup action, so execution never continues
from the same address in a newly selected ROM. The trampoline is outside
`&0400-&07FF` and neither detects nor accesses a Tube.

WiCFS claims `*REWIND` directly when it is the active filing system. It leaves
`*TAPE` functional, allowing every `*MENU` invocation to return to cassette
state before reusing filing workspace. The successful `CHAIN` execution path
also completes its ROMSEL change and extended-vector stack cleanup from the RAM
trampoline. No instruction following a ROMSEL write is fetched from an
unrelated sideways ROM. It removes the dispatcher's two-byte cleanup return and
saved-ROM byte, but retains the original OSCLI return address required when a
first-stage loader returns.

The stock menu installs key 0 as `*REWIND|MCHAIN ""|M` and later inserts that
key into the keyboard buffer after a selected UEF has downloaded. The ROM does
not alter this launch contract. OSFILE requires X and Y to be preserved across
the `CHAIN` load. WiCFS saves the OSFILE control-block pointer on the active
6502 stack before parsing the UEF and restores X and Y on return. This is
intentionally not host heap: first-stage files such as Zalaga and Chuckie Egg
can overwrite the old `&09DA/&09DB` save area while loading. Forwarded FILEV
calls retain their separate vector-chain state. OSBGET similarly preserves X
and Y while returning the byte in A.

WiCFS also returns the CFS header's load address, execution address and complete
file length in the caller's 18-byte OSFILE control block. The inherited code
loaded the bytes but discarded that catalogue metadata after using the control
block pointer to find the filename. Returning the catalogue data remains
necessary for programs which call OSFILE during later UEF stages.

WiCFS is strictly a 1MHz-bus filing system. All bytes are written to Electron
I/O-processor memory and all run addresses execute there. It does not inspect
the Tube-present flag, call `&0406`, access `&FEE4` or `&FEE5`, or claim Tube
registers. A Tube may be absent, fitted or active without becoming part of the
Pi1MHz transfer path.

The downloaded image is in I/O processor memory. Queuing BASIC `CALL &E00`
would execute parasite memory when a Tube processor is active, so it is not a
safe launch mechanism. The ROM enters `&E00` on the I/O processor instead.

The published program exits through a tail-called MOS routine and may change
ROMSEL while running. Before entry, the ROM copies a short return trampoline
to `&1FD0` and pushes that RAM address as the program's return target. The
trampoline restores the service-call registers and returns cleanly to MOS
without relying on the ElkWiFi sideways ROM still being selected.

The published title-launch key expansion contains two commands: `*REWIND`, then
`CHAIN ""`. The ROM preserves that sequence exactly. `*REWIND` resets the WiCFS
cursor to the UEF installed by `*WGET -U`; `CHAIN ""` then uses the cassette
file's OSFILE metadata and BASIC's normal chain semantics. The adaptation does
not replace it with `*RUN`, `*/`, or another inferred launch path.

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

The helper at `&1FC5` establishes `&FCFD=0` and `&FCFE=1`:

```text
A9 00       LDA #&00
8D FD FC    STA &FCFD
A9 01       LDA #&01
8D FE FC    STA &FCFE
60          RTS
```

This selects Pi1MHz JIM address `00:01:page`. Keeping the replaced sequence at
eight bytes preserves every address and relative branch in the downloaded
program.

The stock payload also assumes that this selection remains active for its
entire lifetime. That is not a safe assumption on Pi1MHz because the JIM
aperture is shared by firmware services. For the known 2,907-byte payload, the
ROM replaces its three `LDA &FD00,Y` catalogue reads with calls to a small
trampoline at `&1FF0`. The trampoline selects `00:01:page` before every read.
Its title-selection page write similarly calls a trampoline at `&1FE0`. The
patch is applied only after the payload size and all four original instruction
sites have been verified.

The base-address helper is stored at `&1FC5`, immediately after the temporary
TAPE command. The I/O-processor return trampoline is at `&1FD0`, and the
catalogue helpers are at `&1FE0` and `&1FF0`. These fixed blocks do not overlap.
None is stored at `&0900`, which belongs to filing-system and ROM workspace
when ADFS is present.

The exact byte arrays are defined in `rom-side/elkwifi-0.23/menusrc.asm`. The
download and validation path is in `rom-side/elkwifi-0.23/menu.asm`.

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
`TITLES` through `*WGET -U`, selects JIM address `00:01:page`, enters WiCFS, and launches a
title without accessing `&FC34`.
