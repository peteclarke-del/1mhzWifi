# Hardware validation plan

Use this checklist for each release candidate. Record the Acorn model and MOS,
expansion hardware, Tube parasite, Pi model, Pi1MHz upstream commit, ROM and
kernel hashes, access point, SD card, and power arrangement. Do not record real
WiFi passwords.

An item checked against an earlier binary must be repeated after a ROM, kernel,
or protocol change that can affect it.

## Current artifact identity

```text
Pi1MHz       516a267493d9f19e6bf2f4a2ea4c3e7472b12135
1MHzWifi ROM e26c9b977421b7965c36f6ca65e58367cef04797a75628c8a6687a4525b4d896
kernel.img   e4efcf39b62c448923ee9f68611725b93ae82e3d18a97cd13094a18bd9ebf15b
kernel7.img  1aa61d5b199204054ec018effab0a39f7a19b8cc3069741a02a91d95f8e4a771
EMMFS.rom    b6c766c9a469867cddc0b64900db1693565f59bb6a051dc1a36073e446165955
nettools.ssd a786f8c2ca59362e1c3bd02b25802e272cc8d6d080df06e9735c94ff22a1792f
bundle ZIP   4f7c7a693f695f533e9367a6eaeca8ac78866a37c764951012aee11a10864a0e
```

The Pi1MHz commit was the official `master` tip verified on 9 August 2026. Run
`./pi-side/check_upstream.sh` before producing another hardware-test bundle.

For this update, preserve the existing `Pi1MHz.cfg` and saved `ElkWiFi.*`
files. Replace only `kernel.img` or `kernel7.img` for the fitted Pi, plus the
host `ElkWiFi.rom`. The universal ZIP is for a clean card and may contain a
fresh configuration template.

Also preserve `/BeebSCSI0` and its `scsi*.dat` images. The bundle supplies the
ADFS ROM and default geometry configuration, not a BeebSCSI hard-disc image.

## Pi target matrix

| Board | Image | Required result |
| --- | --- | --- |
| Pi Zero | `kernel.img` | Boot succeeds; `*WIFI ON` reports no WiFi device |
| Pi Zero W | `kernel.img` | WiFi on, scan, join, reconnect, WGET |
| Pi Zero 2 W | `kernel7.img` | WiFi on, scan, join, reconnect, WGET |
| Pi 3A+, 3B, 3B+ | `kernel7.img` | WiFi on, scan, join, reconnect, WGET |

Run the same command sequence on every wireless board. Record the exact board
revision because the bundle selects among CYW43430, CYW43436/43436s, and
CYW43455 firmware at runtime.

## Automated and emulator gate

- [x] Verify the ROM is exactly 16 KiB and matches the recorded SHA-256.
- [x] Run all Python contract tests.
- [x] Verify the universal ZIP and the ROM embedded within it.
- [x] Boot ROM 0.1.22 with Electron OS, BASIC and ADFS in Elkulator.
  Confirm both ROM banners and a BASIC prompt.
- [x] Run `*MENU` with ROM 0.1.30 and the photographed ROM order without a
  Tube. The maintained AP5 model reaches visible gameplay for Zalaga,
  Arcadians, Last of the Free and E-Type. Castle of Riddles reaches its
  interactive command prompt.
- [ ] Repeat the complete 0.1.30 matrix after correcting Tube command ownership.
  A live Zalaga run with the Tube enabled downloaded `&7462` bytes, executed
  the stock `*REWIND` and `CHAIN ""`, loaded `ZALAGA 05 05EE`, then returned
  to the parasite prompt. This is the current failure boundary, recorded in
  `tube-zalaga-return-to-prompt-0.1.30.png`.
- [ ] Run `*VERSION` in Elkulator and verify both copyright lines.
- [ ] Run `*WICFS`, then literal `*REWIND`, and verify an immediate prompt
  return. Elkulator's expansion ROM becomes unavailable after `*TAPE`, so this
  transition must be proved on AP5 hardware.
