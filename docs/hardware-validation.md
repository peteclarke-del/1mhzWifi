# Hardware validation plan

Use this checklist for each release candidate. Record the Acorn model and MOS,
expansion hardware, Tube parasite, Pi model, Pi1MHz upstream commit, ROM and
kernel hashes, access point, SD card, and power arrangement. Do not record real
WiFi passwords.

An item checked against an earlier binary must be repeated after a ROM, kernel,
or protocol change that can affect it.

## Current artifact identity

```text
Pi1MHz       d08242ee1b35cf1285b72c9ec1869e98081a8c3e
1MHzWifi ROM ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb
kernel.img   0a9beedc77d7828a6f5a1a1126f40f47ef601f2a2534840f70d416089d85534a
kernel7.img  ea7273028a547ef314d2af70f27ed8f4392a7d15a6652df091f67062d5e1c1c9
nettools.ssd a44d87062f5af4a84271816fa321d39f6c9220576f5d438affee98ae50630187
bundle ZIP   bb6be65644ca70a5104c9d9c8a14d25129050d185ca2aa932a726fd78e9a349d
```

The Pi1MHz commit was the official `master` tip verified on 15 August 2026. Run
`./pi-side/check_upstream.sh` before producing another hardware-test bundle.

For this update, preserve the existing `Pi1MHz.cfg` and saved `ElkWiFi.*`
files. Replace `kernel.img` or `kernel7.img` for the fitted Pi, the host
`ElkWiFi.rom`, and the separately mounted `nettools.ssd`. The universal ZIP is
for a clean card and may contain a fresh configuration template.

Also preserve `/BeebSCSI0` and its `scsi*.dat` images. The bundle supplies the
ADFS ROM and default geometry configuration, not a BeebSCSI hard-disc image.

## Confirmed physical Tube-off milestone, 18 August 2026

The tested host ROM was
`build/pi1mhz-all/Pi1MHz/ElkWiFi.rom`, version 0.1.55, SHA-256
`ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb`.
The machine used the Electron, Plus 1, Plus 2, AP5, Pi1MHz, RAM expansion,
ADFS/BeebSCSI and MMFS installation with the Tube disabled.

WiFi association, `*MENU`, NetTools and local `*UEF LOAD` complete. PING,
TELNET, NSLOOK, SSH and HWDTEST run. MENU, WGET and UEF transfers are painfully
slow and require measured optimisation. SSH still forces MODE 4 rather than
preserving a suitable caller mode.

Frak loads and plays. Thrust reaches playable gameplay, but ADFS is no longer
available afterwards and Break or reset does not restore it; a full power
cycle is required. Repton 2 hangs as gameplay begins, Plan B remains unstable,
and Arcadians hangs after loading its final `4C 4C49` cassette block. These are
failed stability or filing-system recovery tests even though their initial
loads complete. Public Chat in the current ElkChat live SSD appends main or
Settings menu items, and Private Chat exits with `Bad program`. No Tube-enabled
result is inferred from this milestone.

The current candidate addresses both quick wins but has not replaced this
physical result. NetTools preserves a suitable caller mode and falls back to
MODE 4 only when the measured host boundary is too low. The relocated ElkChat
client restores the full JIM selector before each page access; its dual-ROM
Elkulator journey renders Public and Private Chat without Settings leakage or
`Bad program`. Retest both changes on the same Tube-off machine before updating
the confirmed milestone.

An experimental snapshot of host workspace `&0E00-&1CFF` produced a positive
emulator differential for the ADFS loss, but peer review rejected it. Restoring
filing-system workspace from this ROM's reset service depends on ROM service
order and can overwrite a newer ADFS, DFS or MMFS owner. The experiment is not
part of the build. The replacement must recover only vector components still
owned by WiCFS and must pass the full Break, ADFS catalogue/read and second-load
sequence before physical Tube-off confirmation.

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
- [x] Cold-boot the current ROM with the photographed ROM order and reach the
  BASIC prompt with the AP5 Tube disabled.
- [ ] Repeat the 0.1.55 cold boot with the AP5 Tube enabled. The run must
  contain the exact `AP5 Tube: external 3MHz 65C02 enabled` startup marker.
