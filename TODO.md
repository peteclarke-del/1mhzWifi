# Engineering status

This file records the remaining product boundary after the current ROM and
Pi1MHz implementation pass. Hardware proving is tracked separately in
[`docs/hardware-validation.md`](docs/hardware-validation.md).

## Complete in this build

- [x] Bare-metal Pi1MHz service integration on reviewed upstream commit
  `516a267493d9f19e6bf2f4a2ea4c3e7472b12135`.
- [x] Both Raspberry Pi kernel families and the complete SD-card bundle.
- [x] AP5-safe FRED/JIM transport with no dependency on cartridge `&FC30` UART
  registers.
- [x] `*WIFI ON`, `*WIFI OFF`, `*LAP`, `*LAPOPT`, `*JOIN`, `*JOIN ?`,
  `*LEAVE`, `*ONLINE`, `*IFCFG`, station `*MODE`, `*PING`, `*DATE`, `*TIME`,
  `*WGET`, `*UEF LOAD`, `*MENU`, `*MENUSRC`, `*PRD`, `*WICFS` and `*REWIND`.
- [x] Persistent WiFi profile, menu source and LAPOPT settings.
- [x] Open, WEP, WPA and WPA2 association modes, with automatic reconnect from
  a saved profile.
- [x] MENU download validation, transfer reporting and runtime conversion of
  the published cartridge bank-select sequence.
- [x] Escape-aware scan, DNS, ICMP, NTP, HTTP and raw socket waits. Pi-side
  cancellation releases PCBs, clears scan state and invalidates late callback
  generations.
- [x] WiCFS MOS extended-vector installation without occupying Tube workspace.
- [x] Reset-safe WiCFS teardown. MOS rebuilds its vectors before ROM reset
  service calls, so 1MHzWifi clears its saved ownership record without
  restoring stale cassette predecessors over ADFS, DFS or MMFS.
- [x] Full 32-bit WiCFS catalogue addresses, caller-owned OSFILE control-block
  preservation,
  sequential reads, host loads and standard `&FFFFxxxx` Tube OSFILE
  destinations. WiCFS never uses an optional Tube as its Pi or JIM transport.
- [x] Filing-system-neutral local UEF import through OSFIND/OSBGET, with JIM
  selector restoration, bounded storage, Escape handling, and a two-stage
  automatic queue for the stock WiCFS `*REWIND`, `CHAIN ""` launch sequence.
- [x] DFS-neutral source import and ownership-checked DFS vector restoration.
  The ROM does not inspect DFS structures or retain state in DFS workspace.
- [x] Content-based raw, gzip and single-entry ZIP UEF normalization in the
  Pi kernel, including gzip-in-ZIP, CRC validation and expanded-size bounds.
- [x] Stack-safe OSFILE control-block preservation for loads which overwrite
  the previous `&09DA/&09DB` save area.
- [x] Write-only `&FCFF` handling across the public OSWORD driver. Function 9
  returns a local four-byte `OK` response, and function 13 advances multi-page
  receive data through a RAM page shadow rather than hardware readback.
- [x] Original-compatible OSWORD function 18 response limited to station IP,
  real station MAC, and `OK`; Pi-only status fields moved to `*ONLINE`.
- [x] Removal of emitted UART, AT-command, flash updater, printer, baud-rate,
  CRC diagnostic and unused ROM helper code.
- [x] Explicit `Not implemented` errors for every retained driver entry which
  has no safe Pi1MHz meaning. No unsupported entry falls through to legacy
  cartridge code.
- [x] Clean ROM builds from independent ElkWiFi checkouts produce the same
  16 KiB image.
- [x] Both Pi kernels compile and link from a clean current Pi1MHz checkout.
- [x] ROM contract tests and upstream Pi1MHz services, net and web parser tests
  pass. The Pi host tests run under ASan and UBSan.

## Deliberately unsupported

These are closed failure paths, not partial implementations:

- `*WIFI SR` and `*WIFI HR`. Pi1MHz has no ElkWiFi cartridge UART reset
  target, so both return `Not implemented`.
- AP and station-plus-AP modes, TCP server mode, transparent mode, UART baud
  control, cartridge watchdog control, printer output and cartridge flash
  update.
