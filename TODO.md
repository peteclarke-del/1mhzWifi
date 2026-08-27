# Engineering status

This file records the remaining product boundary after the current ROM and
Pi1MHz implementation pass. Hardware proving is tracked separately in
[`docs/hardware-validation.md`](docs/hardware-validation.md).

## Complete in this build

- [x] Bare-metal Pi1MHz service integration on reviewed upstream commit
  `e949f2d2714b15f314df375e52db5febb6c40e6d`.
- [x] Both Raspberry Pi kernel families and the complete SD-card bundle.
- [x] AP5-safe FRED/JIM transport with no dependency on cartridge `&FC30` UART
  registers.
- [x] `*WIFI ON`, `*WIFI OFF`, `*LAP`, `*LAPOPT`, `*JOIN`, `*JOIN ?`,
  `*LEAVE`, `*ONLINE`, `*IFCFG`, station `*MODE`, `*PING`, `*NSLOOK`, `*DATE`,
  `*TIME`, `*WGET`, `*UEF LOAD`, `*PRD`, `*WICFS` and `*REWIND`.
- [x] Persistent WiFi profile and LAPOPT settings.
- [x] Open, WEP, WPA and WPA2 association modes, with automatic reconnect from
  a saved profile.
- [x] Retire MENU, MENUSRC, their downloaded-code patcher and Pi cache while
  retaining generic WGET and UEF transport.
- [x] Escape-aware scan, DNS, ICMP, NTP, HTTP and raw socket waits. Pi-side
  cancellation releases PCBs, clears scan state and invalidates late callback
  generations.
- [x] WiCFS MOS extended-vector installation without occupying Tube workspace.
  Tube-off hosts also receive an interrupt-safe standard-vector gateway at
  `&0780`, below the observed `&0900-&10FF` cassette-loader overwrite range.
- [x] Reset-safe WiCFS teardown. MOS rebuilds its vectors before ROM reset
  service calls, so 1MHzWifi clears its saved ownership record without
  restoring stale cassette predecessors over ADFS, DFS or MMFS.
- [x] Full 32-bit WiCFS catalogue metadata returned through the caller-owned
  OSFILE control block, sequential reads and host-memory loads. WiCFS does not claim a
  Tube channel or use a parasite as a Pi, JIM or title-load destination.
- [x] Filing-system-neutral local UEF import through OSFIND/OSBGET, with JIM
  selector restoration, bounded storage, Escape handling, and a two-stage
  automatic queue. The first cassette file is structurally classified through
  the CR at its declared BASIC line boundary for `CHAIN ""`; all other loaders
  use `*RUN ""`.
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
- [x] Function 13 receive acceleration behind private Pi command 58. The Pi
  copies from `DISC_RAM_BASE`-relative raw-network scratch into the unbased
  `JIM_ram[0..65535]` public window while the ROM preserves the original
  page-zero start, two-byte length, page progression and trailing zero. An
  older kernel returns `Unsupported`, causing the ROM to use the established
  byte-at-a-time path.
- [x] Apply the same command 58 transport to untransformed paged WGET output,
  including UEF images. Text and MOS-file WGET modes retain their byte-at-a-time
  transformations. Unsupported kernels fall back
  without changing the public command behavior.
- [x] Original-compatible OSWORD function 18 response limited to station IP,
  real station MAC, and `OK`; Pi-only status fields moved to `*ONLINE`.
- [x] Removal of emitted UART, AT-command, flash updater, printer, baud-rate,
  CRC diagnostic and unused ROM helper code.
- [x] Explicit `Not implemented` errors for every retained driver entry which
  has no safe Pi1MHz meaning. No unsupported entry falls through to legacy
  cartridge code.
- [x] Clean ROM builds from independent ElkWiFi checkouts produce the same
  16 KiB image. The installer is repeatable after updating its final WiCFS
  patch detectors and retaining the install-failure guard in `uef.asm`.
- [x] Both Pi kernels compile and link from a clean current Pi1MHz checkout.
- [x] Incremental UEF window generation survives a complete overwrite of
  `&0900-&10FF`; the authoritative generation is stored in Pi-private JIM and
  restored before REFILL or APPEND requests.
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
  time validation, then enable HTTPS for WGET.