- [x] Boot ROM 0.1.55 with Electron OS, BASIC and ADFS in Elkulator. Confirm
  both ROM banners and a BASIC prompt.
- [ ] Repeat current-ROM MENU acceptance with reviewed, title-specific gameplay
  references, input-correlated state changes, complete stream hashes and close
  events. The 0.1.54 Tube-off and Tube-on FrakV2 runs met every gate and used the
  same 30,070-byte payload with SHA-256
  `d1062885c830fad654a1c22075b2024d1973364134f8f4d23b4c38677ea2c3bf`,
  but they do not sign off 0.1.55.
- [x] Run `*UEF LOAD THRUST` with ROM 0.1.55, Tube disabled, the photographed
  ROM order and the real read-only BeebSCSI LUN. The complete three-file load
  reaches the instruction screen. Two separate Space inputs advance through
  the score screen into active gameplay. The automated runner now requires
  the full two-key sequence and uses a longer conservative timing window.
- [ ] Repeat the same 0.1.55 Thrust test with the Tube enabled. Earlier Tube-on
  results used 0.1.54 and must not sign off this binary.
- [ ] Repeat the complete MENU title matrix with the 0.1.55 hardware-test ROM. The
  THRUST and live FrakV2 gameplay evidence is retained, but the complete
  catalogue requires its own run.
  The full catalogue remains a physical and batch-emulator gate. The earlier
  Tube-active return to the parasite prompt remains a regression fixture.
- [ ] Run `*VERSION` in Elkulator and verify both copyright lines.
- [ ] Run `*WICFS`, then literal `*REWIND`, and verify an immediate prompt
  return. Elkulator's expansion ROM becomes unavailable after `*TAPE`, so this
  transition must be proved on AP5 hardware.
- [ ] Run uppercase `*HELP WIFI` and `*VERSION`; verify the ROM identifies as
  `1MHzWifi 0.1.55` before recording any further hardware test result.
- [x] Boot the photographed ROM layout in Elkulator: RH Plus 1 1.33
  in C, BASIC in B, writable sideways RAM in 7 and 6, AFM 1.09 in 5,
  1MHzWifi 0.1.55 in 3, and Acorn ADFS 1.00 in 1. Run the live `*MENU` and
  satisfy the strengthened FrakV2 gameplay gate with the AP5 Tube disabled and
  enabled. The complete catalogue remains a separate unchecked gate.
- [ ] Boot the minimum supported layout in Elkulator: 32K Electron, Plus 1,
  AP5-constrained Pi1MHz mailbox, 1MHzWifi 0.1.55 and a user-supplied MMFS ROM.
  No Plus 2, sideways RAM, ADFS or Tube is present.
  Mount a FAT32 Pi SD-card image containing `BEEB.MMB`, select fixture disc
  507, catalogue `DESK`, run `*UEF LOAD DESK`, and satisfy an application-state
  reference rather than generic screen motion.
- [x] Run `*IFCFG` with no services-mailbox device. Confirm a bounded error and no rows of spaces.
- [x] Run `*MENUSRC` with no services-mailbox device. Confirm a bounded error and return to BASIC.
- [x] Add a Pi1MHz services-mailbox and JIM bridge to Elkulator and run live
  Internet command tests.

Existing captures are stored under `tests/elkulator/screenshots/`. They are
reference material, not proof for a later binary. The
maintained adapter models the Pi1MHz mailbox, JIM, AP5 address decoder, Tube
ULA and an external 3 MHz 65C02. A configured Tube starts during cold boot,
matching PiTubeDirect. Earlier catalogue runs established identical UEF bytes
between Tube states, but their generic framebuffer comparisons do not meet the
current gameplay acceptance rule. Physical hardware remains the final gate.

## Filing-system matrix

Use the same ROM and matched Pi kernel for every row. Changing the filing
system must not require a 1MHzWifi ROM rebuild, a different command path, or a
fixed sideways-bank allocation. For every source filing system, run `*UEF
LOAD` on the same raw UEF and compressed Desk Diary fixture, reach the
application rather than the BASIC prompt, then reselect and catalogue the
source filing system after WiCFS finishes or after Break.

