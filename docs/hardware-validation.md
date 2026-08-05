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
ElkWiFi ROM  b8761bde7d651f3f7faa4386666208ee2e4c2042bed00057a46b294ecdec9480
kernel.img   2332d082ed4b235007fdf8ad50baf99bdf322126af78c3e0f024f9db75d4a6f0
kernel7.img  2825bfc5f0302816c23304bb0fa0f800dd775e9d58dda8487469e5ea7b0cfad7
bundle ZIP   bd3adecda9a76cc85fc7d2b96029fd590bcbf2270ed91b5809721056b528f56e
```

For this update, preserve the existing `Pi1MHz.cfg` and saved `ElkWiFi.*`
files. Replace only `kernel.img` or `kernel7.img` for the fitted Pi, plus the
host `ElkWiFi.rom`. The universal ZIP is for a clean card and may contain a
fresh configuration template.

Also preserve `/BeebSCSI0` and its `scsi*.dat` images. The bundle supplies the
ADFS ROM and default geometry configuration, not a BeebSCSI hard-disc image.

## Automated and emulator gate

- [x] Verify the ROM is exactly 16 KiB and matches the recorded SHA-256.
- [x] Run all Python contract tests.
- [x] Verify the universal ZIP and the ROM embedded within it.
- [x] Boot the ROM in Elkulator with Electron OS and BASIC.
- [x] Run uppercase `*HELP WIFI` and verify the ElkWiFi 0.23 banner and retained commands.
- [x] Boot with ADFS, MMFS/SWRAM, and a Tube ROM present. Confirm the WiFi and ADFS banners reach the BASIC prompt without `Buffer full`.
- [x] Run `*IFCFG` with no services-mailbox device. Confirm a bounded error and no rows of spaces.
- [x] Run `*MENUSRC` with no services-mailbox device. Confirm a bounded error and return to BASIC.
- [ ] Add a Pi1MHz services-mailbox device to Elkulator and run live command tests.

Existing captures are stored under `tests/elkulator/screenshots/`. They prove
ROM startup and missing-service behavior only. Elkulator models the original
cartridge UART, not the Pi1MHz mailbox, Plus 5 forwarding, or Tube transfers.

## Cold boot and bus gate

- [ ] Before running any WiFi or MENU command, run `*ADFS` and `*CAT`. Confirm
  the expected BeebSCSI volume mounts from `/BeebSCSI0/scsi0.dat`.
- [ ] After a failed or successful MENU/WiCFS launch, run `*ADFS` and `*CAT`
  again. Confirm ADFS reclaims the filing-system vectors without resetting.
- [ ] Boot the current ROM with the Pi powered down. Confirm the BASIC prompt appears without a hang or `Buffer full`.
- [ ] Boot the current matched kernel and ROM. Confirm the BASIC prompt appears before a WiFi command is issued.
- [ ] Run `*HELP WIFI`; confirm the current command list and no screen-row corruption.
- [ ] Run `*WIFI ON`; confirm a WiFi-capable Pi reports ready and a Pi without WiFi reports `Device not found`.
- [ ] Run `*WIFI ON` twice; confirm both calls complete and the second call does not lose the service registration.
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
- [ ] Confirm `*IFCFG` reports non-zero address, gateway, and netmask values.
- [ ] Power-cycle the Pi and Acorn; confirm the saved profile associates automatically.
- [ ] Run `*LEAVE`; confirm disassociation and no automatic rejoin until another `*JOIN`.
- [ ] Immediately run `*IFCFG` after `*LEAVE`; confirm link `DOWN`, state
  `IDLE`, and zero IP, gateway, and netmask values.
- [ ] Run `*WIFI OFF`; confirm `WIFI OFF` and `OK`, then confirm `*IFCFG`
  reports the disabled state, link `DOWN`, and zero network addresses.
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
  `Downloading menu`, the counted `WGET OK` line with range and header, and
  `Starting menu` appear, the cartridge
  `&FC34` bank-select sequence is adapted for `&FCFE`, and host `&E00` starts
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

- [ ] Download a known UEF with `*WGET -U` and verify the stored length metadata.
- [ ] Run `*WICFS`, `*CAT`, `*LOAD`, and `*RUN` against that UEF. Confirm the
  selected program reaches its execution address rather than returning to the
  BASIC prompt after the download.
- [ ] Run `*MENU`, press `L` for Zalaga, and confirm the menu proceeds directly
  to `CHAIN""` after the download. The verified stock MENU must not queue its
  redundant `*REWIND` line.
- [ ] Select a MENU title with the Tube off and then on. In both cases confirm
  `WGET OK`, WiCFS activation, and execution of the downloaded program.
- [ ] Test sequential open/read, EOF, rewind, Escape, malformed UEF, and recovery.
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

## Tube gate

- [ ] Run `*HELP WIFI`, `*MENUSRC`, `*MENU`, `*WGET`, and `*WICFS` from the I/O processor.
- [ ] Repeat applicable commands from each supported Tube parasite.
- [ ] Run `*MENU` with the Tube enabled. Confirm the menu UI executes on the
  I/O processor, title data uses host JIM window 1, and no parasite `&0E00`
  execution or BASIC `CALL` occurs.
- [ ] Trace calls and confirm only the I/O processor accesses `&FCxx` and `&FDxx`.
- [ ] Exercise every pointer-bearing OSWORD `&65` call with buffers in parasite memory.
- [ ] Load a UEF file to parasite RAM and trace cassette filing system claim
  `&C0`, Tube operation 1 at `&0406`, an R3 status-bit-6 wait before each
  `&FEE5` write, and release
  `&80` after the final block. Repeat with a malformed or truncated UEF and
  confirm the error path also releases the claim.
- [ ] Run a UEF file with a parasite execution address and trace claim `&C0`
  followed by Tube operation 4 at `&0406`; operation 4 releases implicitly.
  Repeat with an `&FFFFxxxx` host execution address and confirm it runs on the
  I/O processor without claiming R3/R4.
- [ ] Select `Aardvark/Zalaga_E.uef` from `*MENU` with the Tube enabled. Confirm
  the BASIC stage at `&2800`, loader at `&0400`, parasite data at `&8000`, and
  host image at `&FFFF0E00` all load and the game reaches its title screen
  without token text or a BASIC prompt.
- [ ] Confirm no WiCFS vector code occupies Tube workspace `&0400-&07FF` and no
  parasite pointer is passed directly to JIM.

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