- WGET ATM and Atom-in-PC container decoders which depend on the removed
  cartridge transport.
- HTTPS and TLS through the ElkWiFi-compatible `*WGET` path. Secure requests
  fail closed and never downgrade to plain HTTP. SSH is available separately
  through the native host tool and managed Pi secure service.

## Future product scope

The following work would expand the declared product rather than complete a
half-written path in this release:

- [ ] Add a maintained bare-metal TLS stack, certificate store, hostname and
  time validation, then enable HTTPS for WGET and MENU.
- [x] Provide a separate Pi1MHz secure-service ABI and native SSH client with
  verified host keys, known-host persistence, authentication and cancellation.
- [x] Rebase the imported secure service to commands 94-100, with 94-113
  reserved. Commands 92 and 93 remain `*ONLINE` and UEF normalisation.
- [ ] Add AP/APSTA support only with a DHCP server, client-list contract and
  complete teardown semantics.
- [ ] Add a paged scan-result ABI if more than four BSS records must be exposed
  without exceeding the stock 240-byte response.
- [ ] Add power-failure-safe temporary-file and rename updates for saved
  profiles and menu settings if deployment requirements justify it.
- [x] Provide a Pi1MHz Services mailbox and JIM device for Elkulator. The
  maintained adapter is in `emulator/pi1mhz-mailbox` and includes command 93
  for compressed UEF tests.
- [x] Add a maintained AP5 Tube ULA and external 3 MHz 65C02 parasite model to
  the Elkulator integration. A configured Tube starts during cold boot, as it
  does with PiTubeDirect, and reproduces the physical 0.1.25 failure after
  `ZALAGA 05 05EE` loads.

## Outstanding ElkWiFi compatibility work

Compatibility is measured at the public OSWORD `&65` entry, not only through
star commands. The target is one unchanged application binary on an original
ElkWiFi 0.23 cartridge and on 1MHzWifi.

- [x] Implement bounded functions 0 and 1 as volatile TCP resets which preserve
  the Pi WiFi association and saved profile.
- [x] Implement functions 3, 4, 5, 8, 9, 13, 14, 18, 20, 23, 24, 25 and 28 on
  the Pi1MHz transport. Function 9 accepts `0`, CR as the original
  single-connection setup and does not dispatch a mailbox request.
- [x] Start every public response at JIM `00:00:00`, maintain a RAM shadow for
  write-only `&FCFF`, terminate text where space permits, and maintain the
  two-byte response length used by original callers.
- [ ] Add an automated 6502 harness which enters through MOS service reason 8
  and OSWORD `&65`. It must execute functions 0, 3, 4 query, 5, 8, 9, 13, 14,
  18, 20, 23 and 24 against the assembled ROM rather than calling private ROM
  labels or the Pi service directly.
- [ ] Run that harness against both the unmodified ElkWiFi 0.23 ROM and the
  current 1MHzWifi ROM. Record byte-level response differences and either
  remove them or document why an exact match is impossible on Pi1MHz.
- [ ] Boot the unchanged `ELKNET` diagnostic from `../elkChat`, then the
  unchanged ElkChat SSD. Prove Network Status, association query, TCP open to
  `www.chat64.nl:80`, complete function 13 HTTP response collection, close,
  registration, public chat, private chat and user list on Elkulator.
- [ ] Repeat the unchanged ElkChat test on the physical Electron, AP5 and
  Pi1MHz setup, both with and without the Tube enabled. No Pi-specific client
  branch or function number is acceptable.
- [ ] Compare all applicable star commands, help text, response framing and
  MOS errors with an original cartridge. Preserve deliberate differences such
  as the 1MHzWifi identity, `*MENUSRC`, `*ONLINE`, compressed UEF support and
  explicit rejection of cartridge-only hardware operations.

## Outstanding native network-tools work

The former 1mhzNetTools backlog is part of this repository and must not be
tracked elsewhere.

- [ ] Replace the executable `PING`, `NSLOOK`, `FTP`, `HGET` and `VIEWDAT`
  placeholders with complete clients, or remove each command from NETMENU and
  the released SSD until it is implemented.
- [ ] Complete VT100 insert, delete and erase character operations, line
  insert/delete, scroll margins, terminal modes, tab clearing, DA/DSR replies,
  cursor-position replies, Home/Delete/function-key mappings and reply-queue
  backpressure.
