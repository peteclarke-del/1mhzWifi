# 1MHz-WiFi host ROM

The host sideways ROM for 1MHz-WiFi: a 16 KiB image for a BBC Micro or Acorn
Electron that talks to Pi1MHz over the 1 MHz bus.

This project extends dp111's Pi1MHz rather than forking it. The network ROM is
Pi1MHz's `beeb/1mhz-wifi`, taken whole at the commit pinned in
`../pi-side/upstream.env`, and this directory holds only what is added to it:

- `1mhz-wifi/patches/`: this project's changes to upstream's files, applied
  in order. Each patch says in its header what it does and why.
- `1mhz-wifi/src/`: sources upstream does not carry: `*FTP` (built only with
  `INCLUDE_FTP=1`), the filing
  system image's root `1mhzwicfs.asm`, and the WiCFS and UEF sources around
  the inherited file. The build refuses a file here that shadows one of
  upstream's, because that would be a fork of it.
- `inherited/patches/`: what still derives from ElkWiFi 0.23 and, through it,
  Martin Barr's UPCFS. All of it applies to one file, `wicfs.asm`.
- `inherited/TECHNICAL.md`: transport, ABI and loader change record.
- `build_rom.sh`: fetches the pinned upstreams, composes the source tree and
  assembles. See `1mhz-wifi/README.md`.
- `candidates/`: changes kept for reference that are not in the build.

dp111's `build-merged.sh` fetches this repository to build his merged image.
It reads the patch order from the `for patch_name in` line of `build_rom.sh`,
the stack in `inherited/patches/`, and five sources from `1mhz-wifi/src/`, so
those paths and that line are an interface and should not move.

Read `inherited/README.md` before reusing anything: two upstream authors have a
claim on `wicfs.asm` and neither has stated terms.

## Where the ROM keeps its workspace

Both images keep their scratch inside their own image, packed against the top
of the bank: 32 bytes of driver state and the error block at `&BDDE`, the
writable-image flag and the connection status just above it, then a 256 byte
parameter heap at `&BE00` and a 256 byte string buffer at `&BF00`.

It used to live in host memory at `&900`, `&A00` and `&D90`. The OS owns all
three on every machine this ROM supports: `&0900` is the RS423 output buffer
and ENVELOPEs 5 to 16, `&0A00` is the CFS/RFS/RS423 input buffer, and `&0D90`
is VFS and AMX mouse workspace followed by the extended vector table at
`&0D9F`. The service driver was storing its UEF stream generation at `&0DAF`,
four bytes inside that table, which kills the next OS call made through a
claimed vector. `rom-side/check_rom_memory.py` is the check that catches this
class of fault; it is dp111's, extended for two roots and the EPROM build, and
it runs in the ROM build and in `make test`. dp111's own copy runs against
upstream's tree in `make test-pi-integration`.

The consequence is that the bank has to be writable, which it is whenever
Pi1MHz serves the image into sideways RAM. Each image probes its own workspace
at reset, writing `&A5` and then `&5A` so a floating bus cannot pass, and
records the answer. If the bank is read-only, the ROM declines its commands
rather than writing into memory it does not own; see below.

## The EPROM build

For a real ROM there is no writable image, so the build produces a second pair
of images from the same sources with `WS_IN_IMAGE=0`:

| image | workspace | for |
| --- | --- | --- |
| `1mhz-wicfs.rom`, `1mhz-wifi.rom`, `1mhz-wicfs-only.rom` | in the image, `&BDDE` up | sideways RAM, which is what Pi1MHz serves |
| `1mhz-wifi-eprom.rom`, `1mhz-wicfs-only-eprom.rom` | three pages of host RAM, claimed | a burnt EPROM |

The EPROM build keeps the three bases as assembly-time constants and simply
points them at host RAM. That is what lets one set of sources serve both: the
ninety-odd symbols derived from `heap`, `strbuf` and `netprt` stay absolute
addresses, rather than every reference to them having to be reached through a
pointer.

Those pages are claimed from the OS at service call 1, not assumed, so the
build cannot repeat the fault the in-image layout was introduced to fix. The
network image takes `&0E00-&10FF` and the filing system image `&1100-&13FF`,
so two of them fitted together do not collide, and PAGE rises by three pages
per fitted image. That cost is why this is a separate build rather than the
default: it would otherwise be paid on every machine, including the ones where
the workspace costs nothing at all.

### Fit the network image in the higher bank

The two EPROM images take fixed ranges, and the MOS issues service call 1 from
bank 15 downwards, so the one serviced first must be the one wanting the lower
range. That is the network image at `&0E00`, followed by the filing system
image at `&1100`, which gives PAGE `&1400` with both fitted. Measured, not
reasoned: PAGE reads `&0E00` with no EPROM image fitted, `&1100` with the
network image alone, and `&1400` with both in that order.

Fitted the other way round the filing system image claims first and takes Y
past `&0E00`, so the network image can no longer prove its own range is free
and claims nothing. It then prints `needs sideways RAM` under its banner and
declines its commands, which is the safe outcome rather than the right one.
Both images print that line when their claim does not succeed.

Two things guard the claim. The range is only taken if service call 1 reports
it still free, and nothing is written when it is not. And because claimed host
RAM is not owned the way an image is, a two-byte signature is stamped beside
the flag and checked on every command, so workspace another ROM has since
taken is refused rather than used.

## What happens when the workspace is not there

The command entry declines the service call: A is left at 4 and nothing is
pushed, so the MOS carries on offering the command to lower-priority ROMs and
reports `Bad command` if nobody takes it. The reason is printed once at reset,
under the banner, as `1MHz-WiFi 0.1.67 needs sideways RAM`.

It raised an error at first, which the emulator showed to be wrong twice over.
The test sits ahead of the command table search, so the ROM answered for every
unrecognised command on the machine rather than only its own, and `*DISC` with
no DFS fitted stopped working. And the error was a `BRK` with its message
inline in the bank, which the MOS cannot read back once it has paged the ROM
out: the screen filled with whatever the incoming ROM held at those addresses,
which on an Electron is BASIC's keyword table. Upstream still raises the
error, because Pi1MHz only ever serves the ROM into sideways RAM and never
reaches the path, so the fix is carried as
`1mhz-wifi/patches/read-only-bank.patch` and is a candidate to offer upstream.


## Building

See `1mhz-wifi/README.md` for the images and `../docs/building.md` for the
procedure. In short, `./build_rom.sh` fetches Pi1MHz and ElkWiFi at their
pinned commits into `../.build-upstream`, composes the sources in
`../.build-rom`, and writes every image to `../build/pi1mhz-all/Pi1MHz/`.
`../build/elkwifi_pi1mhz.rom` is kept as a compatibility symbolic link to
`1mhz-wifi.rom`. The release build checks the size and recorded SHA-256 of
each image; physical Electron, filing system and Tube coexistence tests remain
separate acceptance gates.