Repeat the ROM-level smoke test with 1MHzWifi in at least three materially
different banks, including one below bank 8 and one above it. The automated
OSWORD harness exercises all sixteen MOS-supplied ROM numbers. Full emulator
runs select the bank with `--wifi-rom-slot`; relocate any displaced profile ROM
explicitly. Sideways RAM may also occupy any bank. `*WGET -S` must succeed for
each writable bank under test and reject a ROM bank without damaging it.

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
the 1MHz bus, 1MHzWifi and a user-supplied compatible filing-system ROM. This
profile must not require a Plus 2, sideways RAM, ADFS or Tube. Filing-system
ROMs are test inputs and are not distributed by this project.

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

Earlier releases corrected the AP5 selector and WiCFS state corruption.
Versions 0.1.24 and 0.1.25 attempted Tube transfers, which was the wrong
architecture. Version 0.1.55 contains no Tube transfer path and preserves the
stock cassette sequence. The private host launch enters Electron BASIC and
queues `PAGE=&E00` before WiCFS so a Tube-active cold BASIC does not retain its
`&23xx` program workspace. Physical Tube-enabled gameplay remains the
acceptance gate.

The maintained Elkulator Tube model now provides a repeatable diagnostic gate.
With the photographed ROM order, live Pi1MHz Internet backend, ROM 0.1.54 and
the Acorn 1.20 Tube boot ROM, cold boot starts `Acorn TUBE 6502 64K`
automatically. `*MENU`, entered using `@` for the emulator's `*` key mapping,
waits for the traced `TITLES` close before selecting a title. Fresh FrakV2
runs complete the stock `*TAPE`, `*WICFS`, `*REWIND`, `CHAIN ""` sequence and
reach moving gameplay in both Tube states. The current batch runner applies
the same menu selection and WiCFS path to arbitrary sorted catalogue ranges.
An earlier first ten-entry 0.1.37 run
produced identical UEF hashes in every Tube-on/off pair. The experimental
0.1.38 MOS-managed handoff returned to the prompt and was rejected. ROM 0.1.40
restored the proven launch path and reached Frak, Zalaga and Arcadians gameplay
Tube off and Tube on. Last of the Free remained a `Bad program` failure in both
modes. ROM 0.1.54 retains the host-only architecture and current FrakV2
evidence. It does not copy a UEF
or game into parasite memory, issue `TUBE OFF`, reset the fitted Tube, or access
a Tube register.

- [ ] Confirm `Pi1MHz.cfg` contains active `Rampage_addr=0xFD`. Boot with ADFS,
  DFS, MMFS/SWRAM and other JIM users present; verify each can reselect its own
  address after 1MHzWifi commands.
- [ ] Download a known UEF with `*WGET -U` and verify the stored length metadata.
- [ ] Run `*WICFS`, `*CAT`, `*LOAD`, and `*RUN` against that UEF. Confirm the
  selected program reaches its execution address rather than returning to the
  BASIC prompt after the download.
- [ ] Retest Zalaga, Arcadians, Last of the Free, E-Type, Frak, Chuckie Egg
  and DeskDiary with ROM 0.1.55 on
  the physical Electron and AP5. Earlier physical builds failed on Zalaga and
  DeskDiary. Zalaga and Arcadians reach gameplay through the live Elkulator
  bridge without a Tube.
  Confirm every requested cassette file stops on its own final CFS block.
  Earlier ROMs called the loader compatibility helper before branching on
  that block's last-block bit. The helper changed the processor flags, so an
  OSFILE load could consume later files and finally report `End of UEF` or an
  invalid chunk type. Version 0.1.46 branches on the bit first, preserves the
  OSFILE control-block pointer on the active 6502 stack, returns catalogue
  metadata through that block, and does not touch the `&03E0-&03FF` keyboard
  command queue.
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
- [ ] Resolve the Arcadians final-file transition. The latest physical
  Tube-off run hangs after loading `4C 4C49`, so this is not a Tube-only
  exception. Capture the final UEF chunk, cassette status and execution
  transition with Tube off and on and compare them with the working Frak path.
  Do not add a title-specific loader path.
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
- [x] Run the first ten published catalogue entries through the automated
  Tube-on/off differential. Confirm identical UEF byte counts and SHA-256
  values for all pairs. Retain strict screen mismatches for visual review.
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
- [x] Run `*UEF LOAD THRUST` with Tube disabled and enabled. Confirm both reach
  live gameplay and the Tube-enabled path does not use Tube registers or a
  parasite destination.

