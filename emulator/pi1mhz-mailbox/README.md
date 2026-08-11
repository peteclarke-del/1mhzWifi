# Reusable Pi1MHz Mailbox Emulator

This directory is a standalone C component for adding the Pi1MHz services/JIM
device to 8-bit Acorn emulators. It has no dependency on the host tools or on an
emulator's CPU/video implementation. The network backend links with zlib for
the same gzip and ZIP UEF formats accepted by the Pi firmware.

Run the host tests from this directory with `make test`. The `integrations`
directory contains emulator-specific adapters. The core device and backends do
not include emulator CPU or display code.

## Emulated hardware

- `&FCA6-&FCA8`: 24-bit byte-mode JIM address
- `&FCA9`: byte-mode data with address auto-increment
- `&FCAA`: services command/result register
- `&FCFD-&FCFF`: the Pi1MHz core's Rampage page selector, high/mid/low
- `&FD00-&FDFF`: selected 256-byte Rampage page
- One shared, zero-filled 16 MiB JIM allocation behind both apertures
- Deferred command dispatch with an observable `NET_BUSY` result
- Pi1MHz FAT raw-sector commands 0 and 1 for MMFS and MMFS2

The page selector is 24 bits like the hardware. This initial allocation covers
pages `&000000-&00FFFF`; reads above it return `&FF` and writes are ignored.
The component can later be given a larger allocation without changing either
register ABI.

## Network backends

`pi1mhz_net_backend_create()` accepts:

- `fixture`: deterministic fragmented reads, partial writes and SSH/Telnet
  streams for CI, including managed SSH commands 94-100.
- `live`: non-blocking host TCP sockets for `TCP://` and `TELNET://` URLs.

Commands 60-63 (`URL_OPEN`, `URL_READ`, `URL_WRITE`, `URL_CLOSE`) are
implemented in both modes. Secure random is available in both modes. The
fixture models managed SSH deterministically; when installed with
`PI1MHZ_WOLFSSH_PREFIX`, the live backend implements commands 96-100 using real
wolfSSH, including public-key and ephemeral password authentication. The
dispatch callback keeps the device independent of either backend.

Control selector `&FF` implements the 1MHzWifi menu services and command 93
UEF normalization. Raw, gzip, ZIP and ZIP-contained gzip inputs are normalized
in the AP5-visible JIM window at `&000000`, with length and CRC validation matching the Pi-side
contract. Secure random uses command 95, so command 93 is unambiguous on every
selector.

## Elkulator adapter

The Elkulator-specific patch record is
[`integrations/elkulator/TECHNICAL.md`](integrations/elkulator/TECHNICAL.md).
Distribute this complete mailbox directory, not only the integration
subdirectory, because the installer copies the reusable device and backend
sources into Elkulator.

Install into a disposable or maintained Elkulator source tree with:

```sh
integrations/elkulator/install.sh /path/to/elkulator
```

The installer copies the standalone sources and applies the mailbox,
ROM-layout, scripted-key and AP5 Tube patches. The mailbox device is disabled
unless selected:

```sh
PI1MHZ_MAILBOX=fixture ./elkulator
PI1MHZ_MAILBOX=live ./elkulator
```

Optional variables:

- `PI1MHZ_TRACE=/path/trace.tsv`: record open/read/write/close traffic.
- `PI1MHZ_EXIT_ON_CLOSE=1`: exit after the client closes, useful for CI.
- `PI1MHZ_SD_IMAGE=/path/card.img`: expose a raw FAT SD-card image through
  Pi1MHz FAT commands 0 and 1. This is the path used by the official
  Pi1MHz-specific MMFS ROMs. The image is writable when host permissions
  allow it and otherwise reports the Pi1MHz write-protect result.

The adapter gives the Pi1MHz device priority over Elkulator's legacy JIM and
ElkWiFi handlers only while `PI1MHZ_MAILBOX` is enabled.
It deliberately does not forward `&FCFD` or `&FCFE` to the mailbox. An
unmodified AP5 forwards only `&FCFF` from that selector group, so Elkulator's
Pi1MHz integration exposes the same 64K JIM window as the real Electron setup.

The integration also makes command-line ROM selection deterministic before
the MOS service-ROM scan. Explicit ROMs in banks 0 and 1 take precedence over
Elkulator's legacy cartridge mapping. Any sideways bank can be made writable
with `-ram <bank>`, for example `-ram 6 -ram 7` for a 32 KB expansion. These
are emulator configuration controls. The 1MHzWifi ROM does not assume fixed
ROM or RAM bank numbers.

The installer also adds `-autokeys <sequence>` for repeatable hardware-level
tests. A sequence is a comma-separated list of `delay:keycode` entries. Codes
`2000` and `2001` press and release Shift, which lets tests type the Electron
`*` character as Shift plus `@` without relying on the host keyboard layout.

Pass `-tube6502 /path/to/6502tube_120.rom` to configure the external AP5 Tube
used by the physical PiTubeDirect profile. The Tube ULA and 3 MHz 65C02 are
ready before the MOS service-ROM scan, and RH Plus starts the parasite during
cold boot without a manual `*TUBE ON`. See
`integrations/elkulator/tube/README.md` for scope and licence details.