- [ ] Run uppercase `*HELP WIFI` and `*VERSION`; verify the ROM identifies as
  `1MHzWifi 0.1.30` before recording any further hardware test result.
- [x] Boot the photographed non-Tube ROM layout in Elkulator: RH Plus 1 1.33
  in C, BASIC in B, writable sideways RAM in 7 and 6, AFM 1.09 in 5,
  1MHzWifi 0.1.28 in 3, and Acorn ADFS 1.00 in 1. Run the live `*MENU`, select
  Zalaga with `L`, and confirm the unmodified loader reaches visible gameplay.
- [x] Boot the minimum supported layout in Elkulator: 32K Electron, Plus 1,
  AP5-constrained Pi1MHz mailbox, 1MHzWifi 0.1.22 and the Electron normal-ROM
  Pi1MHz build of MMFS 1.60. No Plus 2, sideways RAM, ADFS or Tube is present.
  Mount a FAT32 Pi SD-card image containing `BEEB.MMB`, select fixture disc
  507, catalogue `DESK`, run `*UEF LOAD DESK`, and reach the running Desk
  Diary program menu.
- [x] Run `*IFCFG` with no services-mailbox device. Confirm a bounded error and no rows of spaces.
- [x] Run `*MENUSRC` with no services-mailbox device. Confirm a bounded error and return to BASIC.
- [x] Add a Pi1MHz services-mailbox and JIM bridge to Elkulator and run live
  Internet command tests.

Existing captures are stored under `tests/elkulator/screenshots/`. The
maintained adapter models the Pi1MHz mailbox, JIM, AP5 address decoder, Tube
ULA and an external 3 MHz 65C02. A configured Tube starts during cold boot,
matching PiTubeDirect. `tube-zalaga-return-to-prompt-0.1.25.png` records the
clean-install reproduction of the physical failure. The corresponding
`tube-arcadians-running-0.1.28.png` records the corrected host launch with the
Tube enabled. Physical hardware remains the final acceptance gate.

## Filing-system matrix

Use the same ROM and matched Pi kernel for every row. Changing the filing
system must not require a 1MHzWifi ROM rebuild, a different command path, or a
fixed sideways-bank allocation. For every source filing system, run `*UEF
LOAD` on the same raw UEF and compressed Desk Diary fixture, reach the
application rather than the BASIC prompt, then reselect and catalogue the
source filing system after WiCFS finishes or after Break.

| Source filing system | Required setup | Entry and recovery checks | Status |
| --- | --- | --- | --- |
| BeebSCSI ADFS | Acorn ADFS 1.00, AP5 and the existing `/BeebSCSI0/scsi0.dat` | `*ADFS`, `*CAT`, load, Break, `*ADFS`, `*CAT` | Physical gate |
| Normal ADFS | Plus 3 or equivalent 1770 ADFS media | `*ADFS`, `*CAT`, load, Break, `*ADFS`, `*CAT` | Pending with a MOS-valid writable fixture |
| DFS | 1770 DFS media containing the fixture | `*DISC`, `*.` (`@.` in Elkulator), load, Break, `*DISC`, `*.` | Desk Diary launch passed; recovery pending |
| MMFS | Electron MMFS in any suitable ROM or sideways-RAM bank with its normal SD/MMB backing | select image, `*CAT`, load, Break, reselect image, `*CAT` | Minimum-profile emulator launch passed; recovery and physical runs pending |
| TAPE/CFS | Native cassette UEF selected before 1MHzWifi use | `*TAPE`, catalogue/load, MENU or UEF launch, Break, `*TAPE` | Pending exact-profile rerun |

The ROM-side import is deliberately filing-system neutral. It opens the
caller's filename with MOS `OSFIND`, consumes it with `OSBGET`, and reselects
the Pi1MHz JIM window after every byte. Tests must nevertheless exercise each
row because ADFS, DFS and MMFS have different vector owners and workspace
usage. A DFS pass is not evidence for either ADFS variant or MMFS.

