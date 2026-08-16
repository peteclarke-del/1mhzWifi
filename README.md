# 1MHzWifi

This project exposes the Raspberry Pi WiFi stack to an Acorn Electron or BBC
Micro through Pi1MHz. The `1MHzWifi 0.1.52` hardware-test ROM presents the applicable
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

Version 0.1.52 is the current hardware-test build. Earlier 0.1.50 and
0.1.51 timing and WiCFS cursor changes caused physical MENU and local UEF
regressions, so they are not release baselines. The recovered ROM keeps the
0.1.49 WGET and WiCFS transfer paths byte-for-byte, adds the verified local
OSFIND/OSBGET handle repair, then applies a narrowly
scoped settling delay only while the ROM copies ordinary Pi service responses.
That change targets the corrupt `*VERSION` output without changing tape data.
NetTools uses the same bounded settling interval for its own mailbox transfers.

The current ROM has reached animated THRUST gameplay through `*UEF LOAD` with
the Tube disabled and enabled in the maintained Elkulator hardware model. The
live published `*MENU` path has also downloaded and run FrakV2 in both Tube
states. These emulator results protect the recovered game-loading baseline.
Physical validation of `*VERSION`, SSH, MENU, local UEF loading and both Tube
states remains mandatory before this build can be called fixed.

The NetTools applications load at `&1D00` and validate OSHWM and HIMEM at every
entry. If the active screen mode leaves too little application memory, they
select portable MODE 4 and check again. Machine detection is refreshed at
driver entry because the ROM heap is volatile application workspace and cannot
hold a reset-time cache. The bundle retains the BCM43455 7.45.241 firmware used
before the Pi 3A+ DHCP regression. Version 1.0 still requires the public
ElkWiFi OSWORD comparison and the ADFS, DFS, MMFS and TAPE coexistence gates.

The following command paths are implemented. Pi and JIM traffic stays on the
1MHz bus. WiCFS loads into Electron host memory. The launcher uses MOS OSBYTE
`&EA` only to detect whether host BASIC must be entered; it does not claim,
disable or transfer through a fitted Tube. A game remains free to use that
Tube itself:

| Area | Implemented behavior |
| --- | --- |
| WiFi | `*WIFI ON`, `*WIFI OFF`, `*LAP`, `*JOIN`, `*JOIN ?`, `*LEAVE`, `*ONLINE`, `*IFCFG`, `*LAPOPT` |
| Network | `*PING`, HTTP `*WGET`, OSWORD `&65` TCP open/send/receive/close |
| Time | NTP-backed `*DATE` and `*TIME` |
| Menu | Persistent `*MENUSRC`; `*MENU` downloads, validates, adapts, and runs the published payload on the I/O processor |
| Storage | `*WGET -U`, `*UEF LOAD`, `*WICFS`, `*REWIND`, `*PRD`, and `*WGET -S` through Pi1MHz JIM windows |
| Diagnostics | `*HELP WIFI`, `*VERSION`, station `*MODE`, bounded missing-service errors |

The compiled `*MENU` source is Electron-only. On BBC B, B+, Master and
Compact, `*MENU` explains this and asks for a machine-appropriate `*MENUSRC`.
This restriction applies to the default payload, not to WiFi, OSWORD, WGET,
custom menus or NetTools. Platform-sensitive ROM paging uses the documented
OSBYTE `&81` machine query before the driver touches the high JIM selectors.
The result is transient and is not assumed to survive application execution.

`*PRINTER`, `*UPDATE`, update `*CRC`, and `*SETSERIAL` are not present. They
depend on cartridge hardware that Pi1MHz does not expose. Unknown OSWORD
functions and the direct flash function return `Not implemented` before they
can reach the inherited UART or flash code.

The ElkWiFi-compatible ROM does not add HTTPS or TLS to `*WGET`; unsupported
secure URLs fail closed and are never downgraded to plaintext. The separate
native `host-tools/SSH` client uses the managed Pi secure service and wolfSSH.

