# 1MHzWifi

This project exposes the Raspberry Pi WiFi stack to an Acorn Electron or BBC
Micro through Pi1MHz. The `1MHzWifi 0.1.66` candidate ROM presents the
ElkWiFi 0.23 command and OSWORD interface. The same 16 KiB ROM is built for
Electron, BBC B, BBC B+ and Master hosts. The Pi implementation runs inside
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

Version 0.1.66 is the current compatibility candidate. Version 0.1.55 is the last
physically exercised Tube-off baseline. Earlier 0.1.50 and
0.1.51 timing and WiCFS cursor changes caused physical MENU and local UEF
regressions, so they are not release baselines. Version 0.1.55 retains the
0.1.54 WiCFS execution path and checkpoints its stream cursor at file and
execution boundaries. Its WGET transport is not byte-identical to
0.1.49: mailbox and JIM accesses include bounded settling required by the
delayed-FIQ model. The published TITLES transfer takes about 42 seconds in the
conservative emulator profile, during which `Loading title data` remains on
screen. Physical timing remains an acceptance gate.

Version 0.1.63 retires `*MENU`, `*MENUSRC`, their endpoint persistence, binary
patcher and Pi-side cache. This leaves the generic WGET, UEF and WiCFS paths as
the only ROM download mechanisms and recovers about 1 KiB of additional ROM
space. `*PING` and `*NSLOOK` are resident ROM commands. Their former NetTools
copies are no longer included on the SSD.

Version 0.1.65 adds an interactive plain FTP client to the ROM. Control and
passive data sockets remain on the Pi, while GET and PUT use MOS filing calls
on the host. The same release adds SFTP to the NetTools package through the
managed wolfSSH service. Ordinary WGET now requires a destination filename
and writes it through the active MOS filing system.

Version 0.1.66 repairs `*PRD` selection of Pi1MHz JIM windows. It also replaces
repeated command dispatch and text with shared tables and enforces at least 455
unused bytes in the ROM image for the next bounded feature.

This release fixes two independently observed diagnostics. The Pi hardware RNG
wait now uses a 750 ms system-timer deadline instead of a CPU-speed-dependent
iteration count which could permanently disable wolfSSH on a Pi 3. HWDTEST now
fails unless both secure random and managed SSH are ready. WGET error `&30`
also prints the parsed HTTP status before closing the handle.

Version 0.1.61 retains the 0.1.59 OPENUP and vector-lifecycle corrections and
adds a generic low-loader compatibility gateway for Tube-off hosts. Exact
instruction tracing showed that normal cassette loaders can occupy
`&0900-&10FF`, overwriting the Electron MOS extended-vector table at
`&0D9F-&0DEF` and the ROM's transient network workspace. The gateway resides
at `&0780`, repairs the applicable MOS extended-vector tuple atomically, and
then enters the standard MOS dispatcher with the caller's registers and flags
intact. Incremental-stream generations are now kept in Pi-private JIM state,
so the same loader overwrite cannot invalidate a later refill. No production
path tests for a title name.

Version 0.1.61 adds a negotiated incremental UEF transport without changing
the public ElkWiFi command allocation. Local raw, gzip and single-entry ZIP
sources are uploaded through the AP5-visible JIM aperture, normalized into a
16 MiB Pi-private stream, and supplied to WiCFS in `&FF00`-byte windows.
Legacy ROM/kernel pairings retain the previous single-window path. The matched
candidate passes exact-window, multi-window, retry, ZIP and public-JIM-reuse
tests, plus a traced end-to-end Thrust gameplay run. Multi-window physical
gameplay and Tube-enabled operation remain acceptance gates.

The 0.1.55 image, SHA-256
`ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb`, has a
confirmed physical Tube-off baseline. WiFi, HWDTEST, NetTools, `*MENU`
and local `*UEF LOAD` work on the Electron, AP5 and Pi Zero 2 installation.
Data transfer is nevertheless too slow for normal use. Frak loads and plays.
Thrust reaches playable gameplay, but ADFS then remains unavailable through
Break and reset and returns only after a power cycle. Repton 2 hangs on entry
to gameplay, Plan B remains unstable, and Arcadians hangs at the end of its
final `4C 4C49` cassette block. These are open execution or filing-system
recovery defects, not successful title tests. Tube-enabled physical validation
remains mandatory.

