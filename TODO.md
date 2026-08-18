# Engineering status

This file records the remaining product boundary after the current ROM and
Pi1MHz implementation pass. Hardware proving is tracked separately in
[`docs/hardware-validation.md`](docs/hardware-validation.md).

## Complete in this build

- [x] Bare-metal Pi1MHz service integration on reviewed upstream commit
  `d08242ee1b35cf1285b72c9ec1869e98081a8c3e`.
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
- [x] Full 32-bit WiCFS catalogue metadata returned through the caller-owned
  OSFILE control block, sequential reads and host-memory loads. WiCFS does not claim a
  Tube channel or use a parasite as a Pi, JIM or title-load destination.
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
- [x] Atomic shared-JIM access for generic command output, PING, local UEF
  import and WGET finalisation. Electron/AP5 leaves `&FCFD/&FCFE` untouched;
  BBC-family hosts explicitly select upper bank `00:00`.
- [x] Pi1MHz FCAA selector-echo handling and partial TCP-send retry in the
  public OSWORD function 13 path, including zero-byte backpressure and
  fragmented receive tests.
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
- [ ] Add an extended UEF tool family after the current loader and filing-system
  matrix is qualified. Proposed commands are `*UEF TLOAD <file>` for a bounded
  accelerated path, `*UEF CAT <file>` for cassette-file metadata,
  `*UEF EXTRACT <file> [directory]` for reconstructing MOS files with load and
  execution addresses, and `*UEF CREATE <file> [directory]` for producing a
  standards-compliant cassette sequence. Keep UEF, gzip and ZIP parsing on the
  Pi; keep all ADFS, DFS and MMFS catalogue, OSFILE and metadata operations in
  the host ROM. Turbo mode must fall back to normal WiCFS semantics for chunks
  or custom loaders which cannot be safely accelerated.
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
- [x] Add an automated 6502 harness which enters through MOS service reason 8
  and OSWORD `&65`. It executes functions 0, 3, 4 query, 5, 8, 9, 13, 14, 18
  and 24 against the assembled ROM rather than calling private ROM labels or
  the Pi service directly. Function 13 crosses several JIM pages.
- [x] Extend the executable harness to cover functions 20 and 23 independently.
  Confirmed the original `call_claimed` epilogue (unchanged from upstream
  routines.asm) always restores the caller's own X/Y and reports only claim
  status through A=0, so function 23's internal `Y=&FF` write is never
  observable to any caller on either the original cartridge or 1MHzWifi.
- [ ] Run that harness against both the unmodified ElkWiFi 0.23 ROM and the
  current 1MHzWifi ROM. Record byte-level response differences and either
  remove them or document why an exact match is impossible on Pi1MHz.
- [ ] Boot the unchanged `ELKNET` diagnostic from `../elkChat`, then the
  unchanged ElkChat SSD. ELKNET, Network Status, association query, TCP open to
  `www.chat64.nl:80`, complete function 13 HTTP response collection, public
  chat, private conversations and a two-cycle user-list refresh now pass on
  the current Elkulator binary. Exercise new-account registration separately;
  the live SSD already contains credentials and therefore cannot prove it.
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

- [x] Ship completed PING and NSLOOK clients with functional tests. Keep FTP,
  HGET and Viewdata out of NETMENU and the released SSD until implemented.
- [ ] Complete VT100 insert, delete and erase character operations, line
  insert/delete, scroll margins, terminal modes, tab clearing, DA/DSR replies,
  cursor-position replies, Home/Delete/function-key mappings and reply-queue
  backpressure.
- [ ] Add long-running shell, editor and `top` fixtures for TELNET and SSH.
- [ ] Add an optional 80-column TELNET/SSH display mode. Detect and claim a
  suitable host-side expansion or shadow-RAM provider at runtime, use it for
  screen backing and scrollback, and release it cleanly. Retain the current
  40-column ordinary-RAM path as the minimum 32K Electron fallback. A fitted
  Tube must remain available to applications and must never be used by the
  standard host build.
- [ ] Add an explicit 6502 Tube build of TELNET and SSH after the host build is
  qualified. Keep all Pi1MHz register, JIM and OSWORD access in a bounded
  host-resident gateway; use parasite RAM only for the application, display
  model, scrollback and protocol buffers. Do not auto-select this build merely
  because a Tube is present. Retain separate host binaries, and treat other
  parasite CPUs as separate ports rather than assuming 6502 compatibility.
