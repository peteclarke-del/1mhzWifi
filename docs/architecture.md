# Architecture

## Compatibility boundary

The host-facing contract is based on ElkWiFi 0.23. It includes the service ROM
header, retained star commands, OSWORD `&65`, response framing, and error
conventions. `*MENUSRC` and `*ONLINE` are additive extensions. Original driver
functions 29 to 31 remain reserved, as in pinned ElkWiFi 0.23. DATE, TIME and ONLINE use
private ROM selectors 32-34, outside the original 0-31 driver table, so their
star commands do not repurpose a published ElkWiFi call.
Cartridge-specific commands are omitted where the required UART, printer port,
or flash device does not exist.

Pi1MHz V1.30 already provides the bare-metal CYW43/SDIO WiFi stack. This
project reuses that implementation and adds the missing ElkWiFi-compatible
host contract; it does not install a second network stack or emulate the
cartridge UART. The Electron Plus 5 does not forward the original `&FC30` UART
range to its 1 MHz connector. Pi1MHz already provides a command mailbox in a
Plus 5 compatible FRED range, so the ROM uses that mailbox as its private
transport.

## Services mailbox

| FRED address | Function |
| --- | --- |
| `&FCA6-&FCA8` | 24-bit address in Pi1MHz JIM RAM |
| `&FCA9` | Auto-incrementing data register |
| `&FCAA` | Command dispatch and completion status |

The ElkWiFi service owns command numbers 80-93. All commands in that range are
assigned. Command 91 controls the CYW43 radio for public driver function 24.

The ROM accesses `&FCA6-&FCAA` directly from the Electron I/O processor. It
does not use the BBC or Master FRED OSBYTE calls. Tube OSCLI and OSWORD calls
are marshalled to the I/O processor before the service ROM runs, so parasite
code does not access FRED directly.

## Request lifecycle

Pi boot firmware enters Pi1MHz through `kernel_main()`. Pi1MHz initialises the
shared Services device and WiFi runtime before registering the ElkWiFi service.
There is no Linux process, Python runtime, login script, or system service.

The FIQ handler performs bounded work. It captures the command page and status
address, marks the request busy, and returns. Filesystem and network operations
run later from the Pi1MHz main-loop poll callback. Completion writes a result
code to the mailbox only after the response data has been committed to JIM RAM.

Command 80 has a fast path when firmware is already ready. This prevents the
host's short `*WIFI ON` poll from losing a race with an unrelated cooperative
WiFi poll.

The current mailbox holds one outstanding ElkWiFi request. Escape uses command
90 to close ICMP and NTP PCBs, invalidate DNS and packet callback generations,
clear enhanced-scan state, and retire the pending request. WGET and raw TCP use
the net-service close path. Reinitialisation performs the same ElkWiFi cleanup,
reloads the profile saved by `*JOIN`, and registers the poll callback again.
Reloading on every Acorn reset is necessary when the Pi remains powered and
does not perform a matching cold boot.

## Service command map

| Command | Operation |
| ---: | --- |
| 80 | WiFi status and firmware readiness |
| 81 | CYW43 enhanced access-point scan |
| 82 | Join query, profile save, association, and leave |
| 83 | Live lwIP interface and MAC information |
| 84 | Read active menu URL |
| 85 | Validate and save menu URL |
| 86 | Restore and save the default menu URL |
| 87 | Read or save LAPOPT selection |
| 88 | DNS resolution and ICMP echo |
| 89 | DNS and NTP date/time request |
| 90 | Cancel an outstanding foreground network request |
| 91 | Enable or disable the CYW43 radio for public driver function 24 |
| 92 | Concise association and IPv4 readiness status |
| 93 | Validate and normalize raw, gzip or ZIP UEF data in JIM |