An experimental host-workspace snapshot made the exact staged BeebSCSI image
pass a load, Break, ADFS remount and reload emulator sequence. Peer review
rejected that design because restoring arbitrary filing-system workspace during
reset is ROM-order dependent and can overwrite a newer filing-system owner.
That rejected experiment is not in the build. The 0.1.59 candidate instead
captures BYTEV with the pre-TAPE filing vectors and restores the complete set
only while WiCFS still owns it. It also refuses to install over a partially
owned prior WiCFS session. ADFS recovery after gameplay remains a physical
release gate.

The 21 August Tube-off milestone confirms that MENU launches Frak and Arcadians
to gameplay, and local `*UEF LOAD REPTON` reaches gameplay after a long startup.
It also identifies a repeatable generic lifecycle fault: after Frak, another
`*MENU` hangs until a cold start, and after Plan B, ADFS remains unavailable
until a cold start. `*UEF LOAD MRWIZ` normalizes the gzip image to `&3077` bytes
in JIM and then hangs before cassette playback begins. SSH works, but entering
its password from MODE 0 incorrectly changes the display to MODE 4. These
results are the current physical baseline; Tube-on validation remains
outstanding.

Version 0.1.59 is the unpromoted correction for that lifecycle fault. It saves
BYTEV with the pre-TAPE extended-vector snapshot and restores the set only at
an ownership-checked retirement boundary. Executable 6502 tests cover the
inactive MENU transition, balanced stack return, and delayed Pi mailbox
publication. Thrust, Mr Wiz and Repton 2 remain generic acceptance cases, not
names or branches in production code. The exact 0.1.59 image still requires
physical confirmation before these failures can be closed.

The exact 0.1.59 ROM reaches input-responsive Thrust gameplay in the strict
Tube-off Electron/AP5/ADFS/BeebSCSI emulator profile. The evidence includes a
live 184,780-event bus trace, zero Tube-register accesses and unchanged media
and configuration. This is an emulator acceptance result. Repeated MENU and
ADFS recovery, Mr Wiz, Repton 2 and Tube-enabled operation still require the
physical checks listed in the hardware plan.

The NetTools applications load at `&1D00` and validate OSHWM and HIMEM at every
entry. Their bootstrap preserves a suitable caller mode and selects MODE 4
only when the available host memory is insufficient. Machine
detection is refreshed at driver entry because the ROM heap is volatile
application workspace and cannot hold a reset-time cache. The bundle retains
the BCM43455 7.45.241 firmware used before the Pi 3A+ DHCP regression. Version
1.0 still requires the public ElkWiFi OSWORD comparison and the ADFS, DFS,
MMFS and TAPE coexistence gates.

SSH also reads the active MOS text-window dimensions and renders at widths from
20 to 80 columns. A mode with sufficient host memory is preserved through the
password and session path. Stock non-shadow MODE 0 has `HIMEM=&3000`, below
the current SSH image end near `&3906`, so it still selects MODE 4 once at
entry. Supporting that memory envelope requires a separate relocatable or SWR
architecture rather than a password-path display workaround.

The following command paths are implemented. Pi and JIM traffic stays on the
1MHz bus. WiCFS loads into Electron host memory. The launcher uses MOS OSBYTE
`&EA` only to detect whether host BASIC must be entered; it does not claim,
disable or transfer through a fitted Tube. A game remains free to use that
Tube itself:

| Area | Implemented behavior |
| --- | --- |
| WiFi | `*WIFI ON`, `*WIFI OFF`, `*LAP`, `*JOIN`, `*JOIN ?`, `*LEAVE`, `*ONLINE`, `*IFCFG`, `*LAPOPT` |
| Network | `*PING`, `*NSLOOK`, HTTP `*WGET`, OSWORD `&65` TCP/UDP open, send, receive and close |
| Time | NTP-backed `*DATE` and `*TIME` |
| Storage | `*WGET <url> <filename>` through the active filing system; `*WGET -U`, `*UEF LOAD`, `*WICFS`, `*REWIND`, `*PRD`, and `*WGET -S` through explicit Pi1MHz JIM windows |
| Diagnostics | `*HELP WIFI`, `*VERSION`, station `*MODE`, bounded missing-service errors |