- [ ] Apply the same optional host-gateway/parasite split to ElkChat without
  changing its public ElkWiFi OSWORD ABI. The normal ElkChat build must still
  run on a 32K host and against both the original cartridge and 1MHzWifi.
- [ ] Implement the Viewdata/Prestel parser, MODE 7 renderer, input mapping and
  fragmented-page fixtures.
- [x] Implement native PING and NSLOOK clients and service calls, with build
  and emulated-mailbox coverage.
- [ ] Implement HGET HTTPS with certificate and hostname validation plus
  power-failure-safe output replacement. Implement FTP passive transfers.
- [ ] Qualify TELNET and SSH on physical BBC Micro, Master and Electron systems,
  including DFS, ADFS, MMFS and Tube coexistence where applicable.
- [ ] Run the common ROM command and OSWORD matrix on BBC B, B+, Master,
  Master Compact and Electron. Verify OSBYTE `&81` selects `&FE05` only on
  Electron and `&FE30` on the BBC family. On non-Electron hosts, verify the
  compiled default `*MENU` is rejected and a target-specific custom
  `*MENUSRC` remains usable.
- [x] Remove sideways-bank assumptions from the ROM and emulator gate. The
  OSWORD service entry passes with MOS-supplied ROM numbers 0 through 15, the
  Elkulator runner accepts `--wifi-rom-slot 0..15`, and its report records the
  tested bank. `*WGET -S` continues to use and verify the caller-selected bank;
  no sideways-RAM bank is reserved implicitly.
- [ ] Repeat physical `*HWDTEST`, `*NSLOOK` and `*SSH` with the 0.1.55 SSD and
  matching kernel. The 0.1.46 hardware diagnostic established that immediate
  FCA9 auto-increment read-back differs from the synchronous emulator model.
  Version 0.1.55 waits for selector publication and the bounded FCA9 callback acknowledgement,
  validates OSHWM/HIMEM and tests NSLOOK and managed SSH with both asynchronous
  stages delayed. The 0.1.44 diagnostic
  SSD reported `>2D S00 <2A` for
  NSLOOK and `>5E S5E <2A` for SSH on a Pi 3A+ and Zero 2 W, with intermittent
  NSLOOK success on another Zero 2 W. Its trace called MOS after selecting the
  shared FCA6-FCA9 cursor, allowing another ROM to redirect the command write.
  The 0.1.45 retest still produced `>2D S00 <2A`, `>5E S5E <2A`, corrupted
  `*VERSION` after its second line and blocking ElkChat calls. `S5E` is the SSH
  command byte, not a valid Pi stage marker. This demonstrates corruption of
  the common Services cursor/data pair rather than independent DNS, SSH and
  ElkChat defects. Version 0.1.46 restores the authoritative VPU-window
  read/modify/write when publishing a single bus byte, so an `&FCA9` update
  cannot restore a stale ARM-shadow value into adjacent `&FCA8`. It also prints
  diagnostics first, masks IRQ while each request owns the
  cursor and tests the same interference in the executable host fixture. It
  also restores the upstream selector echo before fixed-command dispatch,
  keeps capability discovery independent of the poll table and makes Pi reset
  cleanup atomic against the FIQ request latch. The bounded 300-frame client
  wait remains in place. The assembled SSD completes a real
  public-key-authenticated SSH shell under Elkulator; physical hardware remains
  the open gate.
- [ ] Confirm 0.1.55 HWDTEST reports capability features `07` and readiness
  `01` on Pi Zero W, Zero 2 W and Pi 3. The 0.1.52 physical capture reported
  features `01` and readiness `00`; HWDTEST incorrectly called that PASS.
  Version 0.1.55 uses a wall-clock RNG deadline and treats that state as FAIL.
- [ ] Re-run direct TITLES WGET. If error `&30` remains, record the new
  `HTTP status &xxxx` line. The exact 11,498-byte response passes through the
  real Pi `net_service.c` test with an 8 KiB ring, 1460-byte segments,
  refused-pbuf retry and 240-byte reads. The reported status distinguishes an
  upstream response from request or parser corruption.