HTTP WGET uses the existing Pi1MHz net-service commands 60, 61, and 63. Raw
TCP and connected UDP compatibility use net-service commands 45-53. Private net-service command
58 copies received bytes from the service scratch page to the AP5-visible
public JIM window. It is an internal transport acceleration behind public
ElkWiFi function 13, not a new ElkWiFi function. The service scratch source is
relative to `DISC_RAM_BASE`. The destination is an unbased offset into
`JIM_ram[0..65535]`, matching the physical page-RAM mapping used by
`&FCFF`/`&FDxx`; the host still observes the original bank `00:00`, sequential
pages, response length and trailing zero.
ROMs paired with an older kernel receive `Unsupported` and fall back to the
original byte-at-a-time copy. Raw paged WGET output uses the same private copy
operation; text and host-memory output retain their required per-byte handling.
Host or parasite pointers are never passed to the Pi.

NetTools uses a separate secure-service range. Commands 94-100 provide
capability discovery, secure random data and managed SSH. Commands 101-113 are
reserved. These commands are consumed by native programs from
`host-tools/nettools.ssd`; they are not additions to the ElkWiFi OSWORD ABI.

## Public OSWORD path

MOS service reason 8 enters the retained ElkWiFi `OSWORD &65` handler. It
unpacks driver A, X and Y from the caller's three-byte block and calls the same
`wifidriver` entry used by ROM commands. Function 4 reads its query or JOIN
strings from that public pointer. Function 8 preserves the port-string offset
while copying the DNS result to scratch memory, then opens the socket with the
parsed address and port. Function 9 accepts single-connection mode as a no-op;
multiplexed mode is rejected because the Pi net service owns one raw socket.
Its response is generated locally, leaves JIM at `00:00:00`, and records the
four-byte response length without dispatching a Pi mailbox request. Function
13 uses the same RAM page shadow while gathering a response. The ROM accepts
the original five-byte zero-page control block, retries partial TCP writes,
waits synchronously for receive completion, starts at JIM page zero, advances
across page boundaries, leaves a trailing zero and updates the original
two-byte response length. Function 20 uses the same receive path. The private
Pi copy operation does not change any of these public semantics. Function 8
accepts the original TCP and UDP protocol fields. SSL is rejected rather than
downgraded to plaintext.

Automated ROM checks begin at the emitted OSWORD handler and verify its A/X/Y
unpacking sequence, function 9 routing, caller-owned JOIN parameters, TCP port
offset preservation and the AP5-visible JIM selector. Hardware acceptance still
uses an application binary through `OSWORD &65`, since star commands alone do
not exercise this boundary.

## JIM memory use

Pi1MHz itself exposes a 24-bit JIM page address through `&FCFD` (high), `&FCFE`
(middle), and `&FCFF` (low). The AP5 forwards only `&FCFF` and JIM to its 1MHz
connector, so an Electron can access one standard 64K window. The ROM keeps
responses, UEF data and sideways-RAM downloads in that window. It never relies
on `&FCFD` or `&FCFE` reaching the Pi.

After a successful `*WGET -U`, WGET updates the JIM length trailer. `*REWIND`
reloads that authoritative value and resets the WiCFS cursor. It does not keep
the length in the ROM's `&0900` heap because that workspace is volatile and can
be overwritten by the menu or BASIC before a title is selected.

The MOS keyboard input buffer occupies `&03E0-&03FF`; WiCFS never writes it.
The active stream cursor and counters use the original WiCFS cassette zero-page
ABI while parsing and are round-tripped with vector ownership on every claimed
vector operation. The state is copied through `&FCA6-&FCA9` to
`&FFEF00-&FFEF15` in the Pi1MHz services buffer. This range
sits directly below the command pages at `&FFF000` and outside the AP5-visible
UEF window. The state copier reuses the bounded network cursor routines, so
selector publication and each FCA9 auto-increment are acknowledged before the
following byte. State is reloaded for installation and invalidated during reset.
The public ElkWiFi driver page shadow is transient at `heap+&D8`. No persistent
state is kept in application memory, ADFS `&0Dxx`, Tube workspace, or the
keyboard command queue.

