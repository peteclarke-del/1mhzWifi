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
| `*NSLOOK <host>` | Resolves a hostname and prints its IPv4 address | Implemented |
| `*WGET <url> <filename>` | Streams HTTP data into a file on the active MOS filing system | Implemented for ADFS, DFS and MMFS-compatible filing systems |
| `*WGET -T <url>` | Prints text with CR line endings | Implemented |
| `*WGET -X <url>` | Prints text using LF input | Implemented |
| `*WGET -U <url>` | Downloads a UEF image to JIM `&000000-&00FFFF` | Implemented; hardware validation pending |
| `*WGET -S <url> <slot>` | Downloads to JIM and copies to sideways RAM | Implemented; hardware validation pending |
| `*FTP <host>` | Opens an interactive plain FTP session | Implemented; hardware validation pending |
| `*DATE` | Reads date from NTP | Implemented |
| `*TIME` | Reads time from NTP | Implemented |
| `*DISCONNECT` | Closes the current OSWORD-compatible raw socket and prints the close response | Implemented |

For example:

```text
*WGET http://example.test/archive.uef ARCHIVE
WGET OK &000B5B bytes saved
```

The filename is interpreted by the active filing system, so directory and drive
syntax follow ADFS, DFS or MMFS rules. The ordinary command no longer writes an
unlabelled block into host or JIM memory. `*WGET -T` prints downloaded text
directly. `*WGET -U` remains an explicit JIM destination because WiCFS consumes
that buffer, while `*WGET -S` remains the explicit sideways-RAM form. Pi1MHz
rejects non-2xx HTTP status codes before returning payload bytes.
When a server supplies `Content-Length`, Pi1MHz completes the download after
that exact number of body bytes. A later TCP reset cannot turn an already
complete response into error `&25`, while a short response still fails.

TCP failures retain their source in current kernels: `&2A` route, `&2B`
timeout, `&2C` reset, `&2D` local abort, `&2E` unexpected close, and `&2F`
interface failure. `&30` means that an HTTP response arrived with a non-2xx
status. The older generic `&25` remains for connection errors which lwIP does
not classify more specifically.

### Interactive FTP

`*FTP <host>` and `*FTP ftp://host[:port]` open a standard, unencrypted FTP
control session. The prompt accepts `USER`, `PASS`, `PWD`, `CD`, `DIR`, `LS`,
`GET`, `PUT`, `DELETE`, `MKDIR`, `RMDIR`, `ASCII`, `BINARY`, and `QUIT`.
Server commands not named in that list are passed through unchanged.

`GET remote [local]` writes through MOS OSFIND and OSBPUT. `PUT local
[remote]` reads through OSFIND and OSBGET. Local names are therefore resolved
by the filing system which was active when FTP was entered. Passive data
connections use EPSV first and PASV as a compatibility fallback. The Pi uses
the control peer address for PASV, not an untrusted address embedded in the
server reply.

FTP sends credentials and data without encryption. Use the NetTools `SFTP`
application when the server supports SSH file transfer. Passwords entered as
`PASS` are visible on the Acorn display, so plain FTP should be restricted to
trusted networks and non-sensitive accounts.

### Interactive SFTP

NetTools supplies `*SFTP user@host [port]`. It uses the Pi-side wolfSSH client
and enters an interactive prompt without changing a usable display mode. The
commands are `PWD`, `CD`, `DIR`, `LS`, `GET`, `PUT`, `DELETE`, `MKDIR`,
`RMDIR`, and `QUIT`.

`GET remote [local]` and `PUT local [remote]` use the active MOS filing
system. Remote paths are case-sensitive. The first connection to an unknown
host displays its fingerprint and asks whether the key should be trusted and
stored on the Pi SD card. Password input is hidden and the host and JIM copies
are wiped after authentication. SFTP command responses and directory listings
are currently limited to 240 bytes. File contents are transferred in repeated
chunks and are not subject to that listing limit.

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
| 8 | Open TCP or connected UDP from CR-terminated protocol, host and port fields; unsupported SSL returns `ERROR` |
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

The complete pinned ElkWiFi 0.23 driver table is retained as follows:

| Function | 1MHzWifi behavior |
| ---: | --- |
| 0, 1 | Reset volatile connection state and return `OK` |
| 2 | Return firmware and driver identification |
| 3 | Scan access points |
| 4 | Query or join the current access point |
| 5 | Leave the current access point |
| 6, 18 | Return station IP and MAC configuration |
| 7 | Query station mode or accept mode 1 |
| 8 | Open TCP or connected UDP; reject unsupported SSL |
| 9 | Query or select single-connection mode 0 |
| 10, 12 | Return original-style connection status |
| 11 | Finalise the public response length from X and the current page |
| 13 | Send the caller's 24-bit-length buffer and collect the response |
| 14 | Close the active connection |
| 15, 16, 17 | Return the stable original CIOBAUD query response |
| 19 | Return `Not implemented`, as in ElkWiFi 0.23 |
| 20 | Receive pending connection data |
| 21, 22 | Bounded successful watchdog compatibility calls; the Pi owns its watchdog |
| 23 | Return the implicit single connection channel |
| 24 | Enable or disable WiFi |
| 25 | Set access-point scan display options |
| 26 | Bounded successful SSL-buffer compatibility call; the Pi sizes its own buffers |
| 27 | Query or select normal transfer mode 0; reject transparent mode 1 |
| 28 | Ping |
| 29, 30, 31 | Reserved and `Not implemented`, as in pinned ElkWiFi 0.23 |

