# 1MHzWifi

This project exposes the Raspberry Pi WiFi stack to an Acorn Electron or BBC
Micro through Pi1MHz. The `1MHzWifi 0.1.18` host ROM presents the applicable
ElkWiFi 0.23 command and OSWORD interface. The Pi implementation runs inside
the Pi1MHz bare-metal kernel; it is not a Linux daemon.

The original ElkWiFi cartridge uses a 16C2552 UART at `&FC30`. An Electron Plus
5 does not forward that address to its 1 MHz connector. This implementation
uses the Pi1MHz services mailbox at `&FCA6-&FCAA`, which is forwarded by the
Plus 5 and is accessible from the Electron I/O processor when a Tube parasite
initiates a command.

## Project status

This is a hardware-test release, not a completed ElkWiFi replacement. The ROM,
both Pi kernel families, and the SD-card bundle build successfully. Automated
tests cover the ROM contract and failure behavior when the Pi service is
absent. The current release still requires regression testing on the Electron,
Plus 5, Pi1MHz, and Tube combinations listed in
[the hardware checklist](docs/hardware-validation.md).

The following command paths are implemented. WiCFS load and execution stay on
the Electron or BBC I/O processor and use only the 1MHz-bus Pi service:

| Area | Implemented behavior |
| --- | --- |
| WiFi | `*WIFI ON`, `*WIFI OFF`, `*LAP`, `*JOIN`, `*JOIN ?`, `*LEAVE`, `*ONLINE`, `*IFCFG`, `*LAPOPT` |
| Network | `*PING`, HTTP `*WGET`, OSWORD `&65` TCP open/send/receive/close |
| Time | NTP-backed `*DATE` and `*TIME` |
| Menu | Persistent `*MENUSRC`; `*MENU` downloads, validates, adapts, and runs the published payload on the I/O processor |
| Storage | `*WGET -U`, `*UEF LOAD`, `*WICFS`, `*REWIND`, `*PRD`, and `*WGET -S` through Pi1MHz JIM windows |
| Diagnostics | `*HELP WIFI`, `*VERSION`, station `*MODE`, bounded missing-service errors |

`*PRINTER`, `*UPDATE`, update `*CRC`, and `*SETSERIAL` are not present. They
depend on cartridge hardware that Pi1MHz does not expose. Unknown OSWORD
functions and the direct flash function return `Not implemented` before they
can reach the inherited UART or flash code.

HTTPS, TLS, and SSH are not implemented. Secure requests fail closed; they are
never downgraded to plaintext.

The release boundary and deliberately unsupported cartridge-only features are
recorded in [TODO.md](TODO.md). Asynchronous scan, DNS, ICMP, NTP, WGET and raw
socket waits are Escape-aware. Cancellation closes active PCBs, invalidates
late callbacks and clears scan state before returning to MOS.

The published ElkWiFi menu contains a direct `&FC34` cartridge bank-selection
sequence. At runtime, `*MENU` replaces that exact eight-byte sequence with an
equal-length call to a Pi1MHz JIM address selector after WGET succeeds and
before it enters host `&E00` through a RAM return trampoline. The code does not
inspect, claim or access a fitted Tube. See
[the MENU runtime adaptation](docs/menu-runtime-patch.md) for the byte-level
contract and failure behavior.

## Hardware-test bundle

The ready-to-copy SD-card image tree is `build/pi1mhz-all/`. The equivalent ZIP
archive is [build/pi1mhz-all-hardware-test.zip](build/pi1mhz-all-hardware-test.zip).
Copy the contents of `pi1mhz-all/` to a FAT-formatted Pi boot partition, then
fit or load `Pi1MHz/ElkWiFi.rom` as an Acorn sideways ROM.

When updating an existing test card, keep its `Pi1MHz.cfg` and saved
`Pi1MHz/ElkWiFi.*` settings. Replace only the kernel used by that Pi and the
host ROM. Release 0.1.18 retains the WiCFS host changes and compressed-UEF Pi
service introduced in 0.1.8, supports zero-byte CFS marker files, preserves a
live WiFi association across host resets, and restores the `WGET -U` contract for
raw paged-RAM data such as the published menu TITLES catalogue. The matched
kernel still provides service command 93 for ZIP and gzip UEF normalization,
so replace both the ROM and the kernel from the same bundle.

