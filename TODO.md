# Implementation TODO

This is the complete known implementation backlog for the Pi1MHz ElkWiFi
extension as of the current matched ROM/kernel build. Hardware proving is
tracked separately in `docs/hardware-validation.md`; an item appears here when
code, protocol definition, automated coverage, or packaging work is still
required.

## P0: command correctness and safe failure

- [ ] Hardware-verify the `*MENU`/`*MENUSRC` P0 fix. `MENUSRC` now precedes
  its `MENU` prefix in the ROM table. MENU verifies the WGET transfer, patches
  the published menu payload's cartridge bank-select sequence for `&FCFE`, and
  enters host `&E00` only for a non-empty download. Confirm get, set, DEFAULT,
  successful, failing, and empty cases on real hardware.
- [ ] Extend Escape cancellation beyond `*PING`. PING now cancels DNS/ICMP,
  removes the raw PCB, and exits its inter-packet wait. Add equivalent Pi-side
  cancellation for NTP, scan, JOIN, DHCP, HTTP, and socket operations without
  allowing a late completion to be consumed by the next command.
- [x] Implement genuine `*WIFI OFF`. It now sends `WLC_DOWN`, stops DHCP,
  clears live interface addresses, and leaves the services mailbox responsive.
- [x] Implement genuine `*WIFI ON` after OFF. It now sends `WLC_UP` without
  reloading the resident firmware and restarts association for a saved profile.
  Hardware validation of repeated OFF/ON cycles remains in the validation plan.
- [ ] Implement `*WIFI SR` as a real soft reset. Define the exact contract,
  restart the CYW43 software/runtime state without toggling its power rail,
  cancel all ElkWiFi DNS/ICMP/NTP/scan requests, and optionally restore the
  previous association. It currently performs only a status request.
- [ ] Implement `*WIFI HR` as a real hardware reset. Toggle `WL_REG_ON`, reload
  firmware/CLM/NVRAM, rebuild lwIP state, and optionally restore association.
  It currently performs only a status request.
- [ ] Hardware-verify the OSWORD safe-rejection fix. Driver functions outside
  the explicit Pi1MHz map, including direct update/flash function `&FE`, now
  return stock `Not implemented` before the inherited UART/flash dispatcher.
  Confirm the error behavior from native Electron and Tube callers.
- [ ] Make host reset cancellation explicit. A reset during scan, DNS, ICMP,
  NTP, JOIN, DHCP, WGET, or an OSWORD socket operation must release its lwIP
  PCB/state, clear the one-slot request mailbox, and allow the next command to
  start immediately without leaking a PCB or completing into an obsolete JIM
  command page.
- [ ] Add generation/request IDs to asynchronous ElkWiFi callbacks. Late DNS,
  raw-ICMP, UDP/NTP, scan, or association callbacks must be unable to complete
  a newer request that reused the same static state.

## P0: complete OSWORD &65 compatibility

Audit every public ElkWiFi 0.23 driver function against a real cartridge and
record its parameter block, response bytes, timing, and errors. The current
mapping is incomplete even where star commands work.

- [ ] Function 0, init: replace the status alias with defined Pi-side
  initialization semantics.
- [ ] Function 1, reset: route it to the real soft/hard reset contract rather
  than the status alias.
- [ ] Function 6, `CWSAP`: implement access-point configuration if supported,
  or reject it safely and explicitly.
- [ ] Function 9, `CIPMUX`: implement/query connection multiplexing or document
  and return a compatible single-connection result; it is currently a no-op.
- [ ] Function 10, `CWLIF`: implement associated-client listing when AP mode is
  implemented, otherwise return an explicit unsupported response.
- [ ] Function 11, set buffer: implement the host-visible buffer contract; it
  is currently a no-op.
- [ ] Function 12, `CIPSTATUS`: report real socket/link state rather than the
  fixed `STATUS:3` string.
- [ ] Function 15, `CIPSERVER`: implement or safely reject TCP server mode.
- [ ] Function 16, `CIPSTO`: implement or safely reject server timeout.
- [ ] Function 17, baud: decide the Pi compatibility result. There is no UART,
  and the current fixed `115200` response is synthetic.
- [ ] Function 19, update: return explicit unsupported without entering any
  flash code.
- [ ] Function 21/22, watchdog enable/disable: implement meaningful Pi runtime
  behavior or explicitly reject; both are currently no-ops.
- [ ] Function 23, mux channel: confirm the exact carry/Y convention for
  single-channel mode against real ElkWiFi hardware.
- [ ] Function 26, SSL buffer size: connect it to a future TLS transport or
  reject explicitly; it is currently a no-op.
