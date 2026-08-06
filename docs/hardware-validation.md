# Hardware validation plan

Use this checklist for each release candidate. Record the Acorn model and MOS,
expansion hardware, Tube parasite, Pi model, Pi1MHz upstream commit, ROM and
kernel hashes, access point, SD card, and power arrangement. Do not record real
WiFi passwords.

An item checked against an earlier binary must be repeated after a ROM, kernel,
or protocol change that can affect it.

## Current artifact identity

```text
Pi1MHz       8468a38f63b25785007a50912a3b32a596db8ff9
1MHzWifi ROM b9811c904b4fb2149b4a87ba0694d066f4f1c927148d28868bcfab0be58674d0
kernel.img   77d8904ad65c543ca2c015abf10dd5dfdb5b1e286d44446344e6cda0d68495ca
kernel7.img  abbdb49c13e09b1cc7cec1173ebdbaf3f71c40835cd6688cb530e3d2c341d08f
bundle ZIP   e415359f40a4782664a1b0705467de278df5a2d69c05c939b46411263fb12bbb
```

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
- [ ] Boot ROM 0.1.17 with Electron OS, BASIC and ACP 1770 DFS in Elkulator.
  Confirm both ROM banners and a BASIC prompt.
- [ ] Run `*VERSION` in Elkulator and verify both copyright lines.
- [ ] Run `*WICFS`, then literal `*REWIND`, and verify an immediate prompt
  return. Elkulator's expansion ROM becomes unavailable after `*TAPE`, so this
  transition must be proved on AP5 hardware.
- [ ] Run uppercase `*HELP WIFI` and `*VERSION`; verify the ROM identifies as
  `1MHzWifi 0.1.17` before recording any further test result.
- [x] Boot with ADFS, MMFS/SWRAM, and a Tube ROM present. Confirm the WiFi and
  ADFS banners reach the BASIC prompt without `Buffer full`.
- [x] Run `*IFCFG` with no services-mailbox device. Confirm a bounded error and no rows of spaces.
- [x] Run `*MENUSRC` with no services-mailbox device. Confirm a bounded error and return to BASIC.
- [ ] Add a Pi1MHz services-mailbox device to Elkulator and run live command tests.

Existing captures are stored under `tests/elkulator/screenshots/`. They prove
ROM startup, identity, command return and missing-service behavior. Elkulator
does not model the Pi1MHz mailbox, Plus 5 forwarding, or Tube transfers.

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
  `&FC34` bank-select sequence becomes a full `&FCFD-&FCFE` JIM selection, and host `&E00` starts
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

- [ ] Confirm `Pi1MHz.cfg` contains active `Rampage_addr=0xFD`. Boot with ADFS,
  DFS, MMFS/SWRAM and other JIM users present; verify each can reselect its own
  address after 1MHzWifi commands.
- [ ] Download a known UEF with `*WGET -U` and verify the stored length metadata.
- [ ] Run `*WICFS`, `*CAT`, `*LOAD`, and `*RUN` against that UEF. Confirm the
  selected program reaches its execution address rather than returning to the
  BASIC prompt after the download.
- [ ] Retest Zalaga, Arcadians, Chuckie Egg and DeskDiary with ROM 0.1.17.
  Confirm every requested cassette file stops on its own final CFS block.
  Earlier ROMs called the loader compatibility helper before branching on
  that block's last-block bit. The helper changed the processor flags, so an
  OSFILE load could consume later files and finally report `End of UEF` or an
  invalid chunk type. Version 0.1.17 branches on the bit first, holds OSFILE
  metadata on the active 6502 stack, and leaves the `&03E0-&03FF` keyboard
  command queue untouched.
- [ ] After a title finishes or an explicit catalogue operation reaches the
  physical end of its UEF, press Break and
  confirm `*ADFS` is immediately available. Repeat with `*DISC`, Ctrl-Break
  and with a Tube enabled. The ROM must restore only the FILEV, BGETV, FINDV,
  FSCV and BYTEV entries which are still owned by WiCFS.
- [ ] Run `*MENU`, press `L` for Zalaga, and confirm the published menu executes
  its original `*REWIND` followed by `CHAIN ""` after the download. The ROM
  must not substitute `*RUN`, `*/`, or another launch command.
- [ ] In the Elkulator preload harness, execute the complete published Zalaga
  UEF through WiCFS and confirm the title reaches gameplay. This covers the
  second-stage vector-reset signature and subsequent `Scrunch` and
  `ElkZalaga3` files without changing the stock launch commands.
- [ ] Put the 29,794-byte Zalaga UEF on a DFS image, run
  `*UEF LOAD ZALAGA`, verify `UEF RAW OK &7462 bytes in JIM 1`, and confirm the
  game reaches its title screen through the two-stage queued WiCFS launch with
  no additional keystrokes.
- [ ] Repeat `*UEF LOAD` from hardware DFS, the ADFS hard disc and MMFS, including
  a path-qualified filename, Escape, missing file, empty file, and an image
  larger than `&FFFE` bytes.
- [ ] Run `*UEF LOAD DESKDIARY` with the 20,580-byte expanded image. Confirm
  the final zero-byte `V1` CFS marker completes without `Unexpected EOF` and
  the application continues through its intended launch path.
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
  Any Tube traffic must be normal MOS or application activity, never ElkWiFi or
  WiCFS transport.
- [ ] Run `*MENU` with the Tube enabled. Confirm the menu UI executes on the
  I/O processor, title data uses host JIM address `00:01:page`, and no parasite `&0E00`
  execution or BASIC `CALL` occurs.
- [ ] Trace calls and confirm only the I/O processor accesses `&FCxx` and `&FDxx`.
- [ ] Exercise every pointer-bearing OSWORD `&65` call with buffers in parasite memory.
- [ ] Trace a complete title load and confirm WiCFS never accesses `&0406`,
  `&FEE4` or `&FEE5`, never claims the Tube and never transfers game data to a
  parasite. Repeat with no Tube fitted and with a Tube fitted and active.
- [ ] Select `Aardvark/Zalaga_E.uef` from `*MENU` with the Tube enabled. Confirm
  each stage remains in Electron memory and the game reaches its title screen
  without token text, a BASIC prompt or any Tube activity.
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
- [ ] Repeat the unchanged original-ElkWiFi ElkChat path with 1MHzWifi 0.1.17
  and matched kernel revision `V1.30-80-g8468a38-dirty.5ca5cd71`. None of the
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

Do not mark this section complete until TLS and SSH implementations exist.

- [ ] Validate certificate chains, hostnames, clock policy, protocol minimums, and failure paths.
- [ ] Validate SSH host keys, authentication, known-host persistence, and cancellation.
- [ ] Capture traffic and confirm that every verification failure remains closed rather than retrying in plaintext.
