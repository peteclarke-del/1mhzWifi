# Engineering status

This file records the remaining product boundary after the current ROM and
Pi1MHz implementation pass. Hardware proving is tracked separately in
[`docs/hardware-validation.md`](docs/hardware-validation.md).

## Complete in this build

- [x] Bare-metal Pi1MHz service integration on reviewed upstream commit
  `8468a38f63b25785007a50912a3b32a596db8ff9`.
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
- [x] Full 32-bit WiCFS catalogue addresses, OSFILE metadata returns,
  sequential reads and Electron-only load and execution. WiCFS does not use
  an optional Tube as a source, destination or transport.
- [x] Filing-system-neutral local UEF import through OSFIND/OSBGET, with JIM
  selector restoration, bounded storage, Escape handling, and a two-stage
  automatic queue for the stock WiCFS `*REWIND`, `CHAIN ""` launch sequence.
- [x] Content-based raw, gzip and single-entry ZIP UEF normalization in the
  Pi kernel, including gzip-in-ZIP, CRC validation and expanded-size bounds.
- [x] Stack-safe OSFILE control-block preservation for loads which overwrite
  the previous `&09DA/&09DB` save area.
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
- HTTPS, TLS and SSH. Secure requests fail closed and never downgrade to plain
  HTTP or Telnet.

## Future product scope

The following work would expand the declared product rather than complete a
half-written path in this release:

- [ ] Add a maintained bare-metal TLS stack, certificate store, hostname and
  time validation, then enable HTTPS for WGET and MENU.
- [ ] Define an ElkWiFi extension ABI for SSH, including verified host keys,
  known-host persistence, authentication and cancellation.
- [ ] Add AP/APSTA support only with a DHCP server, client-list contract and
  complete teardown semantics.
- [ ] Add a paged scan-result ABI if more than four BSS records must be exposed
  without exceeding the stock 240-byte response.
- [ ] Add power-failure-safe temporary-file and rename updates for saved
  profiles and menu settings if deployment requirements justify it.
- [ ] Add a Pi1MHz services-mailbox device to Elkulator so live
  Pi-side commands can run without physical hardware.

## Release gate

No known implementation placeholder remains on the declared station-mode,
plain-HTTP hardware milestone. ROM 0.1.8 specifically requires hardware
confirmation that Zalaga and Chuckie Egg now continue after their initial
`CHAIN ""` load. Release acceptance also depends on completing
the real Electron, AP5, Pi1MHz and Tube checks in
[`docs/hardware-validation.md`](docs/hardware-validation.md). Failures found
there must be recorded as new implementation defects before changing this
status.
