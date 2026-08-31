# 1MHz-WiFi host network tools

Native 6502 network programs for BBC Micro, Acorn Electron and compatible
Acorn MOS machines fitted with Pi1MHz. The programs are distributed together
on a bootable 200 KiB DFS `.ssd` image and call Pi1MHz's services mailbox
directly. They do not require the 1MHz-WiFi/ElkWiFi service ROM.

## Current programs

- `TELNET host [port]`: interactive Telnet client using Pi1MHz's `TELNET:`
  adapter and a native VT100 parser. Port 23 is the default. Press
  `Ctrl-]` to disconnect.
- `SSH user@host [port]`: interactive SSH-2 VT100 client over the versioned
  Pi1MHz secure-service ABI. It displays and confirms unknown host-key
  fingerprints, requests atomic known-host persistence on the Pi SD card,
  tries a Pi-resident Ed25519 identity, falls back to a hidden password prompt
  when the key is rejected, and exchanges the decrypted shell byte stream
  without exposing private keys or session keys to the 6502.
- `SFTP user@host [port]`: interactive SFTP client using the same key,
  password and known-host policy. `PWD`, `CD`, `DIR`/`LS`, `GET`, `PUT`,
  `DELETE`, `MKDIR`, `RMDIR` and `QUIT` are implemented. Local file data goes
  through MOS `OSFIND`, `OSBGET` and `OSBPUT`; the client neither claims nor
  transfers through an installed Tube.
- `NETMENU`: concise on-disc launcher/help screen.

- `HWDTEST`: hardware/emulator alignment diagnostic. It reports the MOS
  machine and Tube state, memory limits and key vectors, then checks the
  `&FCA6-&FCA9` cursor/data pair, a Services JIM block and secure capability
  command 94. It finally invokes `*ROMS` and `*VERSION` for a complete profile.
  Its D4 JIM probe uses `&FFEE00`; `&FFEF00-&FFEF19` is reserved for WiCFS and
  is never modified. D4 reports the standard and extended WiCFS vectors, their
  ROM owners, and all 26 bytes of the persisted WiCFS record. It does not
  access the Tube or write to a filing-system volume.

The D4 hardware diagnostic brackets OSBYTE calls and prints the raw capability
bytes. The reference mailbox emulator produces these diagnostic lines:

```text
Loader OSHWM=&0800 HIMEM=&1D00
FCA9 req 00 F0 FF <= 5E
FCA6-9 after: 01 F0 FF 5E PASS
Addressed JIM block: PASS
FCA9 callback ACK: PASS
Secure CAPS result=&00
CAPS 1-5: 01 01 07 B8 88
CAPS 6-10: 01 01 4E 54 53
```

Run `*HWDTEST` unchanged in Elkulator and on physical hardware. It pauses
after the machine/vector report and again after the state/mailbox report so
each capture fits the physical 40-column display without scrolling. It then
allows the machine/vector values, state/mailbox values, ROM list and version
response to be captured as four screens. Any differing register byte or
`FAIL` identifies the first
boundary where the emulator and live bus disagree. Machine, memory, vector and
ROM-list values vary with the host configuration and must be compared as a
complete profile.

Unimplemented commands are not placed on the released SSD. Planned `HGET`
and Viewdata clients remain in the engineering roadmap until they have
complete implementations and functional tests.

`PING` and `NSLOOK` are ROM commands and are deliberately absent from the
NetTools SSD. Plain interactive FTP is also ROM-resident. NetTools supplies
SFTP because its larger client and authentication flow do not fit the ROM
compatibility surface cleanly.

Each public command is a small bootstrap at `&FFFF2000`. This is above the
measured DFS OSHWM of `&1F00`. On the photographed MMFS/ADFS profile, where
HIMEM is `&1D00`, it initially occupies writable display RAM. The bootstrap
preserves the command tail and verifies HIMEM against the exact end of its
corresponding main image before running that image at `&FFFF2200`. It retains
the current display mode when the screen boundary already leaves enough room,
and selects MODE 4 only as a safe fallback. MODE 4 screen memory starts at
`&5800`, so clearing that fallback screen does not erase either stage.

The `&FFFF` address prefix keeps both stages on the I/O processor when a Tube
is active. Neither stage claims nor uses the parasite. Every main entry point
repeats the OSHWM and HIMEM checks before using the mailbox. An OSHWM above
`&2000` is rejected as an unmeasured profile. This bound is explicit because a
program cannot discover a conflicting OSHWM until MOS has already loaded it.