- [x] Provide a separate Pi1MHz secure-service ABI and native SSH client with
  verified host keys, known-host persistence, authentication and cancellation.
- [x] Use secure-service commands 94-100 for SSH and 101-113 for SFTP.
  Commands 92 and 93 remain `*ONLINE` and UEF normalisation.
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
- [x] Preserve pinned ElkWiFi 0.23 functions 29 to 31 as reserved. DATE,
  TIME and ONLINE use private ROM selectors 32-34 rather than occupying an
  original ElkWiFi function number.
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

- [x] Move PING and NSLOOK into the ROM and remove their duplicate NetTools
  programs.
- [x] Add ROM-resident passive FTP and a separate NetTools SFTP application.
  Both use the active MOS filing system for local GET and PUT files.
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
  power-failure-safe output replacement.
- [ ] Qualify TELNET and SSH on physical BBC Micro, Master and Electron systems,
  including DFS, ADFS, MMFS and Tube coexistence where applicable.
- [ ] Run the common ROM command and OSWORD matrix on BBC B, B+, Master,
  Master Compact and Electron. Verify OSBYTE `&81` selects `&FE05` only on
  Electron and `&FE30` on the BBC family. On non-Electron hosts, verify the
  compiled default `*MENU` is rejected and a target-specific custom
  `*MENUSRC` remains usable. Every result must use the same 16 KiB ROM hash.
  Create a separate BBC-family image only if a documented machine contract
  cannot be selected safely at runtime; convenience or untested assumptions
  are not sufficient reasons to split the image.
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

### Vector gateway relocation, 27 August 2026

`*UEF LOAD REPTON` stalls because Repton's second stage executes at `&0700`
and its decryption loop spans `&0700-&07A8`, replacing the 0.1.61 gateway while
FILEV, FINDV and FSCV still point into it. See the gateway location study in
[`docs/hardware-validation.md`](docs/hardware-validation.md).

- [x] Reproduce the failure and identify the overwritten gateway from a host
  RAM dump rather than from source reasoning.
- [x] Test the obvious fix. Removing the gateway reaches sustained Repton
  gameplay and leaves Thrust, Arcadians, Repton 2, Bumble Bee, Mr Wiz and
  Repton Infinity unchanged, but returns Last of the Free to the BASIC prompt.
  The extended-vector repair is load bearing, so the gateway must move, not go.
- [x] Quantify every candidate location across the 727 parseable corpus images
  and record that load-address analysis understates the risk, because Repton
  reaches `&0700` through a run-time copy.
- [ ] Free the cassette workspace. Only about 21 scattered bytes are available
  below the keyboard buffer at `&03E0`, so the 22-byte WiCFS state cache at
  `&0380` must move before a gateway can live in the least contended page.
  Reading it from Pi-private JIM on every OSBGET is too slow, so it needs a new
  home in host RAM or a smaller encoding.
- [ ] Shrink the gateway. It is currently 103 bytes because it calls OSBYTE
  `&A8` on every entry; caching the extended-vector table pointer at install
  time removes about 13 bytes, and the four entry stubs can be tightened.
- [ ] Re-run the differential with the relocated gateway. Repton must reach
  sustained gameplay and Last of the Free must still reach its start prompt
  from the same ROM. Both are required; either alone is not a fix.
- [ ] Trace `WICFS-017`. Repton Infinity stops at `Searching` with 63,886 of
  65,280 stream bytes unread, identically with and without the gateway.

### Physical Tube-off milestone, 21 August 2026

The matched 0.1.58 ROM and Pi Zero 2 kernel make further measurable progress on
the physical Electron, Plus 1, Plus 2, AP5, Pi1MHz, RAM expansion and
ADFS/BeebSCSI system with the Tube disabled:

- MENU launches Frak and Arcadians to playable gameplay.
- Plan B launches and runs.
- Local `*UEF LOAD REPTON` reaches gameplay, although startup remains very slow.
- After Frak, a subsequent `*MENU` hangs until a cold start.
- After Plan B, ADFS remains unavailable until a cold start.
- `*UEF LOAD MRWIZ` reports `UEF GZIP OK &3077 bytes in JIM` and then hangs
  before the cassette-loading sequence begins.
- SSH works, but a session started in MODE 0 switches to MODE 4 when the
  password prompt is displayed.