- [ ] Repeat `*MENU` and `*UEF LOAD` on physical hardware with ROM 0.1.55 after
  the WiCFS cursor, page, stream-start flag and remaining length were added to
  the transactional boundary checkpoints. The exact Tube-off Elkulator profile
  loads all three Thrust files and reaches active gameplay after the two
  required Space inputs. Tube-on 0.1.55 remains untested. Arcadians remains a known
  physical Tube-enabled exception at the end of its final cassette file; keep
  the documented Tube-off workaround unless a generic fix is demonstrated.
- [ ] Replace the fixed DFS application envelope with a reviewed two-stage,
  page-relocatable loader. The current applications cannot select their own
  load address because MOS must load their first instruction before OSBYTE
  `&83` can be called. Keep the `&1D00` runtime guard until the relocatable
  format and overlap-safe copy path have executable tests.
- [ ] Add optional scrollback allocation for TELNET and SSH through an identified
  JIM or sideways-RAM provider. Never assume a bank is spare, and retain the
  current no-scrollback behavior when no allocator is available. ElkChat must
  use the same optional capability without depending on it.
- [ ] Repeat ElkChat Network Status, User List, Private Chat and Public Chat on
  physical hardware. The 0.1.44 image hung in Network Status, returned `Unknown
  option` from User List and corrupted the chat/menu display. Version 0.1.46
  reselects the AP5's write-only JIM page with interrupts masked for every
  public response byte. Machine detection remains a documented OSBYTE `&81`
  query at driver entry; its result is not cached in volatile `&0900` heap.
- [ ] Run the complete secure-service test matrix on both shipped Pi kernel
  families and all supported WiFi boards. Include changed-host rejection,
  password failure, Escape cancellation, reconnect, long sessions and power
  loss during known-host persistence.

## Release gate

### Physical Tube-off milestone, 18 August 2026

`build/pi1mhz-all/Pi1MHz/ElkWiFi.rom` version 0.1.55, SHA-256
`ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb`,
with the matched Pi Zero 2 kernel now has a working physical Tube-off baseline.
WiFi association, WGET, `*MENU`, local `*UEF LOAD`, PING, TELNET, NSLOOK, SSH
and HWDTEST work. Preserve this exact artifact set before performance, loader
or Tube changes.

The milestone does not prove stable UEF application execution or filing-system
recovery. Frak loads and plays. Thrust reaches playable gameplay, but ADFS is
lost afterwards and cannot be reclaimed by Break or reset; only a power cycle
restores it. Repton 2 hangs as gameplay begins, Plan B remains unstable, and
Arcadians hangs after its final `4C 4C49` cassette block. Record entry into
gameplay separately from a stable application run and filing-system recovery.

- [x] Trace the filing-system vectors and workspace before `*UEF LOAD THRUST`,
  at the WiCFS completion boundary, and after Break in the integrated emulator.
  Thrust uses the MOS extended-vector area and the low filing-system workspace
  as normal tape RAM. A snapshot experiment proved that restoring those bytes
  can recover ADFS in the emulator, but peer review rejected the implementation
  because reset-service ordering makes arbitrary workspace restoration unsafe.
- [ ] Implement an ownership-safe ADFS recovery path without restoring arbitrary
  host workspace. Invalid or inactive state must be passive; each extended and
  standard vector must be restored only while WiCFS still owns that component;
  BYTEV must be restored only when it still equals the WiCFS trap. Do not call
  OSBYTE `&8C` from reset.
- [ ] Repeat load, gameplay, Break, `*ADFS`, catalogue/read and a second UEF load
  in the exact emulator profile and on the physical Tube-off Electron. A power
  cycle must not be required. Keep the canonical ROM at 0.1.55 until this gate
  and final peer review pass.
- [ ] Trace Arcadians at the completed `4C 4C49` file boundary on the physical
  Tube-off baseline. Compare the final UEF chunk, cassette status and queued
  execution transition with Frak. Do not add a title-specific workaround.
- [ ] Trace Repton 2 from its final cassette block into its first gameplay
  frame and identify the first non-returning call or corrupted vector.

- [x] Stop the NetTools loader from unconditionally selecting MODE 4. It now
  preserves a caller mode whose host HIMEM covers the exact tool image and uses
  MODE 4 only for an insufficient boundary or active Tube fallback. Assembled
  6502 tests cover both paths. Physical Tube-off confirmation remains required.
  Any future 80-column or enhanced terminal mode must be an explicit user
  option and must restore the previous mode on exit where the MOS permits it.