- [ ] Function 27, `CIPMODE`: implement/query transparent mode or reject
  explicitly; it is currently a no-op.
- [ ] Test pointer-bearing OSWORD calls from every supported Tube parasite.
  Define and implement all required I/O-processor/parasite buffer copying;
  never pass a parasite address directly to Pi JIM memory.

## P1: star-command parity

- [ ] Compare the ROM command table, abbreviation matching, whitespace,
  quoting, output, error text, and return behavior byte-for-byte with a real
  ElkWiFi 0.23 cartridge.
- [ ] `*MODE`: decide whether full cartridge parity requires modes 2 (AP) and
  3 (station+AP). If yes, implement CYW43 AP/APSTA configuration, DHCP server,
  client listing, and teardown. The current supported surface is deliberately
  station-only (`1` and `?`).
- [ ] `*LAPOPT`: implement the complete ElkWiFi option-bitmask contract rather
  than only the common `7` and `127` values. Confirm persistence and exact
  field ordering.
- [ ] `*LAP`: remove the four-network truncation without exceeding the stock
  240-byte response buffer. Define paging/repeated-scan behavior compatible
  with the cartridge, escape handling, duplicate BSSID handling, hidden SSIDs,
  and scan-result ordering.
- [ ] `*JOIN`: verify quoted SSIDs/passwords and values containing spaces,
  commas, quotes, or leading/trailing whitespace. Add a safe way to forget the
  saved profile, distinct from `*LEAVE`, if the cartridge provides one.
- [ ] `*JOIN`: confirm AUTO negotiation against WPA1-only, WPA1/WPA2 mixed,
  WPA2-only, WEP40, WEP104, and open APs. Add WPA3 only if it can be exposed
  without breaking the ElkWiFi contract.
- [ ] `*IFCFG`: compare every line, label, field, ordering, and down/joining
  state with the cartridge. Decide whether DNS, DHCP state, SSID, security,
  and signal strength belong in the compatibility response or only in the
  additive diagnostics.
- [ ] `*VERSION`: include an unambiguous Pi1MHz source/build identifier while
  retaining the exact ElkWiFi-compatible ROM/version output expected by host
  software.
- [ ] `*PING`: test IP literals, DNS names, unreachable hosts, ICMP errors,
  timeout timing, Escape cancellation, sequence wrapping, late replies, and
  repeated five-ping ROM behavior. Add automated lwIP callback tests rather
  than source-string tests.
- [ ] `*DATE`/`*TIME`: validate NTP originate/transmit timestamps, server mode,
  stratum, leap state, and source address. Add multiple NTP server fallback,
  cache a successful time to avoid a new DNS/UDP transaction per command, and
  handle the NTP 2036 and Unix 2038 boundaries.
- [ ] `*DATE`/`*TIME`: decide whether automatic GMT/BST rules are required.
  The current `elkwifi_utc_offset_minutes` setting is manual and therefore
  cannot change itself at daylight-saving boundaries.
- [ ] `*MENU`: maintain a reliable compiled default URL and verify that
  precedence remains saved `MENUSRC`, then `elkwifi_menu_url`, then the
  compiled default. Test unreachable, oversized, invalid, and non-executable
  payloads. Replace the narrow runtime signature adaptation with a versioned
  menu capability contract when a new published menu format is available.
- [ ] `*MENUSRC`: add HTTPS URLs once TLS exists. Confirm maximum length,
  redirect policy, malformed saved-file recovery, SD write failure, and exact
  `DEFAULT` semantics.
- [ ] `*WGET`: complete HTTP compatibility for redirects, chunked transfer,
  content length, connection-close bodies, DNS/connect/read timeouts, status
  errors, escape cancellation, maximum transfer size, and writes crossing JIM
  bank boundaries.
- [ ] `*WICFS`: prove and, where required, fix catalogue, load, run, sequential
  access, rewind, escape, malformed UEF, and error recovery using the Pi1MHz
  JIM windows. Ensure it cannot collide with service/net scratch pages.
- [ ] `*PRD`: verify bank 0/1 selection, selector restoration, escape exit, and
  AP5/Tube behavior. Reject out-of-range banks instead of silently masking
  them if that differs from the cartridge contract.

## P1: secure transports

- [ ] Link a maintained bare-metal TLS implementation into Pi1MHz/lwIP.
- [ ] Implement HTTPS for WGET, MENU/MENUSRC, and OSWORD secure-open without
  plaintext downgrade.
- [ ] Validate certificate chains, hostname/SAN, expiry, trust-store updates,
  SNI, protocol/cipher minimums, redirects, and failure behavior. Define how
  certificate time validation obtains trusted time before the first HTTPS
  request.
