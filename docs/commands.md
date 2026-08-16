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
| `*ONLINE` | Reports `ONLINE <IPv4>` when associated with a DHCP address, otherwise reports a concise offline state | Implemented |
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

Automatic mode uses WPA2/AES. WPA1/TKIP remains available through the explicit
`WPA:` prefix. WEP accepts 5 or 13 ASCII characters,
or 10 or 26 hexadecimal digits. WPA and WPA2 passphrases must contain 8-63
characters. Quoting and unusual whitespace still require compatibility tests;
avoid spaces and commas in initial hardware testing.

`*ONLINE` requires a matched 0.1.6 or later Pi kernel. An older kernel does not
own service command 92 and returns `Not implemented`.

## Network and time

| Command | Behavior | Status |
| --- | --- | --- |
| `*PING <host>` | DNS lookup and five ICMP echo requests | Implemented, including Escape cancellation |
| `*WGET <url> <addr>` | Downloads HTTP data to host memory and reports the byte count, exclusive address range, and first four bytes | Implemented; advanced HTTP cases remain |
| `*WGET -T <url>` | Prints text with CR line endings | Implemented |
| `*WGET -X <url>` | Prints text using LF input | Implemented |
| `*WGET -U <url>` | Downloads a UEF image to JIM `&000000-&00FFFF` | Implemented; hardware validation pending |
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

An `&2D` from `*MENU` can be a refused or aborted connection before HTTP
headers arrive. Check the configured `*MENUSRC` endpoint from another machine
before changing the ROM or SD-card image. On 6 August 2026 the compiled default
host refused both ports 80 and 443, so that occurrence was an upstream outage.

### OSWORD `&65` application interface

The three-byte OSWORD block contains the ElkWiFi driver A, X and Y values.
Pointer-bearing functions retain the original convention: function 8 receives
the parameter address high byte in X and low byte in Y. The application-facing
functions are:

| Function | Operation |
| ---: | --- |
| 0 | Soft reset volatile TCP state and return `OK` |
| 1 | Hardware-reset compatibility alias; resets volatile TCP state and returns `OK` |
| 3 | Scan access points and return `+CWLAP:` records |
| 4 | Join an access point or query the current association |
| 5 | Leave the current association |
| 8 | Open TCP from CR-terminated protocol, host and port fields |
| 9 | Select single-connection mode; `0` is a successful no-op |
| 13 | Send the buffer described by the zero-page control block |
| 14 | Close the connection |
| 18 | Return original-compatible `+CIFSR:STAIP` and `+CIFSR:STAMAC` records |
| 20 | Receive pending connection data |
| 23 | Return the implicit single connection channel |
| 24 | Enable or disable the interface |

Function 9 rejects multiplexed mode because Pi1MHz exposes one connection.
Every driver entry selects the AP5-visible JIM page through `&FCFF`. The page
selector is write-only on AP5/Pi1MHz, so the ROM keeps a
transient ROM-heap shadow for returned length and multi-page function 13 data.
Function 18 deliberately omits Pi-only diagnostics so its complete response
fits the bounded 239-byte application mailbox; `*ONLINE` reports link
readiness. Function 9 returns `OK`, CR, LF, NUL with response length `&0004`.
Callers should reselect
the upper bytes before consuming a returned buffer because DFS, MMFS and other
expansions share the aperture.

HTTP requests identify themselves as `ElkWiFi/0.23`. The default MENU server
rejects anonymous HTTP clients with status 403, so this compatibility header
is required for both `*MENU` and direct `*WGET` requests.

WGET supports plain HTTP only. HTTPS is rejected. Redirects are rejected rather
than followed. Chunked bodies and large transfers remain hardware test cases.
Escape closes the URL handle and returns without treating cancellation as
successful EOF.

For a response with `Content-Length`, an early TCP close is a network error,
not successful EOF. This prevents a partial UEF download from being reported
as `WGET OK` and failing later inside WiCFS with `Unexpected EOF`.

## Menu

| Command | Behavior |
| --- | --- |
| `*MENUSRC` | Prints the active menu URL |
| `*MENUSRC http://host/path` | Validates and saves a menu URL |
| `*MENUSRC DEFAULT` | Restores and saves the compiled default URL |
| `*MENU` | Downloads the active URL to host `&E00`, adapts it, then runs it on the I/O processor |

The compiled default menu is an Electron program. On BBC B, B+, Master and
Compact systems, `*MENU` reports `Default MENU is Electron only` while that
source is active. Set a menu written for the target machine with
`*MENUSRC http://host/path`; custom sources remain available on every host.

Only `http://` menu URLs are accepted. `*MENU` does not enter `&E00` after a
failed, cancelled, empty, shorter-than-16-byte, or invalid-entry download. An
accepted payload must start with a 6502 `JSR` or absolute `JMP` opcode.

