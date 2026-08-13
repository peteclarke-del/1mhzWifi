# Pi1MHz bare-metal integration

This directory contains the Pi1MHz integration package and installer. The
versioned package is under `pi1mhz-516a267/`, with source changes separated into
`patches/` and complete replacement files under `overlay/`. Raspberry Pi
boot firmware loads the resulting `kernel.img` or `kernel7.img` directly. No
Linux service is installed or required.

The implementation record is
[`pi1mhz-516a267/TECHNICAL.md`](pi1mhz-516a267/TECHNICAL.md). The complete
`pi-side` directory is the standalone source patch kit. Its `apply` preset
does not require a host ROM. A complete firmware build accepts `ELKWIFI_ROM`,
`HOST_TOOLS_SSD` and `PI1MHZ_OUTPUT_DIR` when run outside this monorepo.

Pi1MHz V1.30 already contains its own bare-metal CYW43/SDIO WiFi stack. The
overlay retains and extends that stack. Its main addition is an ElkWiFi-facing
services-mailbox adapter, plus the state, security, and networking corrections
needed by the retained ElkWiFi commands.

## Upstream requirements

Use Pi1MHz commit `516a267493d9f19e6bf2f4a2ea4c3e7472b12135`.
This was the tip of the official `master` branch when checked on 9 August
2026. Pi1MHz does not have a `main` branch. The commit is 83 commits after the
V1.30 tag and includes the later net service required by WGET and OSWORD TCP.
The installer rejects any other revision and performs a live upstream check by
default, so a new upstream commit stops the release build pending review.

Run the same check independently with:

```sh
./pi-side/check_upstream.sh /path/to/Pi1MHz
```

For a deliberately offline, reproducible rebuild, set
`PI1MHZ_VERIFY_REMOTE=0`. This skips only the network query. The exact reviewed
commit is still mandatory.

Required build tools:

- Git with initialised Pi1MHz submodules
- Arm GCC 13 or later
- A verified `build/elkwifi_pi1mhz.rom` in this repository

The installer changes the supplied Pi1MHz checkout. Use a dedicated checkout,
inspect its diff after installation, and retain the exact upstream commit in
hardware test records. Keep the checkout outside this repository and use an
absolute path without spaces because the upstream CMake files do not quote all
generated include paths. See [the complete build procedure](../docs/building.md).

## Install and build

```sh
./pi-side/install_bundle.sh /path/to/Pi1MHz all
```

Build presets:

| Preset | Output |
| --- | --- |
| `all` | `kernel.img`, `kernel7.img`, and `build/pi1mhz-all/` |
| `rpi` | `kernel.img` and `build/pi1mhz-rpi/` |
| `rpi3` | `kernel7.img` and `build/pi1mhz-rpi3/` |

Use `kernel.img` for Pi Zero and Zero W. Use `kernel7.img` for Zero 2 W and
Pi 3A+/3B/3B+. The `all` bundle includes CYW43430, CYW43436/43436s, and
CYW43455 firmware. Plain Pi Zero has no onboard WiFi, so the ElkWiFi service
remains available but `*WIFI ON` reports `Device not found`.
The ARMv8 image preloads 43430, 43436, and 43455 candidates, then selects the
original Pi 3B, Zero 2 W, or Pi 3A+/3B+ image from the detected chip and SOCRAM
revision before firmware download.
The BCM43455 image is pinned to firmware 7.45.241 from upstream revision
`8468a38`. The later 7.45.265 image associates on the Pi 3A+ validation
hardware but does not complete DHCP. Pi1MHz source remains based on the
reviewed `516a267` revision.

Set `ARM_GCC` to the compiler path when `arm-none-eabi-gcc` is not on `PATH`.

The installer performs the following operations:

