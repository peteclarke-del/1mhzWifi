# Pi1MHz bare-metal integration

This directory contains the Pi1MHz source overlay and patch set. Raspberry Pi
boot firmware loads the resulting `kernel.img` or `kernel7.img` directly. No
Linux service is installed or required.

Pi1MHz V1.30 already contains its own bare-metal CYW43/SDIO WiFi stack. The
overlay retains and extends that stack. Its main addition is an ElkWiFi-facing
services-mailbox adapter, plus the state, security, and networking corrections
needed by the retained ElkWiFi commands.

## Upstream requirements

Use Pi1MHz commit `8468a38f63b25785007a50912a3b32a596db8ff9`.
The installer rejects any other revision so an upstream change cannot alter a
release build without review. This commit contains tag `V1.30` in its history
and includes the later net service required by WGET and OSWORD TCP.

Required build tools:

- Git with initialised Pi1MHz submodules
- Arm GCC 13 or later
- A verified `build/elkwifi_pi1mhz.rom` in this repository

The installer changes the supplied Pi1MHz checkout. Use a dedicated checkout,
inspect its diff after installation, and retain the exact upstream commit in
hardware test records.

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

Set `ARM_GCC` to the compiler path when `arm-none-eabi-gcc` is not on `PATH`.

The installer performs the following operations:

1. Verifies the Pi1MHz checkout and compiler.
2. Copies `elkwifi_service.c` and `elkwifi_service.h` into `src/`.
3. Applies the Pi1MHz integration and CYW43 patches in a fixed order.
4. Installs the matched host ROM as `firmware/Pi1MHz/ElkWiFi.rom`.
5. Enables the Services mailbox, ElkWiFi service, and net service defaults.
6. Enables the three BeebSCSI defaults when no active value exists.
7. Invokes the upstream Pi1MHz build script.
8. Copies the firmware tree into a model-specific SD-card directory and ZIP.

The installer is intended to be repeatable. Each patch has an explicit
already-applied test. It preserves active configuration values rather than
replacing them.

## Service command range

The overlay registers commands 80-91 at the Pi1MHz Services mailbox. FIQ
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

Raw TCP and HTTP use the existing Pi1MHz net-service command range. Secure
open is registered only as a reserved ABI value and returns unsupported.

## MENU compatibility

Menu URL persistence is implemented by service commands 84-86. The downloaded
upstream MENU is also adapted by the host ROM because it contains a direct
`&FC34` cartridge bank-selection sequence. The ROM replaces that exact
eight-byte sequence with a Pi1MHz `&FCFE` window-1 selection before entering
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
standard page-mode JIM registers at `&FCFD-&FCFF`; relocating or disabling
Rampage would disconnect WiCFS and WGET storage from the 1MHz bus.
It does not merge a previously deployed SD card back into a newly generated
bundle. Preserve deployed configuration separately before replacing an SD-card
tree.

The generated bundle includes `ADFS.rom` and `defscsi.cfg`, but it deliberately
does not include BeebSCSI LUN data. Preserve `/BeebSCSI0` and any other
`/BeebSCSI*` directories when updating a card. A clean card needs a
`/BeebSCSI0/scsi0.dat` image before ADFS has a hard disc to mount.

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
existing access points. WPA3 is not exposed. HTTPS, TLS, and SSH are not
linked into the bare-metal image. Requests for secure transports fail closed.

Credentials are not protected at rest. Do not use a production WiFi password
in public test artifacts.