Release 0.1.18 also includes the public application ABI repairs. OSWORD `&65` function
4 reads the caller's JOIN block, function 8 preserves the port field across
DNS resolution, and function 9 accepts the original single-connection setup
as a successful no-op. These paths are used by ElkChat and other applications
which call the driver directly rather than issuing star commands.

Release 0.1.18 removes all WiCFS state from `&03E0-&03FF`, the MOS keyboard
input buffer which holds the queued `*REWIND` and `CHAIN ""` launch. Stream
state again uses the original WiCFS cassette-workspace zero-page locations.
Vector ownership and predecessor state is persisted on reserved JIM page
`00:02:00`. Earlier builds used the clamped `&FFF200` selector, which resolves
inside Pi1MHz's top 32 MB `DISC_RAM` allocation and could overwrite BeebSCSI
or ADFS data. Its host copy exists only while installing or releasing WiCFS.
The public driver's page shadow is similarly transient in ROM heap. On reset,
the ROM releases only vector entries which it still owns, so ADFS or DFS can
reclaim their vectors safely.

Release 0.1.18 also corrects the common WiCFS completion path used by `*MENU`
and `*UEF LOAD`. The cassette last-block bit is now tested before the legacy
loader compatibility helper can change the processor flags. A completed file
therefore returns to MOS at its own final block instead of consuming later
files and eventually reporting `End of UEF` or an invalid chunk type.

The bundle does not contain a BeebSCSI disc image. Preserve the card's
`/BeebSCSI0` directory when updating it. A clean card needs at least
`/BeebSCSI0/scsi0.dat` from an existing installation or a BeebSCSI starter
image before ADFS can mount a hard disc. `Pi1MHz/defscsi.cfg` is only the
default geometry description; it is not a disc image.

The bundle contains both required kernel families and all CYW43 firmware used
by the target boards:

| Board | Kernel | WiFi result |
| --- | --- | --- |
| Raspberry Pi Zero | `kernel.img` | No onboard WiFi; `*WIFI ON` reports `Device not found` |
| Raspberry Pi Zero W | `kernel.img` | Supported, CYW43430 firmware included |
| Raspberry Pi Zero 2 W | `kernel7.img` | Supported, CYW43436 firmware included |
| Raspberry Pi 3A+, 3B, 3B+ | `kernel7.img` | Supported, CYW43430/CYW43455 firmware included |

There was no production Pi Zero 2 without wireless, nor a Pi 3A without the
plus suffix. The nearest real targets are Zero 2 W and 3A+, listed above.
On `kernel7.img`, the driver distinguishes the original Pi 3B's BCM43430 from
the Zero 2 W's BCM43436 by SOCRAM revision and from the 3A+/3B+'s BCM43455 by
chip ID. The Pi 3B/Zero W NVRAM is the calibrated Raspberry Pi board file, not
the generic placeholder configuration.

Release hashes:

```text
1MHzWifi ROM 9f1a95afce028bcf4535b18c33b24f280ebbf1b010588df3c7adfd72912e5e06
kernel.img   81d3446e1da6c2747ace14f1586d68c57ba222b9981af398fbbfd7277e44332a
kernel7.img  7ddc1fe15d6417488272fee5b6a27c29f83ca381ef746d0ebf8d2a3633e8163e
bundle ZIP   24ed7c84e0abb916d28c45bc1296415903a759cf8998de0a6fd3f6a3ac0109d6
```

The same values are provided in `SHA256SUMS` for automated verification.

## Configuration

The installer preserves active values already present in `Pi1MHz.cfg`. The
JIM transport must remain at its standard 1MHz-bus address, and the following
optional keys provide initial settings:

```ini
Rampage_addr=0xFD
wifi_ssid=MyNetwork
wifi_password=secret
wifi_security=auto
elkwifi_menu_url=http://acornelectron.nl/uefarchive/MENU
elkwifi_utc_offset_minutes=0
```

`wifi_security` accepts `auto`, `open`, `wep`, `wpa`, or `wpa2`. A profile
saved by `*JOIN` takes precedence over the initial WiFi settings. A URL saved
by `*MENUSRC` takes precedence over `elkwifi_menu_url`, which in turn takes
precedence over the compiled default URL. The UTC offset is expressed in
minutes east of UTC. Use `0` for GMT and `60` for BST.