`*MENU` does not queue BASIC `CALL &E00`. That command would execute parasite
memory when a Tube processor is active, although WGET populated I/O processor
memory. The ROM instead enters host `&E00` with a return trampoline in main
RAM. This also remains valid if the downloaded program changes ROMSEL.

The published ElkWiFi menu contains an inlined `&FC34` cartridge bank-select
sequence. Before entering host `&E00`, this ROM replaces that sequence with an
equal-length call to a Pi1MHz JIM address helper. Custom menu payloads that do
not contain the stock sequence are left unchanged.

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
WiCFS. `*REWIND` reloads the authoritative length trailer from Pi1MHz JIM and
resets the read pointer. The length is not cached in volatile host heap.
`*PRD` inspects paged RAM. These
commands use the Pi1MHz JIM window selector rather than the cartridge UART
bank bit.

The published ElkWiFi menu's selected-title sequence remains `*REWIND`, then
`CHAIN ""`. The ROM does not rewrite that key expansion or substitute `*RUN`,
`*/`, or another game command.

Pi1MHz supplies the UEF over the 1MHz bus in every configuration. WiCFS writes
the file to Electron I/O-processor memory and never probes or accesses the
Tube. OSFILE returns the load, execution, length and attribute fields required
by callers. Catalogue,
load, run, sequential access, malformed UEF handling and selector restoration
still require full regression on real hardware.

## Version and help

| Command | Behavior |
| --- | --- |
| `*HELP WIFI` | Lists the retained command surface |
| `*VERSION` | Prints the `1MHzWifi` ROM revision, original ElkWiFi credit and Pi service response |

The current ROM reports `1MHzWifi 0.1.52 (C) 2026 Peter Clarke`, followed
by `Original elkWifi (C) 2020 Roland Leurs`. These lines are generated by the
ROM and confirm the exact host image before a hardware result is reported. The
following line identifies the matched Pi-side service and generated Pi1MHz
kernel revision. The packaged kernels report `Pi1MHz ElkWiFi 0.1.52, kernel
V1.30-84-gd08242e-dirty`. Use the SHA-256 values in `SHA256SUMS` to identify
the exact integrated binaries.

### `*UEF LOAD <filename>`

Opens a UEF image through the currently selected MOS filing system, streams it
into the AP5-visible Pi1MHz JIM window, writes the same length trailer as
`*WGET -U`, selects the tape filing system, installs WiCFS, rewinds, and
executes `CHAIN ""`. The
ROM queues setup and launch separately to stay within the Electron keyboard
buffer, but no further command is required. ADFS, DFS, MMFS, and other filing
systems work through their normal OSFIND and OSBGET implementations. The
importer reselects its JIM page after every OSBGET because the source
filing system may use the same aperture.

The Pi recognizes raw UEF data, gzip by its `1F 8B` signature, and a
single-entry ZIP by its local-file signature. ZIP entries may contain either
raw or gzip-compressed UEF data. Deflate errors, CRC mismatches, invalid UEF
headers and expanded images larger than the JIM window are rejected before
WiCFS is installed. This normalization applies both to `*UEF LOAD` and
`*WGET -U`, including MENU title downloads. A successful import reports
`UEF RAW OK`, `UEF GZIP OK`, or `UEF ZIP OK` and the expanded byte count.
The corresponding WGET forms report `WGET RAW OK`, `WGET GZIP OK`, or
`WGET ZIP OK`.

WiCFS accepts valid zero-byte CFS files. These are used as markers by some
multi-file applications. The ROM checks the cassette block's declared length
before fetching data, so a final zero-byte file such as Desk Diary's
`V1` marker completes normally instead of consuming the following UEF chunk
header and eventually reporting `Unexpected EOF`.

The maximum expanded length is `&FFFE` bytes. Escape is checked at each 256-byte
boundary, and the source file is closed on completion, cancellation, read
failure, or overflow. Import and JIM transfer remain on the I/O processor.
The OSFIND handle is stored below the private two-byte length frame. Inline
OSBGET calls recover it at stack offset three; the close subroutine accounts
for its JSR return address and recovers it at offset five. This prevents TSX
length bookkeeping from turning the stack pointer into an ADFS channel number.
The later `CHAIN ""` follows the standard MOS OSFILE destination selected by
the active host or Tube environment.

## Removed commands

The following cartridge-specific commands are deliberately absent:

- `*PRINTER`
- `*UPDATE`
- Update `*CRC`
- `*SETSERIAL`

The Pi1MHz adapter has no ElkWiFi UART, printer channel, or cartridge flash
device. Direct calls to unsupported legacy driver functions return
`Not implemented` without touching the `&FC30-&FC3F` range.