MOS rebuilds its standard and extended vector tables before issuing reset
service calls. Every reset therefore invalidates the saved WiCFS ownership
record without restoring its predecessor entries. Restoring those stale
entries during the service-ROM pass can overwrite ADFS, DFS, MMFS or another
ROM which has already reclaimed a vector.

`*UEF LOAD` produces the same JIM image from a file on the current MOS filing
system. It uses OSFIND and OSBGET rather than reading ADFS or DFS structures
directly. No importer state is kept in `&0900`: the OSFIND handle is kept in a
private stack frame and recovered into Y before every OSBGET. It is not kept in
X because the import loop uses TSX for its length frame. The byte count remains
in the final JIM page.
After each source byte, the ROM reselects its `&FCFF` page, so an ADFS, DFS or
MMFS read cannot redirect the destination by changing the shared selector.
Once the source file is closed, the command queues the normal tape, PAGE, NEW,
and WiCFS setup sequence. A hidden second-stage command performs the same
callable WiCFS vector installation as `*QUPCFS`, then queues only `*REWIND` and
`CHAIN ""`. This split keeps each insertion below the Electron keyboard-buffer
limit while retaining the published launch sequence.

Before entering the CFS data-copy loop, WiCFS tests the block length. A
zero-byte block skips the data read, accounts for the already-consumed header
and CRC, and returns success. This is required by applications which end a
multi-file tape with a zero-byte version or capability marker.

WiCFS is host-only. It writes downloaded UEF files directly to Electron
I/O-processor memory and never probes or accesses Tube registers. The menu
retains the stock `REWIND` and `CHAIN ""` sequence. A fitted Tube remains
enabled and available to software which chooses to use it after launch.

With a Tube active, the patched menu invokes the private `QHOST` service before
the stock cassette launch. `QHOST` enters BASIC directly on the I/O processor
and queues `PAGE=&E00` followed by the short internal `QR` command. `QR`
installs WiCFS and queues the published `*REWIND`, `CHAIN ""` pair. The PAGE
assignment is required because cold host BASIC otherwise derives a `&23xx`
workspace from the active Tube environment while the Electron program is
loaded at `&0Exx`.

WiCFS records the handler address and owning ROM behind each MOS extended
filing vector before installing its own entries. Unsupported operations are
tail-called through that recorded handler. This is required for OSCLI: the
active filing system sees `*REWIND` before the service ROM gets an opportunity
to claim the command. Sending an unclaimed request back to the MOS dispatcher
without restoring the previous entry would select WiCFS repeatedly. For a
sideways-ROM predecessor, WiCFS copies a short tail-call to host filing
workspace, selects the saved ROM there and jumps to the saved handler. The
handler returns through the existing MOS extended-vector frame. The RAM tail
is necessary because the instruction after ROM selection cannot be fetched
from the displaced 1MHzWifi ROM.

While WiCFS is active it claims its own `*REWIND` during the FSCV OSCLI pass,
before sideways-ROM command dispatch. Its original OSBYTE `&8C` trap remains
installed while a virtual tape is active. This prevents a protected
multi-stage loader's internal `*TAPE` command from disconnecting WiCFS between
files. `*MENU` is the controlled transition back to cassette state: it first
restores the BYTEV entry saved by WiCFS and then issues the normal `*TAPE`
command. Repeated MENU invocations therefore remain possible without weakening
the active virtual-tape contract.

The service command page, URL scratch data and WiCFS vector state remain inside
the Pi1MHz service allocation. WiCFS content occupies the standard JIM range
`&000000-&00FFFF`. The ROM keeps an
independent low-page shadow and never reads AP5's write-only `&FCFF` register.
Large transfers and simultaneous-service use remain hardware stress tests.

## Menu operation

`*MENUSRC` reads or writes `/Pi1MHz/ElkWiFi.menu`. The active URL follows this
precedence:

1. Valid saved `ElkWiFi.menu` value
2. Valid `elkwifi_menu_url` value from `Pi1MHz.cfg`
3. Compiled default URL

