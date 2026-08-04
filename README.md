# ElkWiFi for Pi1MHz

This project exposes the Raspberry Pi WiFi stack to an Acorn Electron or BBC
Micro through Pi1MHz. The host ROM presents the applicable ElkWiFi 0.23 command
and OSWORD interface. The Pi implementation runs inside the Pi1MHz bare-metal
kernel; it is not a Linux daemon.

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

The following command paths are implemented:

| Area | Implemented behavior |
| --- | --- |
| WiFi | `*WIFI ON`, `*LAP`, `*JOIN`, `*JOIN ?`, `*LEAVE`, `*IFCFG`, `*LAPOPT` |
| Network | `*PING`, HTTP `*WGET`, OSWORD `&65` TCP open/send/receive/close |
| Time | NTP-backed `*DATE` and `*TIME` |
| Menu | Persistent `*MENUSRC`; `*MENU` downloads, validates, adapts, and runs the published payload on the I/O processor |
| Storage | `*WGET -U`, `*WICFS`, `*REWIND`, `*PRD`, and `*WGET -S` through Pi1MHz JIM windows |
| Diagnostics | `*HELP WIFI`, `*VERSION`, station `*MODE`, bounded missing-service errors |

`*PRINTER`, `*UPDATE`, update `*CRC`, and `*SETSERIAL` are not present. They
depend on cartridge hardware that Pi1MHz does not expose. Unknown OSWORD
functions and the direct flash function return `Not implemented` before they
can reach the inherited UART or flash code.

HTTPS, TLS, and SSH are not implemented. Secure requests fail closed; they are
never downgraded to plaintext.

The authoritative implementation backlog is [TODO.md](TODO.md). It records
several deliberate compatibility gaps, including soft and hard reset
semantics, complete OSWORD `&65` parity, and full Escape handling.

The published ElkWiFi menu contains a direct `&FC34` cartridge bank-selection
sequence. At runtime, `*MENU` replaces that exact eight-byte sequence with an
equal-length Pi1MHz `&FCFE` window selection after WGET succeeds and before it
enters host `&E00` through a Tube-safe RAM return trampoline. See [the MENU runtime adaptation](docs/menu-runtime-patch.md)
for the byte-level contract and failure behavior.

## Hardware-test bundle

The ready-to-copy SD-card image tree is `build/pi1mhz-all/`. The equivalent ZIP
archive is [build/pi1mhz-all-hardware-test.zip](build/pi1mhz-all-hardware-test.zip).
Copy the contents of `pi1mhz-all/` to a FAT-formatted Pi boot partition, then
fit or load `Pi1MHz/ElkWiFi.rom` as an Acorn sideways ROM.

When updating an existing test card, keep its `Pi1MHz.cfg` and saved
`Pi1MHz/ElkWiFi.*` settings. Replace only the kernel used by that Pi and the
host ROM. A ROM-only change does not require replacing the Pi kernel; a
Pi-only change does not require reloading the ROM.

The bundle does not contain a BeebSCSI disc image. Preserve the card's
`/BeebSCSI0` directory when updating it. A clean card needs at least
`/BeebSCSI0/scsi0.dat` from an existing installation or a BeebSCSI starter
image before ADFS can mount a hard disc. `Pi1MHz/defscsi.cfg` is only the
default geometry description; it is not a disc image.

The bundle contains both supported kernel families:

| File | Target |
| --- | --- |
| `kernel.img` | Raspberry Pi 1 and Pi Zero family |
| `kernel7.img` | Raspberry Pi 2 and Pi 3 family |

Release hashes:

```text
ElkWiFi ROM  923c607123674115c009fd5665b3aea27cd00638054e2a9e937a2903d9a438fe
kernel.img   7a8f564aa20cf8d1c4bffbc71774e500f01eb2795bdbd57f4b5a0ffb087cd1a5
kernel7.img  57eb5fe8cb33dda036bf0af0a33d0bcca95f65068261947a47210e907ec5683a
bundle ZIP   dc319ef83c2500b2b54c840644dd302ab437af33405d69a1edc144fe65155e01
```

The same values are provided in `SHA256SUMS` for automated verification.

## Configuration

The installer preserves active values already present in `Pi1MHz.cfg`. The
following optional keys provide initial settings:

```ini
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

Credentials and saved settings are plaintext files on the FAT partition.
Protect the card and do not publish production credentials in bug reports.

## Build from source

Two upstream source trees are required:

- ElkWiFi commit `7bf366c97bec18bd238963c95e6f2aa6893cdb3a`
- Pi1MHz commit `83bca4922955e28e2f95122d71d631cce813d467`

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
git -C Pi1MHz checkout 83bca4922955e28e2f95122d71d631cce813d467
./pi-side/install_bundle.sh /path/to/Pi1MHz all
```

The installer modifies the supplied Pi1MHz checkout. Use a dedicated clean
checkout so that the resulting patch state is easy to inspect and reproduce.

The root `build.sh` verifies the size and SHA-256 of the already-built ROM. It
does not fetch or compile either upstream project.

## Test

```sh
./build.sh
python3 -m unittest discover -s tests -v
unzip -t build/pi1mhz-all-hardware-test.zip
```

The test suite checks ROM identity, command presence, mailbox addressing,
safe rejection of unsupported functions, WGET and WiCFS routing, configuration
integration, and the absence of the retired Linux bridge.

Elkulator smoke-test captures are under `tests/elkulator/screenshots/`.
Elkulator does not yet emulate the Pi1MHz services mailbox, so live WiFi,
WGET, MENU, and WiCFS behavior must be tested on Pi1MHz hardware.

## Documentation

- [Architecture](docs/architecture.md)
- [Command reference](docs/commands.md)
- [MENU runtime adaptation](docs/menu-runtime-patch.md)
- [Pi1MHz integration](pi-side/README.md)
- [Hardware validation](docs/hardware-validation.md)
- [Implementation backlog](TODO.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