The address choice is based on Acorn's memory model, not an emulator-specific
exception. The Electron documentation gives MODE 4 screen memory as
`&5800-&7FFF`, and Acorn's Master Tube documentation reserves `&FFFF0000` to
`&FFFFFFFF` for host addresses. See the
[Electron screen-memory table](https://www.acornelectron.co.uk/eug/38/a-pro3.html)
and the
[Advanced Master Reference Manual](https://www.bbproj.org/files/computer/machine-bbc-micro/manuals/advanced-master-reference-manual.pdf).

## Requirements

- The combined 1MHz-WiFi Pi1MHz firmware, containing the native net service
  and managed secure service commands 94-113.
- `net_enable=1` in `Pi1MHz.cfg`.
- Configured, associated WiFi.
- Host OSHWM no higher than `&2000`. The bootstrap preserves a suitable current
  mode, otherwise selects MODE 4, and requires writable memory from `&2200`
  through the exact end of the requested tool.
  No loader reserves the unused part of the assembly guard up to `&5800`.

## Repository layout

- `src`: 6502 clients, shared assembly and DFS image definitions.
- `tests`: SSD, CPU-emulation and end-to-end integration tests.
- `../pi-side`: the complete Pi1MHz patch package and firmware installer.
- `../emulator/pi1mhz-mailbox`: standalone mailbox/JIM emulator package and
  Elkulator adapter.
- `docs`: shared ABI and roadmap documentation.

The Pi firmware package and mailbox emulator remain separate components within
this repository so their changes can be reviewed independently.

## Build

Requires BeebAsm, GNU Make, Python 3 and the pinned py65 emulator dependency:

```sh
make emulator-deps
make test
```

Output: `build/nettools.ssd`.

Use `make clean` to remove build outputs. Use `make distclean` to also remove
the local py65 installation and Python bytecode caches.

`make test` extracts the host tools from the finished DFS image and executes
those exact payloads on py65 with emulated MOS entry points and a byte-accurate
Pi1MHz services mailbox/JIM fixture. It tests fragmented network input, forced
partial writes, keyboard sequences, VT100 rendering, managed SSH shell I/O,
unknown-host acceptance, clean close and missing-service failure.
Assembly/catalogue-only checks are not considered a functional test.

### Real-hardware debug tracing

`TELNET`, `SSH`, `PING` and `NSLOOK` share the `pi1mhz_net.asm` command/result
dispatch loop over the `&FCA6`-`&FCAA` mailbox registers. `make debug` builds
a second disc image, `build/nettools-debug.ssd`, from `NET_DEBUG=1` object
files (`build/TELNET-debug`, `build/SSH-debug`, `build/PING-debug`,
`build/NSLOOK-debug`) alongside the normal `build/nettools.ssd`, without
rebuilding or overwriting it. Booting the debug disc prints the mailbox
command/result sequence on screen: `>` followed by two hex digits before the
shared cursor is selected and the command is written to `SERVICE_DATA`, and
`<` followed by two hex digits after
each poll of `SERVICE_COMMAND` returns a non-busy result (including every
intermediate `&01`/pending poll during a bounded `net_dispatch_wait` retry
loop). Command and result byte values match `docs/secure_service_abi.md` and
the `NET_CMD_*`/`SEC_CMD_*` constants in `src/common/mos.inc` and
`src/common/pi1mhz_secure.asm`.

```sh
make debug
```

Printing before cursor selection is required. MOS output may enter another ROM
which also uses FCA6-FCA9. The executable debug regression deliberately
redirects the cursor on every MOS output call and verifies that NSLOOK still
dispatches and returns an address.

This is a physical-hardware diagnostic only; `build/nettools.ssd` (built by
plain `make`/`make test`) is never affected by it and stays the release
configuration. The debug disc's extra trace output is written directly to the
current screen mode, so it interleaves with VT100 rendering and will not
match the golden-screen assertions in `tests/test_emulated_clients.py`. That
suite is only expected to pass against the default build.

The reusable Elkulator integration under
`../emulator/pi1mhz-mailbox/integrations/elkulator` adds the Pi1MHz services
mailbox at `&FCA6`-`&FCAA` and the shared JIM aperture at `&FCFD`-`&FDFF`.
Its control selector implements 1MHz-WiFi menu settings and UEF command 93.
The UEF path recognizes raw, gzip and single-entry ZIP inputs, validates the
container and CRC, updates the JIM length trailer and keeps command 93 distinct
from secure random on socket selectors.

The executables are host-resident transients. With or without a Tube they use
the standard host-utility convention and return through the active OSCLI call
with `RTS`. They neither re-enter the current language nor modify BASIC's
program area while returning.

The released binaries deliberately target the 32K host baseline. A future
optional display mode may use runtime-detected host shadow or writable
sideways RAM for an 80-column screen and scrollback, while retaining the
current 40-column path when no safe provider exists. A separate 6502 Tube
edition may use parasite RAM, but only behind a small host-resident gateway:
the gateway remains solely responsible for OSWORD, JIM and Pi1MHz bus access.
The standard binaries will never claim a fitted Tube, and non-6502 parasites
require distinct ports.
Install it into a clean Elkulator source tree with:

```sh
../emulator/pi1mhz-mailbox/integrations/elkulator/install.sh /path/to/elkulator
```

Set `PI1MHZ_MAILBOX=fixture` for the deterministic test backend. For ROM or
client tests which need pre-existing JIM content, set `PI1MHZ_JIM_IMAGE` to a
binary image and optionally set `PI1MHZ_JIM_IMAGE_ADDRESS` to its base address
(decimal or C-style hexadecimal, default zero). The integration rejects images
which do not fit in the emulated 16 MiB JIM RAM.

The full Electron/DFS gate builds a disposable patched Elkulator tree and boots
dedicated TELNET and SSH images:

```sh
make test-elkulator
```

The gate runs both clients with the AP5 Tube disabled and enabled and uses the
calibrated physical FIQ scheduler profile. Set `ELK_ROMS_DIR` to the directory containing
`electron_tube.zip` when that archive is not in the sibling `elk_roms`
directory. The archive must contain `6502tube_120.rom`.

It verifies URL/SSH opens, fragmented incoming data through JIM, forced
partial writes, the interactive SSH shell path and clean closure. A release
must pass `make test`, `make test-elkulator`, `make test-ssh-real` and
`make test-elkulator-ssh-real` before hardware testing. The real-server gates
prove Ed25519 authentication, PTY/shell setup, encrypted bidirectional data,
changed-host rejection and bad-key authentication failure.

The assembled-SSD real-server run has a 90-second default deadline under the
conservative mailbox timing profile. Set `ELKULATOR_SSH_TIMEOUT` to override
it. A failed run retains its disposable Elkulator tree and mailbox trace under
`/tmp/pi1mhz-elkulator-real.*` and prints that path before exiting.

The current assembled-SSD real-server gate completes public-key authentication,
PTY allocation, shell input/output and close without returning `&2D`. In the
secure-service ABI, `&2D` is reserved for genuine authentication failure. A
valid password fallback or Pi-resident key must not report it.

Install the complete combined package into the pinned Pi1MHz checkout and
build both supported kernels from the repository root with:

```sh
ARM_GCC=/path/to/arm-none-eabi-gcc \
WOLFSSL_SOURCE=/path/to/wolfssl \
WOLFSSH_SOURCE=/path/to/wolfssh \
  ./pi-side/install_bundle.sh /path/to/Pi1MHz all
```

The installer pins wolfSSL commit `65836b4` and wolfSSH commit `c2d1698`.
For offline installation, point `WOLFSSL_SOURCE` and `WOLFSSH_SOURCE` at
checkouts of those exact commits.

The native clients use Pi1MHz handle 0, command page `&FFF000`, RX buffer
`&020000` and TX buffer `&020100`. They poll the net service and leave its
level-triggered nIRQ support disarmed.

## SSH security boundary

The 6502 owns command parsing, the host-trust decision, password entry,
terminal input/output and VT100 behavior. The Pi owns the wolfSSH
transport, cryptography, authentication and channel engine. Private keys live under
`Pi1MHz/ssh/` on its SD card and never cross JIM. This is the practical
security boundary for a 1/2 MHz 6502: implementing modern X25519, Ed25519,
AES-CTR and constant-time packet authentication in application RAM would be
both unreasonably slow and unsafe.

Password fallback is temporary: input is not echoed, the JIM
transfer and 6502 input buffer are wiped immediately, the Pi copy is wiped on
success or failure, and no password is written to the SD card or trace.

The live emulator and Pi firmware use the same mailbox ABI and wolfSSH trust,
authentication and channel model. The Pi provider uses raw lwIP callbacks,
the BCM hardware RNG and FatFs; Pi 1/Zero `kernel.img` and Pi 2/3
`kernel7.img` both cross-build successfully. Hardware execution remains the
next gate after the emulator tests, so retain the original firmware image for
rollback during first-device testing.

`PING` and `NSLOOK` are ROM-resident commands and are not duplicated on
`nettools.ssd`. SFTP is included on the SSD, while plain FTP is ROM-resident.
Planned later SSD tools include `HGET` HTTP/HTTPS and `VIEWDAT`. Viewdata
will reuse the stream transport but has its own MODE 7/Prestel renderer and
key mapping rather than passing its data through the VT100 renderer.

See [the implementation plan](docs/ssh_https_plan.md).