The first normal-ADFS fixture created with the legacy host `fstool` is not
valid acceptance evidence. Acorn ADFS itself reports `Bad FS map` from a plain
`*TYPE DESK`, before 1MHzWifi is entered. Keep that image out of regression
results and use media which passes a native ADFS open/read check first.

## Supported configuration profiles

The minimum release profile is a 32K Electron with a Plus 1, AP5, Pi1MHz on
the 1MHz bus, 1MHzWifi and Electron MMFS. The normal-ROM Pi1MHz MMFS build is
`MMFS/1/EMMFS.rom` in the official MMFS 1.60 release. This profile must not
require a Plus 2, sideways RAM, ADFS or Tube.

The stress profile reproduces the photographed machine: Plus 2, Plus 1, AP5,
Pi1MHz, BeebSCSI ADFS, MMFS, 32K sideways RAM and an optional Tube. Its ROM
order is useful regression evidence but is not an ABI. 1MHzWifi must discover
and coexist with the installed filing systems and expansion ROMs regardless
of their bank numbers.

## Cold boot and bus gate

- [ ] Before running any WiFi or MENU command, run `*ADFS` and `*CAT`. Confirm
  the expected BeebSCSI volume mounts from `/BeebSCSI0/scsi0.dat`.
- [ ] After a failed or successful MENU/WiCFS launch, run `*ADFS` and `*CAT`
  again. Confirm ADFS reclaims the filing-system vectors without resetting.
- [ ] Repeat the same pre-flight and recovery sequence with `*DISC` and `*.`.
  Confirm DFS remains available after Break and after a completed WiCFS load.
- [ ] Boot the current ROM with the Pi powered down. Confirm the BASIC prompt appears without a hang or `Buffer full`.
- [ ] Boot the current matched kernel and ROM. Confirm the BASIC prompt appears before a WiFi command is issued.
- [ ] Run `*HELP WIFI`; confirm the current command list and no screen-row corruption.
- [ ] Run `*WIFI ON`; confirm a WiFi-capable Pi reports ready and a Pi without WiFi reports `Device not found`.
- [ ] Run `*WIFI ON` twice; confirm both calls complete and the second call does not lose the service registration.
- [ ] With the Tube disabled, confirm the WiFi banner consumes one line and
  does not add a blank line.
- [ ] With the Tube enabled, confirm there is no blank line between the WiFi
  and Tube banners. Their relative order is determined by MOS ROM service
  order.
- [ ] Run `*LAP`; confirm the rows describe nearby access points rather than the configured SSID alone.
- [ ] Capture `nRST`, `PHI2`, `R/W`, address, data, and buffer enable for `&FCA6-&FCAA`.
- [ ] Compare setup and hold timing with an unmodified Pi1MHz V1.30-descended build.
- [ ] Run storage, AUN, audio, and ElkWiFi services concurrently; confirm command ranges and poll callbacks do not collide.

Expected error meanings:

| Error | Interpretation |
| --- | --- |
| `Device not found` before dispatch | Services mailbox is absent or not forwarded |
| `Device not found` after dispatch | Pi reports no usable WiFi hardware |
| `Not implemented` | Service range or requested function is unsupported |
| `No response from device` | A claimed request remained busy past its deadline |

## Association and persistence gate

- [ ] With no saved profile, confirm `*JOIN ?` reports `No AP`.
- [ ] Join an automatic WPA/WPA2 access point and wait for DHCP.
- [ ] Confirm `*JOIN ?` reports the associated SSID.
- [ ] Confirm `*IFCFG` reports the assigned IPv4 address and real station MAC.
- [ ] Run `*ONLINE` while DHCP is pending and confirm `OFFLINE CONNECTING`.
- [ ] Run `*ONLINE` after DHCP and confirm `ONLINE` followed by the assigned IPv4 address.
- [ ] Power-cycle the Pi and Acorn; confirm the saved profile associates automatically.
- [ ] Run `*LEAVE`; confirm disassociation and no automatic rejoin until another `*JOIN`.
- [ ] Immediately run `*IFCFG` after `*LEAVE`; confirm a zero IP address, then
  run `*ONLINE` and confirm the interface is offline.