The compiled URL serves the published Electron menu. Before downloading it,
the ROM identifies the host with OSBYTE `&81`. Electron continues normally.
BBC B, B+, Master and Compact return a bounded explanation and require a
machine-appropriate custom `*MENUSRC`. This check does not restrict custom
menu sources or any WiFi, TCP, WGET, OSWORD or NetTools operation.

The ROM lists `MENUSRC` before `MENU` because the inherited command matcher
claims a command when the table spelling ends. Reversing that order causes
`*MENUSRC` to execute `*MENU`.

`*MENU` constructs `*WGET <url> E00` in ROM workspace and executes it through
OSCLI. WGET exposes an internal completed/non-empty flag. The ROM queues
execution of host `&E00` only when that flag indicates success. A failed,
cancelled, or empty transfer cannot execute stale memory at `&E00`.

The ROM copies a return trampoline to host RAM and enters host `&E00` directly.
It does not queue a BASIC `CALL`, because that would execute parasite memory
when a Tube processor is active. The RAM trampoline also permits the menu to
change ROMSEL without making its eventual return depend on the ElkWiFi ROM
remaining selected.

Host-only ROM selection is performed by RAM trampolines after the same OSBYTE
`&81` query. Electron uses its `&FE05` deselect/select sequence. BBC B, B+,
Master and Compact use `&FE30`. The distinction is confined to host BASIC
entry, WiCFS's successful `*RUN` return and `*WGET -S`; the 1MHz mailbox and
JIM protocols are machine-independent.

When a Tube language is active, the cold host BASIC default PAGE is not the
normal Electron value. The private `QHOST` transition therefore queues the
fourteen-byte `PAGE=&E00` and `*QR` sequence. `QR` is an internal alias for
the normal `QUPRUN` second stage. It installs WiCFS and retains the published
`*REWIND`, `CHAIN ""` launch. This corrects host BASIC state only; it does not
inspect a title, transfer data through the Tube or reserve a Tube channel.

The published menu is itself cartridge-specific. It selects the second paged
RAM bank through an inlined `&FC34` sequence. After download, the ROM scans
`&0E00-&1FFF` and replaces that exact eight-byte sequence with an equal-length
Pi1MHz helper call that removes the cartridge bank operation. Equal length
preserves the downloaded program's addresses and relative branches. Custom
payloads without the exact signature are unchanged. The complete contract is
documented in
[MENU runtime adaptation](menu-runtime-patch.md).

One published title contains a second-stage loader at `&0400` which copies the
Electron MOS filing vectors back into page two before issuing `*TAPE`. That
would bypass every virtual filing system, including original WiCFS. After an
execution load, 1MHzWifi compares the complete 24-byte reset loop and the
following `TAPE` command at `&04A8`. Only when both signatures match does it
replace the loop entry with `JMP &0418`, leaving the loader's remaining code
and the official `*REWIND`, `CHAIN ""` launch sequence unchanged.

## Failure policy

The ROM distinguishes transport failures where the hardware permits it:

| Host error | Meaning |
| --- | --- |
| `Device not found` | Services mailbox is absent, or the Pi reports no usable WiFi hardware |
| `Not implemented` | Services mailbox responds but the command is unregistered or unsupported |
| `No response from device` | A claimed command remained busy past its deadline |

HTTP EOF is accepted only after the declared `Content-Length` has been read.
An early close returns `&2E` so truncated MENU and UEF payloads never become a
successful WGET. UEF normalization operates on absolute JIM `&000000-&00FFFF`;
Pi1MHz's private disc-memory base is deliberately not involved.

An Acorn reset rebuilds Pi1MHz's emulator and poll registration tables but
does not reset the CYW43. The ElkWiFi service therefore reloads the saved
profile for comparison and preserves an existing association when SSID,
password and security mode are unchanged. Credential changes still use the
normal asynchronous rejoin path.

Unsupported OSWORD functions return before the inherited UART and flash
dispatcher. Secure transports also fail closed. TLS or SSH support must include
certificate or host-key verification before it can be enabled.
