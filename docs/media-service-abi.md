# Media service ABI

This records the interface for `*UEF CAT`, `*UEF EXTRACT`, `*SSD CAT`,
`*SSD EXTRACT`, `*SSD LOAD`, `*SSD CLOSE` and the Pi-hosted disc. It is a
design record, not a description of shipped behaviour: only the decoder in
`pi-side/pi1mhz-516a267/overlay/src/media_catalogue.c` exists so far.

## Division of work

The host ROM stays a thin client. Every container format decision - UEF chunk
walking, CFS block grouping, cassette CRCs, DFS catalogue decoding, disc
geometry - is made on the Pi, where there is room to validate it and where it
can be unit tested on a build host. The ROM sends a command, renders returned
text, and issues MOS filing calls on the host's behalf.

This is not only a space argument, although the space argument is real: the
16 KiB ROM has a few hundred spare bytes. It is also a correctness argument.
The Pi already normalises raw, gzip and ZIP containers for `*UEF LOAD`, so
putting catalogue and extraction beside that normalisation keeps one parser
rather than two that can disagree.

The host must still own everything MOS owns. Load and execution addresses,
OSFILE and OSGBPB calls, filing-system selection, directory context and error
reporting stay on the Acorn side. The Pi never learns which filing system the
host is using and never sees a MOS control block.

## Command allocation

Pi1MHz services command numbers are allocated as follows. 80 to 119 are
already in use.

| Range | Service |
| --- | --- |
| 80-93 | ElkWiFi station, network, `*ONLINE` and UEF normalisation |
| 94-100 | Secure service, SSH |
| 101-113 | Secure service, SFTP |
| 114-119 | Interactive FTP |
| 120-127 | Media service, reserved by this document |

Within the media range:

| Command | Name | Purpose |
| --- | --- | --- |
| 120 | `MEDIA_OPEN` | Identify and open a container, returning a handle and kind |
| 121 | `MEDIA_CAT` | Return catalogue text one line at a time |
| 122 | `MEDIA_INFO` | Return one entry's name, load, execution address and length |
| 123 | `MEDIA_READ` | Stream one entry's data through the public JIM window |
| 124 | `MEDIA_CLOSE` | Release the handle |
| 125 | `MEDIA_MOUNT` | Present a container as the active filing system |
| 126 | `MEDIA_FSOP` | Proxy one MOS filing operation against a mounted container |
| 127 | `MEDIA_STORE` | Create, select, size and format the Pi-hosted disc |

An older kernel answers an unallocated command with `Unsupported`, so a ROM
built for this ABI must degrade cleanly rather than hang, exactly as the
command 58 receive acceleration already does.

## Transport

Catalogue and extraction reuse the existing incremental window protocol rather
than inventing a second one. `MEDIA_READ` fills the AP5-visible public JIM
window in `&FF00`-byte windows with the length trailer the ROM already
understands, so a file larger than the legacy 64 KiB aperture is delivered in
successive windows. Text from `MEDIA_CAT` is returned through the ordinary
paged command response used by `*ONLINE` and `*VERSION`.

## `*SSD LOAD` and the Pi-hosted disc

`*SSD LOAD` mounts an image so that later `*CAT`, `LOAD`, `RUN` and `CHAIN`
work against it, and runs `!BOOT` when the image's boot option asks for it. If
there is no `!BOOT` the command leaves the image mounted and returns to the
prompt. `*SSD CLOSE` releases it and restores the previous filing system.

Mounting means MOS routes FILEV, ARGSV, BGETV, BPUTV, GBPBV, FINDV and FSCV
somewhere, and MOS can only route them to 6502 code on the host. The Pi cannot
answer a MOS filing call directly. The host side is therefore a call
marshaller: it decodes the MOS control block, sends the operation as
`MEDIA_FSOP`, streams the result back, and returns MOS-correct registers and
errors. All catalogue, free-space and geometry logic stays on the Pi.

Because the vectors must survive whatever the loaded program does to low
memory, a mounted container inherits the same vector-survival problem that
`docs/hardware-validation.md` records for WiCFS. The mount path must reuse
whatever mechanism WiCFS settles on rather than introducing a second one.

The Pi-hosted disc is a DFS-format image held by the Pi and addressed through
exactly the same `MEDIA_MOUNT` and `MEDIA_FSOP` path as a mounted `.SSD` file.
That is deliberate: one filing-system proxy serves both, and `*UEF EXTRACT`
into the Pi-hosted disc then needs no additional host code. Backing store is a
file on the Pi's SD card, so its contents survive a power cycle; a RAM-backed
mode remains possible later for speed, at the cost of that persistence. Size is
configurable through `Pi1MHz.cfg` with a default that leaves the card's
existing contents alone.

## Safety rules

- The Pi treats every container as untrusted input. A malformed or truncated
  image yields the entries that could be recovered and a non-zero issue count,
  never an out-of-bounds read.
- `*SSD EXTRACT` and `*UEF EXTRACT` write through the active MOS filing system
  using the recorded load and execution addresses. They must refuse rather than
  silently truncate when a name cannot be represented on the target filing
  system.
- No command may reserve a sideways RAM bank, assume a Tube, or require one.
- The Pi-hosted disc must never be the implicit destination for a command that
  did not name it.