Platform-sensitive ROM paging uses the documented
OSBYTE `&81` machine query before the driver touches the high JIM selectors.
The result is transient and is not assumed to survive application execution.

`*PRINTER`, `*UPDATE`, update `*CRC`, and `*SETSERIAL` are not present. They
depend on cartridge hardware that Pi1MHz does not expose. Driver function 19
and reserved functions 29 to 31 return `Not implemented`, matching the pinned
0.23 table. Watchdog and SSL-buffer controls return bounded success because
those resources are owned by Pi1MHz. The direct flash function cannot reach
the inherited UART or flash code.

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

The removal and the retained generic facilities are recorded in
[the MENU retirement note](docs/menu-retirement.md).

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
host ROM. Release 0.1.55 retains the WiCFS changes and compressed-UEF Pi
service introduced in 0.1.8, supports zero-byte CFS marker files, preserves a
live WiFi association across host resets, and restores the `WGET -U` contract for
raw paged-RAM data such as the published menu TITLES catalogue. The matched
kernel still provides service command 93 for ZIP and gzip UEF normalization,
so replace both the ROM and the kernel from the same bundle.

Release 0.1.55 includes the public application ABI repairs. OSWORD `&65`
functions 0 and 1 reset volatile TCP state without dropping the saved
association, function 4 reads the caller's JOIN block, function 8 preserves
the port field across
DNS resolution, and function 9 accepts the original single-connection setup
as a successful no-op. These paths are used by ElkChat and other applications
which call the driver directly rather than issuing star commands.

Release 0.1.55 keeps all WiCFS state out of `&03E0-&03FF`, the MOS keyboard
input buffer which holds the queued `*REWIND` and `CHAIN ""` launch. Stream
state again uses the original WiCFS cassette-workspace zero-page locations.
Vector ownership and predecessor state is persisted through the AP5-forwarded
Pi1MHz byte port at reserved services-buffer address `&FFEF00`. ROM 0.1.19
attempted to use JIM page `00:02:00`, but an unmodified AP5 does not forward
`&FCFD` or `&FCFE`; the write therefore aliased page zero and corrupted the
start of every downloaded UEF. Its host copy exists only while installing or
releasing WiCFS.
Version 0.1.55 extends that transactional record with the current UEF offset,
JIM page, stream-start flag and remaining-byte count. It writes the record
only when a file is opened, closed, completed or about to execute. This lets a
loaded title overwrite volatile cassette workspace without losing the next
file position, while avoiding a services-mailbox transaction for every byte.
The public driver's page shadow is similarly transient in ROM heap. During
reset, MOS rebuilds the standard and extended vector tables before issuing ROM
service calls. The ROM therefore discards its saved WiCFS ownership record and
does not restore stale predecessor vectors over ADFS, DFS, MMFS or another ROM
which has already reclaimed them during the same reset pass.

Release 0.1.55 also retains the common WiCFS completion-path correction used by `*MENU`
and `*UEF LOAD`. The cassette last-block bit is now tested before the legacy
loader compatibility helper can change the processor flags. A completed file
therefore returns to MOS at its own final block instead of consuming later
files and eventually reporting `End of UEF` or an invalid chunk type.

Release 0.1.55 uses the single standard 64K JIM window which the AP5 actually
exposes through `&FCFF` and `&FD00-&FDFF`. Each WiCFS read is an interrupt-safe
page-select and data transaction. The data byte is recovered before
the saved processor flags because both values occupy the 6502 hardware stack
during the transaction.

The current candidate retains that AP5-visible window but no longer limits the
authoritative UEF to one window. Command 93 negotiates stream ABI 1, uploads
the source in `&FF00`-byte windows, normalizes it into Pi-private storage, and
publishes the next window only when WiCFS exhausts the current one. Window
generation numbers make retries idempotent. Older kernels continue through the
unchanged single-window path and retain the `&FFFE` limit.