`*UEF LOAD <filename>` reads a UEF image from the currently selected MOS filing
system, including ADFS, DFS, or MMFS, into the WiCFS JIM window. Raw UEF,
gzip-compressed UEF, single-entry ZIP containing UEF, and ZIP containing a
gzip-compressed UEF are recognized by their contents. CRC and expanded-size
checks run on the Pi before launch. The normalizer uses the host-visible JIM
window at `&010000`, not Pi1MHz's private disc-memory base. It then selects
the tape filing system, installs WiCFS, runs `*REWIND`, and executes `CHAIN ""`
without further input. The setup and launch are queued in two stages so they
fit the Electron keyboard buffer. The expanded UEF may contain at most `&FFFE`
bytes because the last two bytes of the 64 KiB window hold its length.
The same normalization is applied to `*WGET -U`, including MENU title
downloads, and the success line identifies the detected format.

Credentials and saved settings are plaintext files on the FAT partition.
Protect the card and do not publish production credentials in bug reports.

## Build from source

The complete, reproducible procedure is in
[Building and release hygiene](docs/building.md). In summary, two clean
upstream source trees are required:

- ElkWiFi commit `7bf366c97bec18bd238963c95e6f2aa6893cdb3a`
- Pi1MHz commit `8468a38f63b25785007a50912a3b32a596db8ff9`

Build the host ROM with BeebAsm:

```sh
git clone https://github.com/hoglet67/ElkWiFi.git
git -C ElkWiFi checkout 7bf366c97bec18bd238963c95e6f2aa6893cdb3a
./rom-side/build_rom.sh /path/to/ElkWiFi
```

Build both Pi kernel families with Arm GCC 13 or later:

```sh
git clone --recursive https://github.com/dp111/Pi1MHz.git
git -C Pi1MHz submodule update --init --recursive
git -C Pi1MHz checkout 8468a38f63b25785007a50912a3b32a596db8ff9
./pi-side/install_bundle.sh /path/to/Pi1MHz all
```

The installer modifies the supplied Pi1MHz checkout. Keep both upstream
checkouts outside this repository and use a path without spaces. This avoids
an upstream Pi1MHz CMake quoting limitation and prevents generated source trees
from accumulating in the project workspace.

The root `build.sh` verifies the size and SHA-256 of the already-built ROM. It
does not fetch or compile either upstream project.

## Test

```sh
./build.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
unzip -t build/pi1mhz-all-hardware-test.zip
```

The test suite checks ROM identity, command presence, mailbox addressing,
safe rejection of unsupported functions, WGET, WiCFS host-only execution,
cancellation, configuration integration, and the absence of retired
UART/flash and Linux bridge code. The Pi1MHz services, net and web parser
suites also run under ASan and UBSan during release validation. WiCFS treats
Pi1MHz strictly as a 1MHz-bus service and never transfers through an optional
Tube.

Elkulator smoke-test captures are under `tests/elkulator/screenshots/`. The
earlier 0.1.16 harness confirmed that the ROM and ACP 1770 DFS could boot
together. The 0.1.18 WiCFS correction must repeat that emulator and
hardware gate before release.
Elkulator's emulated expansion ROM becomes unavailable after `*TAPE`, so it
cannot provide an authoritative end-to-end WiCFS result for this AP5 setup.
`*UEF LOAD` from DFS, post-WiCFS DFS restoration, WiFi association, HTTP
transfer, AP5 forwarding and Tube coexistence remain hardware gates.

Real hardware with earlier ROMs loaded the first Zalaga and Chuckie Egg files
but sometimes returned to the BASIC prompt after `CHAIN ""`. An instrumented
0.1.18 Elkulator run reconstructed the first Zalaga CFS payload and proved that
all 1,518 bytes loaded at `PAGE` match the UEF data exactly. It also confirmed
that BASIC continues into the loaded program and that WiCFS leaves the caller's
OSFILE control block unchanged. The remaining Electron, Plus 5, BeebSCSI and
Tube-coexistence cases are therefore explicit hardware release gates rather
than assumptions derived from the earlier symptom.

## Documentation

- [Architecture](docs/architecture.md)
- [Building and release hygiene](docs/building.md)
- [Command reference](docs/commands.md)
- [MENU runtime adaptation](docs/menu-runtime-patch.md)
- [Pi1MHz integration](pi-side/README.md)
- [Hardware validation](docs/hardware-validation.md)
- [Implementation backlog](TODO.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