## OSWORD application compatibility gate

- [x] Assemble the unchanged original-ElkWiFi ElkChat client and pass all 16
  deterministic bridge fixture tests. This checks the client and reference
  protocol fixtures, but does not replace entry through the Pi ROM's OSWORD
  service handler.
- [x] Enter 1MHzWifi through MOS service reason 8 and execute ElkChat-shaped
  OSWORD `&65` calls for functions 9, 18, 4, 8, 13 and 14. The executable
  test forces zero and partial TCP sends, waits through empty receive gaps and
  receives a response spanning several public JIM pages. It also checks
  bounded functions 0, 3, 5 and 24. This test uses
  ElkChat's original ABI and does not call private ROM labels.
- [ ] Run ElkChat's `ELKNET` diagnostic with `*RUN ELKNET` against the original
  ElkWiFi 0.23 ROM. Record function 18 IFCFG, function 4 JOIN query and
  function 8 TCP-open responses.
- [ ] Repeat the unchanged original-ElkWiFi ElkChat path with the 1MHzWifi
  0.1.55 hardware-test ROM
  and the kernel revision reported by the bundled `*VERSION`. None of the
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

The 0.1.44 physical diagnostic trace failed before useful Pi progress was
visible: NSLOOK printed `>2D S00 <2A`, and SSH printed `>5E S5E <2A`. Pi 3A+
and Zero 2 W tests failed consistently, while a second Zero 2 W produced
intermittent NSLOOK success. This was not a board-specific protocol difference.
The diagnostic printed through MOS after selecting the global FCA6-FCA9 cursor,
so another active ROM could redirect the pending write. In 0.1.46 the trace is
emitted before selection, cursor ownership is interrupt-safe and the emulator
fixture redirects the cursor on every MOS output call to enforce the rule.

The subsequent 0.1.45 hardware run produced the same trace, corrupted
`*VERSION` immediately after the two ROM-local lines and blocked ElkChat's
public OSWORD calls. The shared failure identified the Pi bus publication path.
The pinned upstream tree contained a shadow-based optimisation for
`Pi1MHz_MemoryWrite` whose own change record said it had not been exercised
against a live Beeb read. Host/VPU writes are not guaranteed to update the ARM
shadow first, so publishing one byte could restore a stale value into the
adjacent FRED register in the same VPU word. In the Services pair this is
`&FCA8/&FCA9`, directly explaining a response byte being observed as the cursor
diagnostic. Version 0.1.46 restores the authoritative VPU-window
read/modify/write. The automated model starts with a deliberately stale ARM
shadow and verifies that the live adjacent selector survives publication.

The 14 August physical `*HWDTEST` capture then measured a separate emulator
discrepancy. The Electron reported `00 F0 FF 5E`, the sixteen-byte sequential
JIM test failed, and secure capability discovery timed out with `&2A`. The
emulator had completed every FCA9 auto-increment synchronously and therefore
reported `01 F0 FF 5E`. Pi1MHz performs that update from an asynchronous FIQ
callback, so a following host access cannot assume that the read-back cursor
has advanced. Version 0.1.49 makes every ROM and NetTools byte transfer
explicitly select its complete software-shadowed 24-bit address and then waits
for the bounded FCA9 callback acknowledgement before selecting the following address.
The executable tests run NSLOOK and a complete managed SSH session with
hardware auto-increment disabled, ensuring that the emulator no longer
conceals this dependency.

The Tube-off hardware capture also reported OSHWM `&1D00` while the 0.1.47
NetTools image was loaded at `&1900`. Its later text corruption is therefore
explained by filing-system workspace overlap, independently of the mailbox
failure. Version 0.1.49 loads at `&1D00` and every application checks both
OSHWM and HIMEM before continuing. This protects the measured configuration;
a future two-stage relocatable loader remains required for arbitrary workspace
layouts because a program cannot query MOS until after its initial load.