- [ ] Implement SSH only after defining its host-visible ElkWiFi extension
  ABI. Support host-key verification, authentication, known-host persistence,
  terminal/data transport, cancellation, and secret handling. Never accept an
  unknown host key silently or fall back to Telnet/plain TCP.
- [ ] Define SD-card storage and update policy for CA roots, SSH known hosts,
  and credentials. The current FAT configuration/profile storage is plaintext.

## P1: Pi1MHz configuration and persistence

- [ ] Add parser-level automated tests for `wifi_ssid`, `wifi_password`,
  `wifi_security`, `elkwifi_menu_url`, and
  `elkwifi_utc_offset_minutes`, including comments, spaces, empty values,
  invalid security, invalid URLs, and offset limits.
- [ ] Define and test precedence for Pi1MHz.cfg, legacy aliases, saved JOIN
  profile, saved MENUSRC, and compiled defaults. Invalid saved files must fall
  back deterministically without partially applying credentials.
- [ ] Preserve user-edited `Pi1MHz.cfg` when regenerating a bundle. The
  installer currently edits the upstream firmware copy and then copies it into
  the output tree; add an explicit template/merge policy so a rebuild cannot
  overwrite an SD-card configuration the user intended to retain.
- [ ] Make saved profile/menu writes power-failure safe using write-temp,
  flush/close, and atomic replace where FatFs permits it.
- [ ] Add a versioned settings format and migration tests for every persistent
  ElkWiFi file, including `ElkWiFi.wifi`, `.menu`, and `.lapopt`.
- [ ] Decide whether credentials should be obfuscated/encrypted or explicitly
  remain plaintext; document the threat model and recovery procedure.

## P1: automated functional testing

- [ ] Add a Pi1MHz services-mailbox device to Elkulator, including FCA6-FCAA,
  JIM auto-increment, busy completion, error injection, reset, and Tube
  marshalling. The current emulator tests cover only the service-absent path.
- [ ] Automate Elkulator command tests for every retained star command and
  OSWORD `&65` function, including screen/output assertions and escape/reset
  during asynchronous work.
- [ ] Add host-compiled unit tests for `elkwifi_service.c` with fake filesystem,
  clock, DNS, raw ICMP, UDP/NTP, scan, JOIN, and reset callbacks. Current tests
  mostly assert source/binary contracts and do not execute these state machines.
- [ ] Add deterministic packet fixtures for valid/malformed ICMP and NTP,
  HTTP edge cases, and delayed callbacks.
- [ ] Add clean-checkout CI that applies every ROM/Pi patch in order, builds
  the ROM plus `kernel.img`/`kernel7.img`, runs tests, verifies hashes where
  reproducible, and checks the ZIP contains the same ROM and current kernels.
- [ ] Add regression tests proving no retained command or OSWORD function can
  execute a read/write in the legacy cartridge UART range `&FC30-&FC3F`.
- [ ] Add memory-layout assertions for ROM size, JIM service pages, net scratch
  pages, WiCFS buffers, and both 64K logical windows.
- [ ] Add long-running fault tests: repeated JOIN/LEAVE, WiFi OFF/ON/SR/HR,
  DHCP loss, AP reboot, DNS failure, NTP failure, scan storms, large WGET, and
  host reset at every asynchronous phase.

## P2: source and bundle maintenance

- [ ] Remove or isolate unreachable upstream UART, printer, updater, flash,
  and AT-command bodies from the emitted ROM once exact layout compatibility
  has been settled. Dead code still exists even though its star commands were
  removed; it must not remain callable through direct driver entry points.
- [ ] Replace overlapping hand-maintained patch fragments with a maintainable
  integration branch or generated patch series, while retaining clean v1.30
  ancestry and reproducible application checks.
- [x] Update `pi-side/manifest.txt` to include every WiFi patch, validation
  test, implementation TODO, hardware checklist, and the universal ZIP.
- [ ] Generate build metadata and a machine-readable manifest containing ROM,
  kernel, firmware, Pi1MHz commit, patch-set version, and hashes. Display the
  same build ID through `*VERSION` and Pi diagnostics.
- [ ] Add release packaging that preserves executable bits, validates every
  required Broadcom firmware/NVRAM/CLM file, rejects stale artifacts, and
  emits a signed checksum file.
- [x] Reconcile current documentation with the implemented command surface,
  pinned upstream sources, release hashes, and known limitations. Repeat after
  the final byte-level cartridge audit.

## External validation still required

These are not missing implementations by themselves, but failures may create
new implementation work. Complete every unchecked item in
`docs/hardware-validation.md`, especially AP5 timing, PiTubeDirect/parasite
buffer transfers, all WiFi security modes, reset during active operations,
WiCFS/PRD JIM access, and long network transfers.