- [ ] Run `*WIFI OFF`; confirm `WIFI OFF` and `OK`, then confirm `*IFCFG`
  reports a zero IP address and `*ONLINE` reports `OFFLINE WIFI OFF`.
- [ ] Run `*ONLINE` after `*WIFI OFF` and confirm `OFFLINE WIFI OFF`.
- [ ] Run `*WIFI ON`; confirm `WLC_UP` succeeds and the saved profile starts
  associating again without restarting the Pi.
- [ ] Test forced WPA, forced WPA2, WEP40, WEP104, and open profiles on isolated test access points.
- [ ] Test invalid keys, association rejection, DHCP failure, and access-point loss.
- [ ] Test SSIDs and passwords containing spaces, commas, quotes, and boundary lengths.
- [ ] Confirm configuration and profile precedence matches the documented order.

## Menu and HTTP gate

- [ ] Run `*MENUSRC`; confirm it prints the active URL and does not dispatch `*MENU`.
- [ ] Save a temporary HTTP URL with `*MENUSRC <url>` and read it back.
- [ ] Run `*MENUSRC DEFAULT` and confirm the default persists after power cycle.
- [ ] Run `*MENU` against the published ElkWiFi payload. Confirm
  `Downloading menu`, the counted `WGET RAW OK`, `WGET GZIP OK`, or
  `WGET ZIP OK` line with expanded length, and
  `Starting menu` appear, the cartridge
  `&FC34` bank-select sequence becomes an AP5-compatible no-bank helper, and host `&E00` starts
  the menu without a BASIC `CALL`.
- [ ] Confirm the first screen renders all 21 catalogue entries.
- [ ] With ADFS current, run `*MENU` without entering `*TAPE` first. Confirm
  the complete catalogue renders and a selected title runs.
- [ ] Run `*MENU` against DNS failure, refused connection, HTTP error, empty body, and timeout cases. Confirm none calls stale `&E00` memory.
- [ ] Cancel WGET with Escape during DNS, connect, empty wait, and body transfer.
- [ ] Test binary WGET across a main-memory page boundary.
- [ ] Test text modes, maximum transfer size, and a 30-minute repeated-transfer loop.
- [ ] Test redirects, chunked bodies, content length, and connection-close bodies; record unsupported cases.

## WiCFS and JIM gate

### Local physical-hardware evidence

The ignored `samples/` directory is retained as local test evidence. It is not
build output and must not be removed by repository cleanup. The current files
record tests on the Electron installation with Plus 2, Plus 1, AP5, a 6502
Tube, Pi1MHz on the 1MHz bus, ADFS, MMFS/SWRAM and BeebSCSI support present.

The 7 August 2026 photographs record these ROM 0.1.22 results:

- `20260807_180750.jpg`: raw Zalaga downloads as `&7462` bytes, WiCFS starts,
  `CHAIN ""` loads `ZALAGA 05 05EE`, then returns to the Tube BASIC prompt.
- `20260807_180801.jpg`: `*ROMS` and `*VERSION` identify 1MHzWifi 0.1.22,
  Acorn Tube 6502 64K, Acorn ADFS, RH Plus 1 and BASIC. The Pi reports kernel
  `V1.30-80-g8468a38-dirty.5cd08bdf`.
- `20260807_181024.jpg`: `*ONLINE` succeeds, but the native `*SSH` capability
  probe returns local timeout `&2A`.

`samples/sdcard.zip` is the complete FAT boot-partition capture from that
test. Its ROM and both kernels match the then-current 0.1.22 release hashes,
so these failures are not stale-deployment results. It also preserves the
active AP5, Services, BeebSCSI and WiFi configuration for comparison.

