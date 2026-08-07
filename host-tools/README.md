# 1MHzWifi host network tools

Native 6502 network programs for BBC Micro, Acorn Electron and compatible
Acorn MOS machines fitted with Pi1MHz. The programs are distributed together
on a bootable 200 KiB DFS `.ssd` image and call Pi1MHz's services mailbox
directly. They do not require the 1MHzWifi/ElkWiFi service ROM.

## Current programs

- `TERM host [port]`: interactive Telnet client using Pi1MHz's hardware-tested
  `TELNET:` adapter and a native VT100 parser. Port 23 is the default. Press
  `Ctrl-]` to disconnect.
- `SSH user@host [port]`: interactive SSH-2 VT100 client over the versioned
  Pi1MHz secure-service ABI. It displays and confirms unknown host-key
  fingerprints, requests atomic known-host persistence on the Pi SD card,
  tries a Pi-resident Ed25519 identity, falls back to a hidden password prompt
  when the key is rejected, and exchanges the decrypted shell byte stream
  without exposing private keys or session keys to the 6502.
- `NETMENU`: concise on-disc launcher/help screen.
- `PING`, `NSLOOK`, `FTP`, `HGET` and `VIEWDAT`: runnable protocol scaffolds
  which currently report that implementation is pending. `VIEWDAT` is the
  seven-character DFS command name for the planned Viewdata client.

The executables have DFS load and execution addresses encoded as `&FFFF1900`.
This makes Tube-aware filing systems load and execute them on the I/O
processor. The applications neither claim nor use a Tube parasite. Without a
Tube, they execute normally at `&1900`.

## Requirements

- The combined 1MHzWifi Pi1MHz firmware, containing the native net service
  and managed secure service commands 94-100.
- `net_enable=1` in `Pi1MHz.cfg`.
- Configured, associated WiFi.
- MODE 4 and memory available from `&1900` to below `&5800`; this is compatible
  with a stock 32 KiB Electron baseline.

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

`make test` extracts `TERM` and `SSH` from the finished DFS image and executes
those exact payloads on py65 with emulated MOS entry points and a byte-accurate
Pi1MHz services mailbox/JIM fixture. It tests fragmented network input, forced
partial writes, keyboard sequences, VT100 rendering, managed SSH shell I/O,
unknown-host acceptance, clean close and missing-service failure.
Assembly/catalogue-only checks are not considered a functional test.

The reusable Elkulator integration under
`../emulator/pi1mhz-mailbox/integrations/elkulator` adds the Pi1MHz services
mailbox at `&FCA6`-`&FCAA` and the shared JIM aperture at `&FCFD`-`&FDFF`.
Its control selector implements 1MHzWifi menu settings and UEF command 93.
The UEF path recognizes raw, gzip and single-entry ZIP inputs, validates the
container and CRC, updates the JIM length trailer and keeps command 93 distinct
from secure random on socket selectors.
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
dedicated TERM and SSH images:

```sh
make test-elkulator
```

It verifies URL/SSH opens, fragmented incoming data through JIM, forced
partial writes, the interactive SSH shell path and clean closure. A release
must pass `make test`, `make test-elkulator`, `make test-ssh-real` and
`make test-elkulator-ssh-real` before hardware testing. The real-server gates
prove Ed25519 authentication, PTY/shell setup, encrypted bidirectional data,
changed-host rejection and bad-key authentication failure.

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
next gate after the emulator proofs, so retain the original firmware image
for rollback during first-device testing.
Planned later SSD tools include implementations of the installed `PING`,
`NSLOOK`, `FTP`, `HGET` HTTP/HTTPS and `VIEWDAT` Viewdata scaffolds. Viewdata
will reuse the stream transport but has its own MODE 7/Prestel renderer and
key mapping rather than passing its data through the VT100 renderer.

See [the implementation plan](docs/ssh_https_plan.md).