Function numbers are masked to five bits as they are by the original driver.
The DATE, TIME and ONLINE star commands use private ROM entries and do not
replace functions 29 to 31.

HTTP requests identify themselves as `ElkWiFi/0.23` for compatibility with
servers which inspect the original cartridge's user-agent header.

WGET supports plain HTTP only. HTTPS is rejected. Redirects are rejected rather
than followed. Chunked bodies and large transfers remain hardware test cases.
Escape closes the URL handle and returns without treating cancellation as
successful EOF.

For a response with `Content-Length`, an early TCP close is a network error,
not successful EOF. This prevents a partial UEF download from being reported
as `WGET OK` and failing later inside WiCFS with `Unexpected EOF`.

See [MENU retirement](menu-retirement.md) for the removed command surface and
the generic facilities which remain.

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
`*PRD [address] [bank]` inspects paged RAM without reading the write-only JIM
selectors. On a direct BBC-family connection, bank 0 or 1 selects the matching
64 KiB Pi1MHz window. Electron AP5 exposes only bank 0, so requesting bank 1
returns `Unknown option` instead of silently displaying the wrong data. PRD
reasserts the complete address before each byte and restores bank `00:00` when
it finishes.

The private `*QAUTO` entry validates the first file as tokenised BASIC,
including the CR at the line's declared boundary, before choosing `CHAIN ""`;
otherwise it chooses `*RUN ""`. The stream is rewound after classification.
This is a generic format decision, not a catalogue or title-specific
exception. The retired `*MENU` command is not required by this path.

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

The current ROM reports `1MHzWifi 0.1.66 (C) 2026 Peter Clarke`, followed
by `Original elkWifi (C) 2020 Roland Leurs`. These lines are generated by the
ROM and confirm the exact host image before a hardware result is reported. The
following line identifies the matched Pi-side service and generated Pi1MHz
kernel revision. The packaged kernels report `Pi1MHz ElkWiFi 0.1.66, kernel
<revision>`. Use the SHA-256 values in `SHA256SUMS` to
identify the exact integrated binaries.

### `*UEF LOAD <filename>`

Opens a UEF image through the currently selected MOS filing system, streams it
through the AP5-visible Pi1MHz JIM window, selects the tape filing system,
installs WiCFS, and classifies the first cassette file. Structurally valid
tokenised BASIC is executed with `CHAIN ""`; machine-code loaders use
`*RUN ""`. The ROM rewinds after classification and queues setup and launch
separately to stay within the Electron keyboard
buffer, but no further command is required. ADFS, DFS, MMFS, and other filing
systems work through their normal OSFIND and OSBGET implementations. The
importer reselects its JIM page after every OSBGET because the source
filing system may use the same aperture.

The Pi recognizes raw UEF data, gzip by its `1F 8B` signature, and a
single-entry ZIP by its local-file signature. ZIP entries may contain either
raw or gzip-compressed UEF data. Deflate errors, CRC mismatches, invalid UEF
headers and expanded images larger than the 16 MiB private-stream limit are
rejected before WiCFS is installed. This normalization applies both to `*UEF LOAD` and
`*WGET -U`. A successful import reports
`UEF RAW OK`, `UEF GZIP OK`, or `UEF ZIP OK` and the expanded byte count.
The corresponding WGET forms report `WGET RAW OK`, `WGET GZIP OK`, or
`WGET ZIP OK`.

WiCFS accepts valid zero-byte CFS files. These are used as markers by some
multi-file applications. The ROM checks the cassette block's declared length
before fetching data, so a final zero-byte file such as Desk Diary's
`V1` marker completes normally instead of consuming the following UEF chunk
header and eventually reporting `Unexpected EOF`.

Matched ROM and kernel builds negotiate stream ABI 1. The ROM uploads
`&FF00`-byte source windows, the Pi retains and normalizes up to 16 MiB, and
WiCFS requests subsequent public windows without resetting its parser. Each
request carries the previous window generation, so a retried request
republishes the same bytes rather than advancing twice. Older kernels use the
unchanged legacy path with a maximum expanded length of `&FFFE` bytes. Escape
is checked at each 256-byte boundary, and the source file and partial Pi
session are closed on cancellation, read failure, or overflow.
The OSFIND handle is stored below the private two-byte length frame. Inline
OSBGET calls recover it at stack offset three; the close subroutine accounts
for its JSR return address and recovers it at offset five. This prevents TSX
length bookkeeping from turning the stack pointer into an ADFS channel number.
The later `CHAIN ""` executes from host memory through the I/O processor's MOS
OSFILE path. 1MHzWifi does not select, address or transfer the file to a Tube
parasite. A fitted Tube remains available to software which explicitly uses it.

WiCFS checkpoints the UEF cursor, page, stream-start flag and remaining length
after file operations and immediately before a loaded program executes. The
record is checksummed and committed through the Pi1MHz services byte port. It
is not rewritten for every OSBGET byte. A multi-stage loader can therefore
reuse volatile cassette workspace without restarting or losing its next-file
position, while retaining the established transfer timing.

## Removed commands

The following cartridge-specific commands are deliberately absent:

- `*PRINTER`
- `*UPDATE`
- Update `*CRC`
- `*SETSERIAL`

The Pi1MHz adapter has no ElkWiFi UART, printer channel, or cartridge flash
device. Direct calls to unsupported legacy driver functions return
`Not implemented` without touching the `&FC30-&FC3F` range.