- [ ] Add long-running shell, editor and `top` fixtures for TERM and SSH.
- [ ] Implement the Viewdata/Prestel parser, MODE 7 renderer, input mapping and
  fragmented-page fixtures.
- [ ] Implement HGET HTTPS with certificate and hostname validation plus
  power-failure-safe output replacement. Implement FTP passive transfers and
  native PING/NSLOOK service calls.
- [ ] Qualify TERM and SSH on physical BBC Micro, Master and Electron systems,
  including DFS, ADFS, MMFS and Tube coexistence where applicable.
- [ ] Repeat the physical `*SSH` test with the rebuilt SSD now shipped as
  `build/pi1mhz-all/host-tools/nettools.ssd`. The 0.1.22 client
  timed out at capability command 94 because its tight busy loop completed
  before the ordinary Pi firmware poll. The new bounded 300-frame dispatch
  wait passes a delayed-poll 6502 emulator fixture. The assembled SSD also
  completes a real public-key-authenticated SSH shell under Elkulator without
  `&2D`; physical hardware remains the open gate.
- [ ] Run the complete secure-service test matrix on both shipped Pi kernel
  families and all supported WiFi boards. Include changed-host rejection,
  password failure, Escape cancellation, reconnect, long sessions and power
  loss during known-host persistence.

## Release gate

No implementation placeholder remains on the declared 1MHzWifi ROM
station-mode, plain-HTTP command surface. The unified native-tools SSD still
contains the placeholders listed above. ROM 0.1.30 reaches visible Zalaga,
Arcadians, Last of the Free and E-Type gameplay in the AP5-accurate live
Elkulator profile without a Tube. Castle of Riddles reaches its interactive
command prompt. Frak still needs a fresh 0.1.30 gameplay capture. 1MHzWifi does
not access or disable the Tube, but this build has not passed the Tube-enabled
emulator gate or the physical-hardware WiCFS gate.

The current Tube-enabled 0.1.30 reproduction downloads Zalaga, installs WiCFS,
rewinds and loads `ZALAGA 05 05EE`, then returns to the parasite prompt. The
remaining defect is command ownership: the remote menu returns before its
`CHAIN ""` input is interpreted, so active parasite BASIC consumes it. Resolve
that launch on the I/O processor without transferring the UEF to Tube RAM,
issuing `TUBE OFF`, resetting the Tube, or changing the stock cassette command
sequence. Then rerun the no-Tube game matrix before accepting the correction.
The recorded 0.1.22 Electron test downloads Zalaga and loads its initial
`ZALAGA 05 05EE` file, then returns to Tube BASIC. Review found that WiCFS
discarded the upper half of the caller's OSFILE address and always wrote into
host RAM. ROM 0.1.24 and 0.1.25 attempted Tube transfers and selected the wrong
processor for host loaders. ROM 0.1.30 removes that path, preserves the stock
menu `REWIND` and `CHAIN ""` sequence, and keeps Pi and JIM transport entirely
on the 1MHz bus. Its five-pop extended-vector unwind fixes the returning
first-stage loader used by E-Type. Release acceptance still depends on
physical hardware and proving that
Break restores BeebSCSI ADFS, normal ADFS, DFS, MMFS and TAPE/CFS, and
completing the real Electron, AP5, Pi1MHz and Tube checks in
[`docs/hardware-validation.md`](docs/hardware-validation.md). Failures found
there must be recorded as new implementation defects before changing this
status.

The minimum hardware release profile is a 32K Electron with Plus 1, AP5,
Pi1MHz and Electron MMFS. It must pass without Plus 2, sideways RAM, ADFS or a
Tube. The matching Elkulator profile now mounts MMFS and runs the Desk Diary
UEF end to end; physical execution and filing-system recovery after Break are
still required.

After the 0.1.30 Tube-active and filing-system reset corrections pass on physical hardware, the ROM
version moves to a 0.9.x release-candidate series. Version 1.0 requires the
original-ElkWiFi OSWORD comparison and all filing-system coexistence gates.
Unfinished NetTools clients do not block the ROM release unless they require a
host-visible ABI change.