`Acornsoft Desk Diary (198x)(Acornsoft).uef` is the local compressed-UEF test
fixture used by the normalisation test. It remains ignored because it is
third-party test media. These files are observations from physical hardware,
not emulator acceptance evidence.

`samples/RHPLUS133.rom` is the exact RH Plus 1.33 dump from the test Electron.
Its SHA-256 is
`cda520a110b160af2c750b2d28c84353ad2c3ede15b4821cf96452ee4dc3b5f8`.
Exact-profile emulator runs load it in bank C. The earlier `ap6v133t.rom`
substitute is not acceptance evidence for this AP5 configuration.

Earlier releases corrected the AP5 selector and WiCFS state corruption, but
the current photographs isolate a Tube coexistence defect. Versions 0.1.24 and
0.1.25 attempted to solve it with Tube transfers. That was the wrong
architecture. Version 0.1.30 contains no Tube transfer path and preserves the
stock cassette sequence. Physical Tube-enabled gameplay remains the acceptance
gate.

The maintained Elkulator Tube model now provides a repeatable diagnostic gate.
With the photographed ROM order, live Pi1MHz Internet backend, ROM 0.1.25 and
the Acorn 1.20 Tube boot ROM, cold boot starts `Acorn TUBE 6502 64K`
automatically. `*MENU`, entered using `@` for the emulator's `*` key mapping,
downloads the `&7462`-byte Zalaga UEF and executes the stock `*TAPE`, `*WICFS`,
`*REWIND`, `CHAIN ""` sequence. It then loads `ZALAGA 05 05EE` and returns to
the prompt. This matches the physical failure boundary and remains a regression
fixture. It is not evidence that the current 0.1.30 Tube-enabled path passes.
The complete 0.1.30 game matrix must be rerun with the Tube model before the
emulator gate can be marked complete.

The 0.1.30 reproduction establishes that the UEF download, JIM transfer,
WiCFS installation, rewind and first OSFILE load all complete. The outstanding
Tube defect occurs after the published menu returns and its `CHAIN ""` input is
interpreted by the active parasite BASIC. WiCFS deliberately wrote the file to
Electron host memory, so returning to the parasite prompt is expected until the
launch remains in an I/O-processor language context. A correction must not copy
the UEF or game into parasite memory, issue `TUBE OFF`, or reset the fitted Tube.

- [ ] Confirm `Pi1MHz.cfg` contains active `Rampage_addr=0xFD`. Boot with ADFS,
  DFS, MMFS/SWRAM and other JIM users present; verify each can reselect its own
  address after 1MHzWifi commands.
- [ ] Download a known UEF with `*WGET -U` and verify the stored length metadata.
- [ ] Run `*WICFS`, `*CAT`, `*LOAD`, and `*RUN` against that UEF. Confirm the
  selected program reaches its execution address rather than returning to the
  BASIC prompt after the download.
- [ ] Retest Zalaga, Arcadians, Last of the Free, E-Type, Frak, Chuckie Egg
  and DeskDiary with ROM 0.1.30 on
  the physical Electron and AP5. Earlier physical builds failed on Zalaga and
  DeskDiary. Zalaga and Arcadians reach gameplay through the live Elkulator
  bridge without a Tube.
  Confirm every requested cassette file stops on its own final CFS block.
  Earlier ROMs called the loader compatibility helper before branching on
  that block's last-block bit. The helper changed the processor flags, so an
  OSFILE load could consume later files and finally report `End of UEF` or an
  invalid chunk type. Version 0.1.19 branches on the bit first, preserves the
  OSFILE control-block pointer on the active 6502 stack, leaves the caller's
  block unchanged, and does not touch the `&03E0-&03FF` keyboard command queue.
- [ ] After a title finishes or an explicit catalogue operation reaches the
  physical end of its UEF, press Break and
  confirm `*ADFS` is immediately available. Repeat with `*DISC`, Ctrl-Break
  and with a Tube enabled. MOS must rebuild the vectors and 1MHzWifi must not
  restore stale cassette predecessors over the filing system selected during
  the reset service pass.