1. Verifies the Pi1MHz checkout and compiler.
2. Copies the maintained service and UEF normalisation sources into `src/`.
3. Applies the Pi1MHz integration and CYW43 patches in a fixed order.
4. Installs the matched host ROM as `firmware/Pi1MHz/ElkWiFi.rom`.
5. Installs Electron MMFS Pi1MHz 1.60 as `firmware/Pi1MHz/EMMFS.rom` for
   minimum 32K Electron systems which do not have sideways RAM.
6. Enables the Services mailbox, ElkWiFi service, and net service defaults.
7. Enables the three BeebSCSI defaults when no active value exists.
8. Invokes the upstream Pi1MHz build script.
9. Copies the firmware tree into a model-specific SD-card directory and ZIP.

The installer is intended to be repeatable. Each patch has an explicit
already-applied test. It preserves active configuration values rather than
replacing them. Normal hardware-test bundles preserve the linked kernels'
actual modification times so stale copies are visible on an SD card. Set
`SOURCE_DATE_EPOCH` when a release job requires normalized timestamps.

## Service command range

The overlay registers commands 80-93 at the Pi1MHz Services mailbox. FIQ
context captures a request and marks it busy. Filesystem, scan, association,
DNS, ICMP, and NTP work runs in a main-loop poll callback.

| Command | Operation |
| ---: | --- |
| 80 | Status and firmware readiness |
| 81 | Access-point scan |
| 82 | Join query, save, associate, and leave |
| 83 | Interface addresses and MAC |
| 84 | Get menu URL |
| 85 | Validate and save menu URL |
| 86 | Restore default menu URL |
| 87 | Save LAPOPT mode |
| 88 | DNS and ICMP echo |
| 89 | DNS and NTP date/time |
| 90 | Cancel an outstanding scan, DNS, ICMP or NTP request |
| 91 | Reserved secure-open ABI; unsupported |
| 92 | Concise association and IPv4 readiness status |
| 93 | Validate and normalize raw, gzip or ZIP UEF data in JIM |

Raw TCP and HTTP use the existing Pi1MHz net-service command range. Secure
open is registered only as a reserved ABI value and returns unsupported.
Command 93 performs CPU-only decompression and CRC checks in the main poll,
never in FIQ context.

## MENU compatibility

Menu URL persistence is implemented by service commands 84-86. The downloaded
upstream MENU is also adapted by the host ROM because it contains a direct
`&FC34` cartridge bank-selection sequence. The ROM replaces that exact
eight-byte sequence with an AP5-compatible no-bank helper before entering
host `&E00`. No Pi-side binary rewrite occurs. See
[the byte-level runtime contract](../docs/menu-runtime-patch.md).

## Pi1MHz.cfg

The installer adds required defaults only when no active setting exists:

```ini
Services_addr=0xA6
ElkWiFi_addr=0x00
net_enable=1
Rampage_addr=0xFD
SCSIJUKE=0
SCSIID=0
VFSJUKE=0
```

Optional initial ElkWiFi settings are:

```ini
wifi_ssid=MyNetwork
wifi_password=secret
wifi_security=auto
elkwifi_menu_url=http://acornelectron.nl/uefarchive/MENU
elkwifi_utc_offset_minutes=0
```

`wifi_security` accepts `auto`, `open`, `wep`, `wpa`, and `wpa2`. A valid
saved profile takes precedence over the initial WiFi settings. A valid saved
menu URL takes precedence over `elkwifi_menu_url`; the compiled default is used
when neither value is valid.

The installer preserves an active `Pi1MHz.cfg` value in its source checkout,
except that it rejects a `Rampage_addr` other than `0xFD`. The ROM uses the
standard `&FCFF` page selector and JIM window forwarded by the AP5; relocating
or disabling Rampage would disconnect WiCFS and WGET storage from the 1MHz bus.
It does not merge a previously deployed SD card back into a newly generated
bundle. Preserve deployed configuration separately before replacing an SD-card
tree.

The services dispatcher owns the individual ElkWiFi, raw network and secure
command ranges once `Services_addr` is enabled. Legacy values such as
`ElkWiFi_addr=-1`, `net_addr=-1`, or `secure_addr=-1` do not disable those
subservices. Set `Services_addr=-1` only when the entire shared services
mailbox is intentionally removed from the host address map. The child poll
callbacks can remain registered, but without a parent mailbox command they are
dormant background work rather than host-visible services.