The first 0.1.48 hardware run refused HWDTEST with the generic memory-envelope
message and then produced only `r` for the Pi line of `*VERSION`. The latter is
ROM code and cannot be caused by the NetTools load address. Inspection found
that 0.1.48 acknowledged asynchronous FCA9 cursor updates in NetTools only,
while the ROM's ElkWiFi response copier still consumed consecutive FCA9 bytes
without waiting. Version 0.1.49 applies the same bounded acknowledgement to
the ROM command, OSWORD, WGET and response-copy paths. The HWDTEST refusal now
prints the actual OSHWM, HIMEM and executable range.

The matched 0.1.49 physical run then provided the missing distinction. With
the Tube disabled, HWDTEST passed, TELNET worked and NSLOOK resolved correctly,
but SSH reported `&27`, `*VERSION` still printed only `r` for its Pi line and
ElkChat blocked in User List and chat operations. The ROM had waited for the
FCA9 auto-increment callback after each data access, but it consumed FCA9
immediately after writing FCA6-FCA8. Pi1MHz publishes the newly selected data
byte from that selector callback too. A fast ROM or assembled NetTools client
could therefore consume stale FCA9 data before the selector callback ran.
The rejected 0.1.51 candidate added a bounded settling interval to every ROM
selector and data transaction. Although it passed the delayed-selector model,
it regressed MENU and local UEF loading on physical hardware. The current WGET
path still contains bounded mailbox and JIM settling and must not be described
as byte-identical to 0.1.49. The conservative emulator measures about 42
seconds for the 11,498-byte TITLES transfer. NetTools retains a CPU-local
bounded delay in its own mailbox transport. It
must not read FRED or JIM while waiting because another bus transaction can
replace the pending one-slot FIQ event. Automated tests
complete IFCFG, delayed `*VERSION`, SSH capability discovery, NSLOOK and a
managed SSH session, but the response timing changes still require hardware
validation.

Before repeating application tests, run the same released diagnostic binary in
Elkulator and on the physical machine:

```text
*HWDTEST
```

Capture each of the three screens through the final `*VERSION` output. The raw
auto-increment line is diagnostic rather than a pass gate: the current hardware
observation is `00 F0 FF 5E FAIL`, while the synchronous emulator reports
`01 F0 FF 5E PASS`. The release gate is `FCA9 callback ACK: PASS`,
`Addressed JIM block: PASS`, `Secure CAPS result=&00`, capability feature bits
`&03` or greater, and provider readiness byte `&01`. Version 0.1.55 correctly
reports FAIL for the physical `CAPS 1-5: 01 01 01 ...` result because managed
SSH is not ready. Compare the machine
byte, Tube byte, OSHWM, MEMTOP,
FILEV, FSCV, WORDV and complete ROM order between both runs. This separates a
MOS or ROM-layout mismatch from an `&FCA6-&FCAA` bus publication failure without
modifying ADFS, MMFS or DFS data and without touching Tube state.

- [ ] With the packaged 0.1.55 kernel and matching SSD, run `*NSLOOK example.com` with
  Tube disabled and enabled. It must print an IPv4 address, return normally,
  and never report `&2A` or `Bad program`.
- [ ] Run `*SSH user@host` with Tube disabled and enabled. Capability command
  94 must return immediately, then the managed wolfSSH session must reach host
  key verification or authentication without `&2A`.
- [ ] If the debug SSD is used, confirm NSLOOK starts `>2D <00` and SSH starts
  `>5E <00`. `S00` or `S5E` followed by `<2A` is still a failed dispatch, not
  an acceptable retry.
- [ ] Run ElkChat Network Status immediately after cold boot and after BREAK.
  OSWORD function 18 must return STAIP and STAMAC without blocking. Repeat with
  MMFS and ADFS active to exercise interrupt-side JIM cursor contention.
- [ ] Exercise ElkChat User List, Private Chat and Public Chat from the same
  SWRAM build. Verify each public response remains intact while MMFS or ADFS
  also uses JIM. Version 0.1.46 reselects the AP5 page for every response byte
  with interrupts masked and does not cache machine type in volatile heap.
- [ ] Qualify SSH host keys, public-key and password authentication,
  known-host persistence, cancellation and long sessions on physical hardware.
- [ ] Implement HTTPS before testing certificate chains, hostnames, clock
  policy, protocol minimums and failure paths.
- [ ] Capture traffic and confirm that every verification failure remains
  closed rather than retrying in plaintext.
