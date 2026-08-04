# ElkWiFi MENU runtime adaptation

## Purpose

The menu published at `http://acornelectron.nl/uefarchive/MENU` is a valid
2,907-byte executable for the original ElkWiFi cartridge. It is not directly
compatible with an Electron Plus 5 and Pi1MHz because it contains an inlined
access to the cartridge UART modem-control register at `&FC34`.

The menu uses that register to select the second 64 KiB paged-RAM bank before
loading its title index. The Plus 5 does not forward the ElkWiFi UART register.
Pi1MHz selects its two JIM windows through `&FCFE` instead.

## Download and execution sequence

`*MENU` performs these steps:

1. Resolve the active URL through `*MENUSRC` configuration precedence.
2. Construct `*WGET <url> E00` in ROM workspace.
3. Clear byte `&E00` and the internal WGET completion flag.
4. Execute WGET synchronously through OSCLI.
5. Require both a completed, non-empty WGET result and a non-zero byte at `&E00`.
6. Scan `&0E00-&1FFF` for the published menu's cartridge bank-select sequence.
7. Replace that sequence in place when present.
8. Copy a return trampoline to host RAM and enter host `&E00`.

The menu then invokes `*WGET -U` for the TITLES index. Network waits call MOS
polling services, so the active JIM page and offset are held in ROM heap while
the transfer is in progress. The original ElkWiFi zero-page locations are
populated only after the download, before WiCFS starts. This prevents MOS
workspace use during a network wait from corrupting the page pointer and
raising a false `Buffer full` error on a small TITLES file.

The AP5/Pi1MHz `&FCFF` page register is treated as write-only. Its selected
page is shadowed in ROM workspace and incremented there. Reading the register
through this hardware path can return the floating-bus value `&FF`; using that
readback as the next page would falsely report a full 64 KiB window at the
first 256-byte boundary.

WiCFS uses the same shadow rule while consuming the downloaded UEF. At a page
boundary it increments `pr_r` and writes that value to `&FCFF`; it never reads
the hardware register back. Without this second fix, downloading a title can
succeed but WiCFS loses its position after 256 bytes and never reaches the
program stored later in the UEF stream.

The WiCFS page and offset cursor live in private ROM workspace at `&09D8` and
`&09D9`, not the inherited zero-page locations `&C7` and `&C8`. This keeps the
cursor stable when BASIC, MOS filing code or a Tube transfer runs between WiCFS
vector calls.

WiCFS also retains its sideways-ROM slot in private workspace and refreshes it
when `*QUPCFS` runs. The queued `*TAPE`, `PAGE` and `NEW` commands therefore
cannot corrupt the slot used by the installed filing vectors. Screen output is
left enabled during this sequence so any queue, filing or UEF error remains
visible on real hardware.

The downloaded image is in I/O processor memory. Queuing BASIC `CALL &E00`
would execute parasite memory when a Tube processor is active, so it is not a
safe launch mechanism. The ROM enters `&E00` on the I/O processor instead.

The published program exits through a tail-called MOS routine and may change
ROMSEL while running. Before entry, the ROM copies a short return trampoline
to `&0900` and pushes that RAM address as the program's return target. The
trampoline restores the service-call registers and returns cleanly to MOS
without relying on the ElkWiFi sideways ROM still being selected.

## Byte-level replacement

The published menu contains this eight-byte sequence:

```text
AD 34 FC    LDA &FC34
09 08       ORA #&08
8D 34 FC    STA &FC34
```

The ROM replaces it with an equal-length sequence:

```text
A9 01       LDA #&01
EA          NOP
EA          NOP
EA          NOP
8D FE FC    STA &FCFE
```

The replacement selects Pi1MHz JIM window 1. Keeping the sequence at eight
bytes preserves every address and relative branch in the downloaded program.

The stock payload also assumes that this selection remains active for its
entire lifetime. That is not a safe assumption on Pi1MHz because the JIM
aperture is shared by firmware services. For the known 2,907-byte payload, the
ROM replaces its three `LDA &FD00,Y` catalogue reads with calls to a small
trampoline at `&1FF0`. The trampoline checks `&FCFE` and selects window 1 only
when another host operation changed it. An unconditional write for every byte
would make Pi1MHz remap the complete JIM page repeatedly and can overrun the
real 1 MHz bus path. The title-selection page write similarly calls a
trampoline at `&1FE0` which selects window 1 before writing `&FCFF`. The patch
is applied only after the payload size and all four original instruction sites
have been verified.

The I/O-processor return trampoline is stored at `&1FD0`, above the published
payload and immediately below the two JIM helpers. It is not stored at `&0900`,
which belongs to filing-system and ROM workspace when ADFS is present.

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
`TITLES` through `*WGET -U`, selects JIM window 1, enters WiCFS, and launches a
title without accessing `&FC34`.