- [ ] Run `*MENU`, press `L` for Zalaga, and confirm the private host entry
  queues the original `*REWIND` followed by `CHAIN ""` after the download. The
  ROM must not substitute `*RUN`, `*/`, or another launch command.
- [x] In the live Elkulator bridge, execute the complete published Zalaga UEF
  through WiCFS and confirm the title reaches gameplay. This covers the
  second-stage vector-reset signature and subsequent `Scrunch` and
  `ElkZalaga3` files without changing the stock launch commands.
- [x] Trace the initial Zalaga file under the photographed non-Tube ROM order.
  Confirm its relocated entry at `&13DA` matches the UEF byte for byte, issues
  the original `/` OSCLI shorthand, and reaches WiCFS FSCV reason 2 after the
  reason-8 notification is handled locally.
- [x] Select Arcadians as menu entry `O`; confirm the live 24,946-byte
  `Acornsoft/Arcadians_E.uef` download reaches its runnable game screen.
- [x] Put the gzip DeskDiary sample on an emulated DFS disc as `DESK`, run
  `*UEF LOAD DESK`, confirm normalization from 10,631 to 20,580 bytes, and
  reach the application's `ADDRESS`/`PLANNER` menu without another command.
- [ ] With the exact RH Plus dump and Tube enabled, select Planner. Both the
  WiCFS stream and Elkulator's untouched native cassette path currently stop
  after the final `23 2301` block. Treat this as a Tube-model or application
  compatibility investigation, not evidence of missing WiCFS bytes.
- [ ] Put the 29,794-byte Zalaga UEF on a DFS image, run
  `*UEF LOAD ZALAGA`, verify `UEF RAW OK &7462 bytes in JIM`, and confirm the
  game reaches its title screen through the two-stage queued WiCFS launch with
  no additional keystrokes.
- [ ] Repeat `*UEF LOAD` from hardware DFS, the ADFS hard disc and MMFS, including
  a path-qualified filename, Escape, missing file, empty file, and an image
  larger than `&FFFE` bytes.
- [ ] Run `*UEF LOAD DESKDIARY` with the 20,580-byte expanded image. Confirm
  the final zero-byte `V1` CFS marker completes without `Unexpected EOF` and
  the application continues through its intended launch path on physical
  hardware. This path has passed under Elkulator from an emulated DFS disc.
- [ ] Repeat the local import with raw UEF, gzip UEF, a single-entry ZIP
  containing raw UEF, and a ZIP containing gzip UEF. Verify the reported
  format and expanded byte count, then test bad CRC, truncated deflate data,
  multiple-entry ZIP, and an expanded image larger than `&FFFE` bytes.
- [ ] Select a MENU title with the Tube off and then on. In both cases confirm
  a format-qualified `WGET ... OK`, WiCFS activation, and execution of the
  downloaded program.
- [ ] Test sequential open/read, EOF, rewind, Escape, malformed UEF, and recovery.
- [ ] While associated, press BREAK and time `*ONLINE`. Confirm the preserved
  Pi-side association is available within seconds and no full rejoin starts.
- [ ] Confirm `*PRD` can inspect both defined JIM windows and restores the selector.
- [ ] Test `*WGET -S` with valid sideways RAM and with no writable sideways RAM.
- [ ] Run WiCFS and another Pi1MHz JIM-using service concurrently; check for scratch-page collision.

## Ping and time gate

- [ ] Ping an IP literal and a DNS hostname.
- [ ] Test unreachable host, DNS failure, ICMP error, timeout, and repeated commands.
- [ ] Press Escape during DNS, ICMP reply wait, and the delay between PING
  attempts. Confirm the command returns promptly and the next PING succeeds.
- [ ] Run `*DATE` and `*TIME`; compare with a trusted clock and configured UTC offset.
- [ ] Test DNS and NTP failures, repeated queries, invalid server packets, and reset during an outstanding request.