The maintained upstream changes are grouped by target. ElkWiFi changes live
under `rom-side/elkwifi-0.23/`, and Pi1MHz changes live under
`pi-side/pi1mhz-516a267/`. Each package separates ordered patches from complete
source overlays and records its required upstream commit.

The former 1mhzNetTools project is incorporated under `host-tools/`,
`emulator/pi1mhz-mailbox/` and the central Pi overlay. Its disposition and
validation are recorded in [the merge record](docs/nettools-merge.md).

The release boundary and deliberately unsupported cartridge-only features are
recorded in [TODO.md](TODO.md). Asynchronous scan, DNS, ICMP, NTP, WGET and raw
socket waits are Escape-aware. Cancellation closes active PCBs, invalidates
late callbacks and clears scan state before returning to MOS.

The published ElkWiFi menu contains a direct `&FC34` cartridge bank-selection
sequence. At runtime, `*MENU` replaces that exact eight-byte sequence with an
equal-length call to a Pi1MHz JIM address selector after WGET succeeds and
before it enters host `&E00` through a RAM return trampoline. The menu itself
and all WiCFS transfers remain Electron host code. The ROM does not select,
disable, or transfer data to a fitted Tube. See
[the MENU runtime adaptation](docs/menu-runtime-patch.md) for the byte-level
contract and failure behavior.

## Hardware-test bundle

The ready-to-copy SD-card image tree is `build/pi1mhz-all/`. The equivalent ZIP
archive is [build/pi1mhz-all-hardware-test.zip](build/pi1mhz-all-hardware-test.zip).
Copy the contents of `pi1mhz-all/` to a FAT-formatted Pi boot partition, then
fit or load `Pi1MHz/ElkWiFi.rom` as an Acorn sideways ROM.
The same tree includes `host-tools/nettools.ssd`. Install or select that SSD
through DFS/MMFS when testing `*SSH` or `*TELNET`; replacing the Pi files alone
does not replace host programs already held on another disc image.

When updating an existing test card, keep its `Pi1MHz.cfg` and saved
`Pi1MHz/ElkWiFi.*` settings. Replace only the kernel used by that Pi and the
host ROM. Release 0.1.52 retains the WiCFS changes and compressed-UEF Pi
service introduced in 0.1.8, supports zero-byte CFS marker files, preserves a
live WiFi association across host resets, and restores the `WGET -U` contract for
raw paged-RAM data such as the published menu TITLES catalogue. The matched
kernel still provides service command 93 for ZIP and gzip UEF normalization,
so replace both the ROM and the kernel from the same bundle.

Release 0.1.52 includes the public application ABI repairs. OSWORD `&65`
functions 0 and 1 reset volatile TCP state without dropping the saved
association, function 4 reads the caller's JOIN block, function 8 preserves
the port field across
DNS resolution, and function 9 accepts the original single-connection setup
as a successful no-op. These paths are used by ElkChat and other applications
which call the driver directly rather than issuing star commands.

Release 0.1.52 keeps all WiCFS state out of `&03E0-&03FF`, the MOS keyboard
input buffer which holds the queued `*REWIND` and `CHAIN ""` launch. Stream
state again uses the original WiCFS cassette-workspace zero-page locations.
Vector ownership and predecessor state is persisted through the AP5-forwarded
Pi1MHz byte port at reserved services-buffer address `&FFEF00`. ROM 0.1.19
attempted to use JIM page `00:02:00`, but an unmodified AP5 does not forward
`&FCFD` or `&FCFE`; the write therefore aliased page zero and corrupted the
start of every downloaded UEF. Its host copy exists only while installing or
releasing WiCFS.
The public driver's page shadow is similarly transient in ROM heap. During
reset, MOS rebuilds the standard and extended vector tables before issuing ROM
service calls. The ROM therefore discards its saved WiCFS ownership record and
does not restore stale predecessor vectors over ADFS, DFS, MMFS or another ROM
which has already reclaimed them during the same reset pass.