Treat the Frak and Plan B aftermath as one generic WiCFS ownership or filing
system teardown investigation. Do not add title-specific production paths.
The Mr Wiz stop is at the normalization-to-launch boundary and is distinct from
the earlier final-file hypothesis. Repton is now a successful gameplay gate;
retain its startup latency as a performance issue.

The 0.1.59 baseline passes the exact Tube-off Thrust emulator journey to
input-responsive, sustained gameplay with a live bus trace and zero Tube
register accesses. The complete extracted BeebSCSI UEF corpus passes structural
chunk, block-sequence and CRC validation. Repton 3, Repton Around the World and
Repton Infinity exceed the legacy 64 KiB stream. The current candidate now
implements the generic command-93 incremental protocol and passes raw, gzip,
ZIP, exact-window, public-JIM-reuse and retry tests. Physical validation of
these multi-window titles remains outstanding.

### Physical Tube-off milestone, 18 August 2026

`build/pi1mhz-all/Pi1MHz/ElkWiFi.rom` version 0.1.55, SHA-256
`ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb`,
with the matched Pi Zero 2 kernel now has a working physical Tube-off baseline.
WiFi association, WGET, `*MENU`, local `*UEF LOAD`, PING, TELNET, NSLOOK, SSH
and HWDTEST work. Preserve this exact artifact set before performance, loader
or Tube changes.

The full-stream candidate kernel has now extended that milestone. Frak and
Arcadians load through MENU and play, local `*UEF LOAD THRUST` plays, and ADFS
returns after every tested Break. A subsequent local Repton 2 load therefore
also proves that recovery survives more than one WiCFS session. Repton 2 still
stalls after reaching gameplay. Bumble Bee completes. Plan B 2 reaches its
application but Break then loses ADFS. Mr Wiz stops while loading the valid
final `MRWIZ4` file. Repton reaches its title screen, then reports `End of
UEF`, `Searching`, `Loading` and `Cannot write!`. Record entry into gameplay
separately from a stable application run.

- [x] Trace the filing-system vectors and workspace before `*UEF LOAD THRUST`,
  at the WiCFS completion boundary, and after Break in the integrated emulator.
  Thrust uses the MOS extended-vector area and the low filing-system workspace
  as normal tape RAM. A snapshot experiment proved that restoring those bytes
  can recover ADFS in the emulator, but peer review rejected the implementation
  because reset-service ordering makes arbitrary workspace restoration unsafe.
- [x] Implement an ownership-safe ADFS recovery path without restoring arbitrary
  host workspace. Invalid or inactive state must be passive; each extended and
  standard vector must be restored only while WiCFS still owns that component;
  BYTEV is restored only when it still equals the WiCFS trap. The ROM does not
  call OSBYTE `&8C` from reset. The full-stream physical run recovered ADFS
  after every tested Break.
- [x] Repeat load, gameplay, Break, `*ADFS` and a second UEF load
  in the exact emulator profile and on the physical Tube-off Electron. A power
  cycle must not be required. The physical run loaded Thrust, recovered ADFS,
  then opened Repton 2 from ADFS without a power cycle. A known-file read was
  not separately recorded, so retain that narrower check in the general
  filing-system matrix.
- [x] Trace Arcadians at the completed `4C 4C49` file boundary on the physical
  Tube-off baseline. The full-stream candidate now passes the boundary and
  reaches playable Arcadians without a title-specific workaround.
- [x] Add `scripts/uef_map.py` to decode raw, gzip, ZIP and ZIP-wrapped gzip
  images, validate exact chunk boundaries, decode CFS file and block metadata,
  verify cassette header/data CRCs, and report both the full length and the
  former last-`&0100` effective length. The exact staged BeebSCSI Arcadians,
  Bumble Bee, Mr Wiz, Plan B, Plan B 2, Repton family and Thrust files have
  continuous block sequences, valid final flags and valid CRCs. Desk Diary's
  valid zero-byte `V1` marker has a header CRC but no data CRC. These files all
  end in a carrier chunk followed by an integer-gap chunk, totalling 16 bytes
  which the earlier Pi path removed.
- [ ] Run the strict physical A/B/C UEF comparison. A is the untouched 0.1.55
  ROM and kernels. B is the candidate kernel with the full normalized stream
  and `elkwifi_uef_trim_tail=0`. C uses the same candidate kernel with
  `elkwifi_uef_trim_tail=1`. Record the final live page, offset, remaining
  length, CFS block status, OSFILE execution address and vector ownership.