## Tube coexistence gate

- [ ] Run `*HELP WIFI`, `*MENUSRC`, `*MENU`, `*WGET`, and `*WICFS` from the I/O processor.
- [ ] Repeat applicable commands while each supported Tube is fitted and active.
  Any Pi, network or JIM traffic must remain on the 1MHz bus. Tube traffic is
  permitted only for application activity outside 1MHzWifi.
- [ ] Run `*MENU` with the Tube enabled. Confirm the menu UI executes on the
  I/O processor, title data uses the AP5-visible JIM window, and no parasite `&0E00`
  execution or BASIC `CALL` occurs.
- [ ] Trace calls and confirm only the I/O processor accesses `&FCxx` and `&FDxx`.
- [ ] Exercise every pointer-bearing OSWORD `&65` call with buffers in parasite memory.
- [ ] Trace a complete title load. Confirm 1MHzWifi never accesses Tube
  registers, claims a Tube channel or disables the Tube. Confirm the loader
  executes in Electron host memory and a Tube-aware game can still use the
  fitted processor itself.
- [ ] Select `Aardvark/Zalaga_E.uef` from `*MENU` with the Tube enabled. Confirm
  each stage reaches the destination requested by MOS and the game reaches its
  title screen without token text or an unexpected BASIC prompt.
- [ ] Confirm no WiCFS vector code occupies Tube workspace `&0400-&07FF` and no
  parasite pointer is passed to JIM or the 1MHz-bus Pi service.

## OSWORD application compatibility gate

- [x] Assemble the unchanged original-ElkWiFi ElkChat client and pass all 16
  deterministic bridge fixture tests. This checks the client and reference
  protocol fixtures, but does not replace entry through the Pi ROM's OSWORD
  service handler.
- [ ] Run ElkChat's `ELKNET` diagnostic with `*RUN ELKNET` against the original
  ElkWiFi 0.23 ROM. Record function 18 IFCFG, function 4 JOIN query and
  function 8 TCP-open responses.
- [ ] Repeat the unchanged original-ElkWiFi ElkChat path with 1MHzWifi 0.1.30
  and matched kernel revision `V1.30-83-g516a267-dirty.5e877218`. None of the
  calls may block or
  raise `Not implemented`.
- [ ] Call function 9 with a CR-terminated `0` parameter before function 8.
  Confirm it returns `OK`, reports response length `&0004`, and leaves JIM
  selected at `00:00:00` with the single connection available.
- [ ] Send an HTTP request with function 13, receive through functions 13/20,
  and close through function 14. Confirm the Chat64 response is present in JIM
  `00:00:page` across at least 16 pages and not in a DFS/MMFS-selected bank.
- [ ] Repeat with AP5, DFS and MMFS active, then with a Tube fitted. The Pi transport
  must remain the 1MHz bus and the application must not depend on the Tube.

## Reset and fault-recovery gate

- [ ] Reset during scan, association, DHCP, DNS, ICMP, NTP, connect, send, receive, and filesystem writes.
- [ ] After each reset, run `*WIFI ON` and one network command without rebooting the Pi.
- [ ] Repeat `*WIFI OFF`/`*WIFI ON` cycles before, during and after association.
- [ ] Confirm `*WIFI SR` and `*WIFI HR` return the documented explicit
  `Not implemented` error without changing radio state.
- [ ] Confirm late callbacks cannot complete a newer request.

## Secure transport gate

Managed SSH is implemented in the Pi firmware and native `SSH` host tool.
HTTPS and TLS are not implemented.

- [ ] Qualify SSH host keys, public-key and password authentication,
  known-host persistence, cancellation and long sessions on physical hardware.
- [ ] Implement HTTPS before testing certificate chains, hostnames, clock
  policy, protocol minimums and failure paths.
- [ ] Capture traffic and confirm that every verification failure remains
  closed rather than retrying in plaintext.
