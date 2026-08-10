# Pi1MHz network tools plan

## Product boundary

The release is a bootable 200 KiB DFS image containing native 6502 network
tools for BBC Micro, Electron and compatible Acorn MOS machines with Pi1MHz.
The clients call the Pi1MHz mailbox directly. No 1MHzWifi or ElkWiFi service
ROM is required.

All programs use Tube-aware DFS load and execution metadata but run on the I/O
processor. They do not require or claim a Tube parasite.

## Repository layout

- `src`: 6502 clients, shared assembly and SSD definitions.
- `tests`: SSD, 6502 and end-to-end emulator tests.
- `../pi-side`: installable combined Pi1MHz firmware patch package.
- `../emulator/pi1mhz-mailbox`: reusable mailbox/JIM emulator device, network
  backends, tests and Elkulator adapter.
- `docs`: shared protocol and release documentation.

The Pi firmware changes remain separate from the original ElkWiFi-derived ROM
patches, while the repository-level Makefile runs their common validation.

## Current SSD contents

- `NETMENU`: launcher and command summary.
- `TERM`: Telnet client with a bounded 40 by 24 VT100 parser.
- `SSH`: SSH v2 client with host-key confirmation, Pi-resident keys and hidden
  password fallback.
- `PING`, `NSLOOK`, `FTP`, `HGET`: executable protocol placeholders.
- `VIEWDAT`: executable Viewdata placeholder. DFS limits names to seven
  characters.

The placeholders report that their implementation is pending. This avoids
shipping commands that appear to work but silently return incomplete results.

## Responsibility split

The 6502 owns:

- command parsing and user interaction;
- VT100 or Viewdata rendering;
- keyboard mapping and local disconnect handling;
- host-key confirmation; and
- decrypted terminal input and output.

The Pi owns:

- WiFi, DNS, TCP and URL transports;
- SSH key exchange, authentication, packet protection and channels;
- entropy; and
- persistent keys and known-host data on the Pi SD card.

The Pi will also own TLS and certificate validation when HTTPS is implemented.

Private keys and session keys do not cross JIM. Password fallback is temporary
and is wiped from 6502 RAM, JIM and Pi RAM after use.

## VT100 scope

The current renderer supports printable ASCII, common control characters,
cursor positioning and bounded movement, display and line erasure, reset,
inverse video, save and restore, OSC suppression, character-set designators
and safe control-string consumption.

Parser entry points now exist for:

- insert, delete and erase character operations;
- insert and delete line operations;
- scrolling and scroll margins;
- terminal modes;
- tab clearing; and
- device attributes and status reports.

The remaining editing operations need a screen-memory abstraction. Device
reports need a small renderer-to-transport reply queue. Until those parts are
implemented, complete sequences are consumed without leaking bytes to the
display.

UTF-8, sixel, true colour and full VT220 behaviour are outside the initial
terminal scope.

## Viewdata scope

`VIEWDAT host [port]` will reuse the common TCP/Telnet stream layer but will
not use the VT100 renderer. It needs:

- a bounded Viewdata and Prestel control-code parser;
- a MODE 7 renderer;
- numeric, `#`, `*`, correction and disconnect key mappings;
- configurable raw TCP or Telnet transport; and
- recorded page fixtures split across arbitrary network reads.

## Roadmap

### Milestone 1: terminal and SSH

- Complete common stream and managed secure-service ABIs.
- Provide host-key storage and Pi-resident identities.
- Support hidden password fallback.
- Validate TERM and SSH through py65, Elkulator and real SSH fixtures.

Status: implemented. Physical hardware qualification remains outstanding.

### Milestone 2: terminal completion

- Implement screen editing and scrolling regions.
- Add terminal reply queues for DA, DSR and cursor-position reports.
- Complete keyboard mappings for Home, Delete and function keys.
- Add long-running `top`, editor and shell fixtures.

### Milestone 3: Viewdata

- Implement the MODE 7 parser and renderer.
- Add input mapping and transport selection.
- Test recorded pages and a live emulator service.

### Milestone 4: utility clients

- Implement PING and NSLOOK using native Pi services.
- Implement HGET with TLS validation and transactional file output.
- Implement FTP control and passive data connections.

### Milestone 5: release and hardware

- Test BBC Micro, Master and Electron systems with supported Pi1MHz hardware.
- Verify filing-system and Tube coexistence.
- Publish the SSD, matching firmware images, hashes and recovery instructions.

## Test gates

Run these before hardware testing:

```sh
make test
make test-elkulator
make test-ssh-real
make test-elkulator-ssh-real
make test-pi-firmware PI1MHZ_SOURCE=/path/to/Pi1MHz
```

The real SSH tests require the pinned wolfSSH and wolfSSL build described in
the firmware patch README. Hardware testing does not replace emulator or host
tests.

## Release rules

- Do not put private keys, passwords or generated test credentials in an SSD
  or source package.
- Do not provide runtime switches that disable host-key, certificate, MAC or
  signature checks.
- Wipe password and key buffers on success, failure and cancellation.
- Keep debug traces free of passwords and private material.
- Pin cryptographic dependencies and record compatible ABI versions.
- Reject incompatible firmware with a clear upgrade message.

The mailbox command layout and validation rules are documented in
`secure_service_abi.md`.