Release 0.1.55 retains the removal of the incorrect Tube-transfer path exposed
by physical testing. 1MHzWifi is an Electron 1MHz-bus filing system and always
places UEF data in host memory. The patched menu uses OSBYTE `&EA` only to
detect an active Tube. It then enters the installed BASIC ROM directly on the
Electron and queues `PAGE=&E00` before the internal WiCFS launch command. It
does not access Tube registers, claim a channel, disable the Tube, or transfer
code through it. The stock menu launch remains `REWIND`, then `CHAIN ""`.

Release 0.1.55 also retains the original Zalaga loader's cassette `/` handoff fix.
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
1MHzWifi ROM 25472db8c5cc22e09bf6b9a5531bba0cc334cdec3ba0af459d3bfc6fa82082ef
kernel.img   c8910a1ea94d72647a45b6d61c9dbd197865371e1b8662327d9a0e9c798e496d
kernel7.img  20b3439503d574a73304b86fbd124efe6301e39ee3190a20711b3c78919770f1
nettools.ssd 7bfe26b2c8f3212466bd3bdbc7f40e6f1d72722a3dbcc7a9f25fd3858dc8d883
bundle ZIP   65702f87e59fd3fddc819e8712df4146278754ad32b23d49e26e040e4060f110
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
elkwifi_utc_offset_minutes=0
```

`wifi_security` accepts `auto`, `open`, `wep`, `wpa`, or `wpa2`. A profile
saved by `*JOIN` takes precedence over the initial WiFi settings. The UTC offset is expressed in
minutes east of UTC. Use `0` for GMT and `60` for BST.

`*UEF LOAD <filename>` reads a UEF image from the currently selected MOS filing
system, including ADFS, DFS, or MMFS, through the WiCFS JIM window. Raw UEF,
gzip-compressed UEF, single-entry ZIP containing UEF, and ZIP containing a
gzip-compressed UEF are recognized by their contents. CRC and expanded-size
checks run on the Pi before launch. The normalizer uses the host-visible JIM
window at `&000000`, not Pi1MHz's private disc-memory base. It then selects
the tape filing system, installs WiCFS, runs `*REWIND`, and executes `CHAIN ""`
without further input. The setup and launch are queued in two stages so they
fit the Electron keyboard buffer. With a matched stream-ABI kernel, expanded
images may be up to 16 MiB and are exposed to WiCFS as `&FF00`-byte windows.
An older kernel is detected safely and retains the `&FFFE`-byte limit.
The same normalization is applied to `*WGET -U`
downloads, and the success line identifies the detected format.

Credentials and saved settings are plaintext files on the FAT partition.
Protect the card and do not publish production credentials in bug reports.

## Build from source

The complete, reproducible procedure is in
[Building and release hygiene](docs/building.md). In summary, two clean
upstream source trees are required:

- ElkWiFi commit `7bf366c97bec18bd238963c95e6f2aa6893cdb3a`
- Pi1MHz commit `e949f2d2714b15f314df375e52db5febb6c40e6d`, the official
  `master` tip verified on 23 August 2026

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
git -C Pi1MHz checkout e949f2d2714b15f314df375e52db5febb6c40e6d
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
the Tube BASIC prompt. The differential runner exercises catalogue entries by
sorted index, not by title-specific ROM behavior. The exact 0.1.55 ROM enters
Thrust gameplay through local UEF import with the Tube disabled. Its MENU and
Tube-enabled runs remain unchecked. Physical-hardware
gameplay remains an open release gate and must not be inferred from the
emulator result.

## Documentation

- [Architecture](docs/architecture.md)
- [Building and release hygiene](docs/building.md)
- [Command reference](docs/commands.md)
- [MENU retirement](docs/menu-retirement.md)
- [Pi1MHz integration](pi-side/README.md)
- [Hardware validation](docs/hardware-validation.md)
- [Regression ownership](docs/regression-testing.md)
- [Implementation backlog](TODO.md)
- [ElkWiFi ROM patch kit](rom-side/README.md)
- [Pi1MHz patch kit](pi-side/README.md)
- [Elkulator mailbox patch kit](emulator/pi1mhz-mailbox/README.md)
- [Contributing](CONTRIBUTING.md)
- [Project governance](GOVERNANCE.md)
- [GitHub repository settings baseline](docs/github-repository-settings.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Support](SUPPORT.md)
- [Security policy](SECURITY.md)
- [Licensing status](LICENSING.md)
- [Copyright and distribution notice](NOTICE)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
