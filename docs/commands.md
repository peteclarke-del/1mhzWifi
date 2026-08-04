# Command reference

Commands are entered through the MOS command line and therefore include the
leading `*`. `*HELP WIFI` must be uppercase on the target system.

## WiFi and configuration

| Command | Behavior | Status |
| --- | --- | --- |
| `*WIFI ON` | Initialises or probes the Pi WiFi runtime | Implemented |
| `*WIFI OFF` | Sends `WLC_DOWN`, clears the live lease and interface addresses, and leaves the mailbox available | Implemented |
| `*WIFI SR` | Cartridge UART soft reset | Explicitly unsupported |
| `*WIFI HR` | Cartridge hardware reset | Explicitly unsupported |
| `*LAP` | Lists nearby access points | Implemented; response is limited to four records |
| `*LAPOPT 7` | Selects compact scan rows | Implemented and persistent |
| `*LAPOPT 127` | Selects full scan rows | Implemented and persistent |
| `*JOIN <ssid> <password>` | Saves a profile and starts association | Implemented |
| `*JOIN ?` | Reports saved and live association state | Implemented |
| `*LEAVE` | Sends `WLC_DISASSOC`, clears the live lease and interface addresses, and pauses automatic rejoin | Implemented |
| `*IFCFG` | Reports live interface and MAC state | Implemented |
| `*MODE 1` | Selects station mode | Implemented |
| `*MODE ?` | Reports station mode | Implemented |

AP and station-plus-AP modes are not implemented. Unsupported modes are
rejected rather than reported as successful.

`*JOIN` accepts the standard two-argument ElkWiFi form. Optional security
selectors are carried in the password argument so that the command ABI remains
compatible:

```text
*JOIN myssid mypassword
*JOIN myssid WPA:password
*JOIN myssid WPA2:password
*JOIN myssid WEP:abcde
*JOIN myssid WEP:0011223344
*JOIN myssid OPEN
```

Automatic mode negotiates WPA or WPA2. WEP accepts 5 or 13 ASCII characters,
or 10 or 26 hexadecimal digits. WPA and WPA2 passphrases must contain 8-63
characters. Quoting and unusual whitespace still require compatibility tests;
avoid spaces and commas in initial hardware testing.

## Network and time

| Command | Behavior | Status |
| --- | --- | --- |
| `*PING <host>` | DNS lookup and five ICMP echo requests | Implemented, including Escape cancellation |
| `*WGET <url> <addr>` | Downloads HTTP data to host memory and reports the byte count, exclusive address range, and first four bytes | Implemented; advanced HTTP cases remain |
| `*WGET -T <url>` | Prints text with CR line endings | Implemented |
| `*WGET -X <url>` | Prints text using LF input | Implemented |
| `*WGET -U <url>` | Downloads a UEF image to JIM window 1 | Implemented; hardware validation pending |
| `*WGET -S <url> <slot>` | Downloads to JIM and copies to sideways RAM | Implemented; hardware validation pending |
| `*DATE` | Reads date from NTP | Implemented |
| `*TIME` | Reads time from NTP | Implemented |
| `*DISCONNECT` | Closes the current OSWORD-compatible raw socket and prints the close response | Implemented |

For example, a successful menu-sized transfer to `&0E00` reports a line in
this form:

```text
WGET OK &0B5B bytes at &0E00-&195B head &208A124C
```

The end address is exclusive. The byte count and address range prove how much
host memory changed; `head` exposes the first four downloaded bytes so an HTTP
error page cannot be confused with the expected program header. `*WGET -T`
prints the downloaded text directly. Pi1MHz also rejects non-2xx HTTP status
codes before returning payload bytes.
When a server supplies `Content-Length`, Pi1MHz completes the download after
that exact number of body bytes. A later TCP reset cannot turn an already
complete response into error `&25`, while a short response still fails.

TCP failures retain their source in current kernels: `&2A` route, `&2B`
timeout, `&2C` reset, `&2D` local abort, `&2E` unexpected close, and `&2F`
interface failure. `&30` means that an HTTP response arrived with a non-2xx
status. The older generic `&25` remains for connection errors which lwIP does
not classify more specifically.

HTTP requests identify themselves as `ElkWiFi/0.23`. The default MENU server
rejects anonymous HTTP clients with status 403, so this compatibility header
is required for both `*MENU` and direct `*WGET` requests.

WGET supports plain HTTP only. HTTPS is rejected. Redirects are rejected rather
than followed. Chunked bodies and large transfers remain hardware test cases.
Escape closes the URL handle and returns without treating cancellation as
successful EOF.

## Menu

| Command | Behavior |
| --- | --- |
| `*MENUSRC` | Prints the active menu URL |
| `*MENUSRC http://host/path` | Validates and saves a menu URL |
| `*MENUSRC DEFAULT` | Restores and saves the compiled default URL |
| `*MENU` | Downloads the active URL to host `&E00`, adapts it, then runs it on the I/O processor |

Only `http://` menu URLs are accepted. `*MENU` does not enter `&E00` after a
failed, cancelled, empty, shorter-than-16-byte, or invalid-entry download. An
accepted payload must start with a 6502 `JSR` or absolute `JMP` opcode.

`*MENU` does not queue BASIC `CALL &E00`. That command would execute parasite
memory when a Tube processor is active, although WGET populated I/O processor
memory. The ROM instead enters host `&E00` with a return trampoline in main
RAM. This also remains valid if the downloaded program changes ROMSEL.

The published ElkWiFi menu contains an inlined `&FC34` cartridge bank-select
sequence. Before entering host `&E00`, this ROM replaces that sequence with an
equal-length Pi1MHz `&FCFE` window selection. Custom menu payloads that do not
contain the stock sequence are left unchanged.

See [MENU runtime adaptation](menu-runtime-patch.md) for the exact byte
replacement, scan range, execution order, and failure policy.

## WiCFS and paged RAM

A typical WiCFS sequence is:

```text
*WGET -U http://host/program.uef
*WICFS
*CAT
```

`*WICFS` installs FILEV, FINDV, BGETV and FSCV through the MOS extended-vector
table. It does not copy code into `&0400-&07FF`, which belongs to the Tube host
code. Each successful `*WGET -U` publishes the new UEF length directly to
WiCFS. `*REWIND` restores that saved length and resets the read pointer without
performing another synchronous JIM metadata read. `*PRD` inspects paged RAM. These
commands use the Pi1MHz JIM window selector rather than the cartridge UART
bank bit.

Whole-file loads retain all four address bytes. Host destinations are written
through the normal indirect store. Parasite destinations initialise Tube
operation 1 at `&0406` and stream each byte through R3DATA at `&FEE5`.
Successful `*RUN` requests jump to host memory for `&FFFFxxxx` execution
addresses or use Tube operation 4 for parasite execution. OSFILE returns load,
execution, length and attribute fields required by BASIC `CHAIN`. Catalogue,
load, run, sequential access, malformed UEF handling and selector restoration
still require full regression on real hardware.

## Version and help

| Command | Behavior |
| --- | --- |
| `*HELP WIFI` | Lists the retained command surface |
| `*VERSION` | Prints the ElkWiFi and Pi service version response |

The current `*VERSION` output does not yet contain a unique source revision or
release build identifier.

## Removed commands

The following cartridge-specific commands are deliberately absent:

- `*PRINTER`
- `*UPDATE`
- Update `*CRC`
- `*SETSERIAL`

The Pi1MHz adapter has no ElkWiFi UART, printer channel, or cartridge flash
device. Direct calls to unsupported legacy driver functions return
`Not implemented` without touching the `&FC30-&FC3F` range.