Release 0.1.52 also retains the common WiCFS completion-path correction used by `*MENU`
and `*UEF LOAD`. The cassette last-block bit is now tested before the legacy
loader compatibility helper can change the processor flags. A completed file
therefore returns to MOS at its own final block instead of consuming later
files and eventually reporting `End of UEF` or an invalid chunk type.

Release 0.1.52 uses the single standard 64K JIM window which the AP5 actually
exposes through `&FCFF` and `&FD00-&FDFF`. Each WiCFS read is an interrupt-safe
page-select and data transaction. The data byte is recovered before
the saved processor flags because both values occupy the 6502 hardware stack
during the transaction.

Release 0.1.52 retains the removal of the incorrect Tube-transfer path exposed
by physical testing. 1MHzWifi is an Electron 1MHz-bus filing system and always
places UEF data in host memory. The patched menu uses OSBYTE `&EA` only to
detect an active Tube. It then enters the installed BASIC ROM directly on the
Electron and queues `PAGE=&E00` before the internal WiCFS launch command. It
does not access Tube registers, claim a channel, disable the Tube, or transfer
code through it. The stock menu launch remains `REWIND`, then `CHAIN ""`.

Release 0.1.52 also retains the original Zalaga loader's cassette `/` handoff fix.
WiCFS now handles FSCV reason 8 locally while it is the active filing system.
Earlier builds forwarded that notification through the displaced cassette
handler's extended-vector frame, so the following FSCV reason 2 never reached
WiCFS. A live Elkulator run with the photographed ROM order now downloads the
published Zalaga UEF and reaches gameplay through the unchanged `CHAIN ""`
and `/` sequence.

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
| Raspberry Pi 3A+, 3B, 3B+ | `kernel7.img` | Supported; BCM43455 7.45.241 compatibility firmware included |

There was no production Pi Zero 2 without wireless, nor a Pi 3A without the
plus suffix. The nearest real targets are Zero 2 W and 3A+, listed above.
On `kernel7.img`, the driver distinguishes the original Pi 3B's BCM43430 from
the Zero 2 W's BCM43436 by SOCRAM revision and from the 3A+/3B+'s BCM43455 by
chip ID. The Pi 3B/Zero W NVRAM is the calibrated Raspberry Pi board file, not
the generic placeholder configuration.
The Pi 3A+ hardware associated but remained at `0.0.0.0` with upstream
BCM43455 firmware 7.45.265. This bundle pins the preceding 7.45.241 image while
retaining the current Pi1MHz source revision.

Release hashes:

```text
1MHzWifi ROM bfaf33235ac4b3d96bae3c47a38080d5fd01795094bd52af5d42933bbfaf8f04
kernel.img   991edb294ccdc9c7e7e3406676c3cf6df8a7a4d44a16af529a9315c95f539906
kernel7.img  4f241520a41615e29a5500d2f62e751c0cb8ae28d5e51d1a55e8e76c4e4c305c
EMMFS.rom    b6c766c9a469867cddc0b64900db1693565f59bb6a051dc1a36073e446165955
nettools.ssd ce526c0023ad073ecdfe02bc804ea86b6162b405ffdd5d8c26dbc93df3c2ba8f
bundle ZIP   a9def4ca2a415d429292d2678761923e2bba4c06da63842316c0852243c00eaa
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
window at `&000000`, not Pi1MHz's private disc-memory base. It then selects
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
- Pi1MHz commit `d08242ee1b35cf1285b72c9ec1869e98081a8c3e`, the official
  `master` tip verified on 15 August 2026

Pi1MHz has no `main` branch. Run `./pi-side/check_upstream.sh` before a release;
it fails if the official default branch or its tip has changed.

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
git -C Pi1MHz checkout d08242ee1b35cf1285b72c9ec1869e98081a8c3e
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
make deps
make test
```