- [ ] Measure and optimise the physical mailbox/JIM transfer path. `*MENU`
  title-data loading, WGET and UEF streaming are currently functional but
  unacceptably slow. Record byte counts and elapsed times before changing bus
  settling or polling. Do not remove delays merely because a synchronous
  emulator passes.
- [x] Fix ElkChat in the relocated `8bit-net` workspace. The client now restores
  JIM address `00:00:page` before every response access. The full Elkulator
  journey passes through both Pi1MHz and the original ElkWiFi ROM, and its
  OSWRCH trace proves Public Chat emits no Settings labels and Private Chat does
  not exit through `Bad program`. The ignored live SSD was rebuilt from the
  existing 94-byte local `ELKCFG` without exposing or changing its contents.
- [ ] Repeat the Public Chat, Private Chat and User List journey on the physical
  Tube-off Electron using that rebuilt live SSD. Emulator evidence is not a
  substitute for this hardware result.
- [ ] Repeat this complete baseline with the Tube enabled only after the
  Tube-off screen-mode, performance and ElkChat defects are characterised.

No implementation placeholder remains on the declared 1MHzWifi ROM
station-mode, plain-HTTP command surface. The native-tools SSD ships only the
implemented TELNET, SSH and NETMENU programs. ROM 0.1.30 reached visible Zalaga,
Arcadians, Last of the Free and E-Type gameplay in the AP5-accurate live
Elkulator profile without a Tube. Castle of Riddles reached its interactive
command prompt. The current 0.1.55 ROM passes the exact Tube-off local Thrust
path. The earlier FrakV2 and Tube-enabled results used 0.1.54 and must be
repeated before they count for this candidate.

ROM 0.1.55 retains host-only WiCFS transfer and the Tube-active host
BASIC workspace. `QHOST` now queues `PAGE=&E00` before the internal WiCFS
second stage, so BASIC CHAIN continuation uses the same host address range
with Tube enabled and disabled. No Tube register is accessed and no program is
transferred to the parasite. The experimental 0.1.38 MOS-managed return was
rejected after reproducing its return-to-prompt failure in Elkulator. Version
0.1.40 includes corrected host address metadata, private filing workspace,
persistent stream cursor, the five-byte Electron MOS vector unwind, and the
generic host-BASIC handoff used by multi-stage loaders with a Tube active.
Physical gameplay across the wider catalogue and
post-Break filing-system restoration remain release gates.
The recorded 0.1.22 Electron test downloads Zalaga and loads its initial
`ZALAGA 05 05EE` file, then returns to Tube BASIC. Review found that WiCFS
discarded the upper half of the caller's OSFILE address and always wrote into
host RAM. ROM 0.1.24 and 0.1.25 attempted Tube transfers and selected the wrong
processor for host loaders. ROM 0.1.40 removes that path, preserves the stock
menu `REWIND` and `CHAIN ""` sequence, and keeps Pi and JIM transport entirely
on the 1MHz bus. Its successful-run trampoline discards the five MOS dispatcher
bytes while retaining the real caller return. The catalogue-wide differential runner is the
continuing regression gate; named titles are samples, not implementation
branches. Release acceptance still depends on
physical hardware and proving that
Break restores BeebSCSI ADFS, normal ADFS, DFS, MMFS and TAPE/CFS, and
completing the real Electron, AP5, Pi1MHz and Tube checks in
[`docs/hardware-validation.md`](docs/hardware-validation.md). Failures found
there must be recorded as new implementation defects before changing this
status.

The minimum hardware release profile is a 32K Electron with Plus 1, AP5 and
Pi1MHz. It must boot and expose the ROM command and OSWORD surfaces without
Plus 2, sideways RAM, a filing-system expansion or a Tube. DFS, ADFS and MMFS
are separate storage profiles, not requirements of the minimum machine. The
matching bare Elkulator profile now boots the current ROM and returns a clean
`*VERSION`; application and UEF tests use an explicitly declared storage
profile. Physical execution and filing-system recovery after Break are still
required.

After the 0.1.54 Tube-active, filing-system reset and WiFi association
corrections pass on physical hardware, the ROM
version moves to a 0.9.x release-candidate series. Version 1.0 requires the
original-ElkWiFi OSWORD comparison and all filing-system coexistence gates.
Unfinished NetTools clients do not block the ROM release unless they require a
host-visible ABI change.