The generated bundle includes `ADFS.rom` and `defscsi.cfg`, but it deliberately
does not include BeebSCSI LUN data. Preserve `/BeebSCSI0` and any other
`/BeebSCSI*` directories when updating a card. A clean card needs a
`/BeebSCSI0/scsi0.dat` image before ADFS has a hard disc to mount.

The bundle retains upstream `SWMMFS.rom` for systems with writable sideways
RAM and adds `EMMFS.rom` for a 32K Electron with only ROM storage. Both use
the Pi1MHz FAT service and the `BEEB.MMB` file in the SD-card root. `EMMFS.rom`
is the Electron normal-ROM, Pi1MHz-device build from MMFS 1.60.

## Persistent files

| File | Purpose |
| --- | --- |
| `/Pi1MHz/ElkWiFi.wifi` | Versioned saved WiFi profile |
| `/Pi1MHz/ElkWiFi.menu` | Saved menu URL |
| `/Pi1MHz/ElkWiFi.lapopt` | Saved scan display mode |

Legacy two-line WiFi profile files remain readable. New profile, menu, and
LAPOPT writes are not yet atomic. All files, including WiFi passwords, are
plaintext on the FAT partition.

## Association behavior

`*JOIN <ssid> <password>` saves the requested profile before starting
association. The host receives `WIFI CONNECTING` once the request has been
accepted; association and DHCP continue cooperatively. `*JOIN ?` and `*IFCFG`
report live state without holding the shared mailbox request open.
If JOIN arrives during radio startup or an earlier association attempt, the
runtime queues a fresh association using the newly saved credentials. The
accepted request is not lost when the current state machine reaches DONE.
`*ONLINE` is the short readiness check: it reports the assigned IPv4 address,
`OFFLINE CONNECTING`, `OFFLINE WIFI OFF`, `OFFLINE ERROR`, or `OFFLINE`.

The radio-only startup path performs CLM/country, PHY, and event-mask setup so
that `*LAP` works before association. A saved profile is loaded during Pi boot
and reapplied after every Acorn reset, even when the separately powered Pi has
not restarted. Association starts automatically. `*LEAVE` sends
`WLC_DISASSOC`, releases the live DHCP state, clears the interface addresses,
and pauses automatic rejoin until the next explicit join.

`*WIFI OFF` is distinct from LEAVE. It sends `WLC_DOWN`, clears the live
network state, and marks the radio disabled while keeping SDIO, firmware, and
the services mailbox resident. A later `*WIFI ON` sends `WLC_UP` and restarts
association when a saved profile is available.

The scan response is capped at four BSS records to fit the inherited 240-byte
host buffer. Removing that limit requires a compatible paging contract.

Escape cancellation closes ICMP/NTP PCBs, invalidates callback generations
and clears the active scan state. A late DNS or packet callback cannot complete
a newer request which reused the same command page. WGET and raw TCP close the
net-service handle on cancellation.

## Security limits

WEP, WPA, and WPA2 profile modes are implemented for compatibility with
existing access points. WPA3 is not exposed. The bundled kernels link the
managed wolfSSH service used by the separate NetTools `SSH` client. The
ElkWiFi-compatible ROM does not expose SSH, TLS or HTTPS. HTTPS remains
unimplemented and requests for it fail closed.

Secure-service capability command 94 is a fixed mailbox response and completes
in the services callback. It does not wait for the main-loop wolfSSH reset or
RNG initialisation. Before the first poll it reports the capabilities compiled
into the kernel; the poll loop then replaces that startup snapshot with actual
provider readiness. SSH open, authentication and session traffic remain
asynchronous and bounded through the normal Pi1MHz poll path.

Credentials are not protected at rest. Do not use a production WiFi password
in public test artifacts.