The unified test target builds the NetTools DFS image, runs its executable
py65 tests, runs the mailbox/JIM and secure-service core tests, checks the
hardware bundle, and runs the ROM integration suite. The latter checks ROM
identity, command presence, mailbox addressing, ElkChat-shaped calls through
the public MOS service-reason-8 and OSWORD `&65` entry,
safe rejection of unsupported functions, WGET, host-only WiCFS loading,
cancellation, configuration integration, and the absence of retired
UART/flash and Linux bridge code. The Pi1MHz services, net and web parser
suites also run under ASan and UBSan during release validation. WiCFS treats
Pi1MHz strictly as a 1MHz-bus service and never accesses Tube registers.

The real wolfSSH and Elkulator gates are available as `make test-ssh-real`,
`make test-elkulator`, and `make test-elkulator-ssh-real`. A clean two-kernel
build uses `make test-pi-firmware PI1MHZ_SOURCE=/path/to/Pi1MHz` with the
pinned wolfSSL and wolfSSH source paths described in the build guide.

The retained Elkulator captures under `tests/elkulator/screenshots/` cover ROM
startup, missing-service behavior and earlier Tube diagnostics. Manual
live-bridge sessions exercised the real Internet path rather than preloading a
response. The corrected loader has reached visible gameplay without a Tube for
Zalaga, Arcadians, Last of the Free, E-Type and Thrust. Castle of Riddles
reaches its interactive command prompt. Zalaga fetched 29,794 bytes (`&7462`)
from the published URL.
The local-import test placed the 10,631-byte gzip DeskDiary sample on an
emulated DFS disc, ran `*UEF LOAD DESK`, normalized it to its 20,580-byte raw
UEF, and reached the Desk Diary `ADDRESS`/`PLANNER` program menu.

Physical Electron tests of 0.1.22 exposed the wrong language-processor launch:
the `&7462`-byte Zalaga UEF loaded `ZALAGA 05 05EE` and returned to Tube BASIC.
The SD-card ZIP proves that the tested ROM and kernels matched the published
0.1.22 artifacts. Physical 0.1.24 testing then isolated its reversed Tube
transfer command: the same ROM order works after a Tube-off reboot and fails
when BASIC is running on the parasite. Version 0.1.46 contains no Tube transfer
path and retains the FSCV reason-8 correction. A symbol-guided trace found that
a cold host BASIC selected while the Tube is active chooses PAGE in `&23xx`;
the loaded Electron program remains at `&0Exx`, so a returning CHAIN stage
scans the wrong continuation. `QHOST` now queues `PAGE=&E00` before the
internal WiCFS launch. A live ten-entry catalogue differential produced
identical UEF hashes in every Tube-on/off pair, with nine strict framebuffer
matches and one animated-screen review item. Physical gameplay, BeebSCSI and
ADFS/DFS restoration remain release gates.

The maintained Elkulator adapter now includes an AP5 Tube ULA and external
3 MHz 65C02. When `-tube6502` is configured, RH Plus starts the Tube during
cold boot without manual intervention. A clean live run with the photographed
ROM order first reproduced the hardware boundary exactly with 0.1.25: Zalaga
downloaded, the initial `ZALAGA 05 05EE` file loaded, and execution returned to
the Tube BASIC prompt. The current 0.1.52 differential exercises catalogue
entries by sorted index, not by title-specific ROM behavior. The exact final
ROM reaches FrakV2 gameplay through MENU and enters Thrust gameplay through
local UEF import with Tube disabled and enabled. Physical-hardware
gameplay remains an open release gate and must not be inferred from the
emulator result.

## Documentation

- [Architecture](docs/architecture.md)
- [Building and release hygiene](docs/building.md)
- [Command reference](docs/commands.md)
- [MENU runtime adaptation](docs/menu-runtime-patch.md)
- [Pi1MHz integration](pi-side/README.md)
- [Hardware validation](docs/hardware-validation.md)
- [Implementation backlog](TODO.md)
- [ElkWiFi ROM patch kit](rom-side/README.md)
- [Pi1MHz patch kit](pi-side/README.md)
- [Elkulator mailbox patch kit](emulator/pi1mhz-mailbox/README.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