- [x] Reconcile the clean-source ROM with the maintained patch series. A clean
  build reproduces the 0.1.62 candidate ROM at SHA-256
  `d74863484c6e52bc6a2c497d7c83210232c19844af2c6d729e87db4f49d346fa`.
  Physical compatibility gates remain required before promotion.
- [x] Move HWDTEST's JIM write/read probe from reserved WiCFS state at
  `&FFEF00` to `&FFEE00`. D4 verifies the 26-byte state record is unchanged and
  reports standard vectors, extended handler/owner tuples and the persisted
  state bytes for reset-lifecycle comparison.
- [ ] Trace Repton and Repton 2 from their final cassette blocks into the first
  failing filing-system or gameplay operation. Native Elkulator cassette
  loading of the exact BeebSCSI Repton image reaches the title, accepts Space
  and enters the game. WiCFS corrupts the lower title area before input and
  physical hardware prints `End of UEF`, `Searching`, `Loading`, then `Cannot
  write!`. The 0.1.58 candidate retains original ElkWiFi OSFIND `&C0`
  OPENUP handling, which the host-only patch had incorrectly routed to the
  output-error path. It also prevents Service 1 from restoring stale extended
  vectors after final-byte handling has already released BYTEV. The candidate
  assembles and passes its contract tests, and now reaches the Repton title
  instead of the earlier `Cannot write!` path. The exact Repton emulator run
  still stops at a corrupted title instead of gameplay. Capture the physical
  OSFIND request and the first divergent FILEV/FSCV transition before accepting
  the UEF path as complete. Do not add a title-specific path.

- [x] Stop the NetTools loader from unconditionally selecting MODE 4. It now
  preserves a caller mode whose host HIMEM covers the exact tool image and uses
  MODE 4 only for an insufficient boundary. The terminal renderer reads the
  active MOS text window and supports 20 through 80 columns. Assembled 6502
  tests prove a suitable 80-column mode survives password authentication and
  an insufficient stock MODE 0 falls back exactly once at entry. Physical
  Tube-off confirmation remains required.
  Any future 80-column or enhanced terminal mode must be an explicit user
  option and must restore the previous mode on exit where the MOS permits it.
- [ ] Measure the accelerated physical mailbox/JIM transfer path. `*MENU`
  title-data loading, WGET and UEF streaming are currently functional but
  unacceptably slow. The current physical run took about two minutes to WGET
  each of Frak and Arcadians, followed by slow cassette playback. Record exact
  byte counts and elapsed times before changing bus settling or polling. Do
  not remove delays merely because a synchronous emulator passes. The 0.1.59
  bundle removes the host byte loop for raw paged WGET and OSWORD receive, but
  its improvement still requires elapsed-time measurements on hardware.
- [ ] Complete physical ElkChat validation in the relocated `8bit-net`
  workspace. The client now performs every selector-plus-data JIM access as an
  interrupt-masked transaction using the proven settling interval, sends all
  HTTP requests with a 16-bit length, and identifies itself so the local server
  returns bounded, pageable responses below its 4K parser window. The full Elkulator
  journey passes through both Pi1MHz and the original ElkWiFi ROM, and its
  OSWRCH trace proves Public Chat emits no Settings labels and Private Chat does
  not exit through `Bad program`. Physical hardware contradicts that result:
  latest hardware report has Public Chat working, while Private Chat opens but
  reports zero chats and the User List reports zero online users. Repeat those
  outcomes with the rebuilt live SSD. The current loader is itself at `&1900`, stages the SWR image at
  `&1B00-&5AFF`, and keeps runtime workspace from `&1B00`; all overlap an ADFS
  host whose OSHWM is `&1D00`. Replace it with an OSHWM-safe launcher which
  streams directly into SWR, relocate or allocate all main-RAM workspace above
  OSHWM, and refuse cleanly when no safe conventional layout exists. The staged BeebSCSI files match
  `elkchat-live-base.ssd`, not the current live build. Reproduce the exact ADFS,
  AP5, SWR and ROM order, embed a build ID, then fix the shared client without
  adding a Pi-only network path.
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
