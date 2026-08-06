# Architecture

## Compatibility boundary

The host-facing contract is based on ElkWiFi 0.23. It includes the service ROM
header, retained star commands, OSWORD `&65`, response framing, and error
conventions. `*MENUSRC` and `*ONLINE` are additive extensions.
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

The ElkWiFi service owns command numbers 80-93. Commands 80-90 and 92-93 are
assigned. Command 91 returns unsupported and is reserved in the source ABI for
a future secure-open operation.

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
| 91 | Reserved secure-open ABI; returns unsupported |
| 92 | Concise association and IPv4 readiness status |
| 93 | Validate and normalize raw, gzip or ZIP UEF data in JIM |

HTTP WGET uses the existing Pi1MHz net-service commands 60, 61, and 63. Raw
TCP compatibility uses net-service commands 45-53. Host buffers are copied
through reserved JIM scratch pages instead of passing host or parasite pointers
to the Pi.

## Public OSWORD path

MOS service reason 8 enters the retained ElkWiFi `OSWORD &65` handler. It
unpacks driver A, X and Y from the caller's three-byte block and calls the same
`wifidriver` entry used by ROM commands. Function 4 reads its query or JOIN
strings from that public pointer. Function 8 preserves the port-string offset
while copying the DNS result to scratch memory, then opens the socket with the
parsed address and port. Function 9 accepts single-connection mode as a no-op;
multiplexed mode is rejected because the Pi net service owns one raw socket.

Automated ROM checks begin at the emitted OSWORD handler and verify its A/X/Y
unpacking sequence, function 9 routing, caller-owned JOIN parameters, TCP port
offset preservation and all three JIM selectors. Hardware acceptance still
uses an application binary through `OSWORD &65`, since star commands alone do
not exercise this boundary.

## JIM memory use

Pi1MHz exposes a 24-bit JIM page address through `&FCFD` (high), `&FCFE`
(middle), and `&FCFF` (low). This ROM reserves addresses `00:00:page` for
command responses and `00:01:page` for UEF and sideways-RAM downloads. Every
entry point establishes the high byte explicitly, so ADFS, MMFS, DFS helpers,
or another application ROM cannot redirect WiCFS into another JIM region.

After a successful `*WGET -U`, WGET updates the JIM length trailer. `*REWIND`
reloads that authoritative value and resets the WiCFS cursor. It does not keep
the length in the ROM's `&0900` heap because that workspace is volatile and can
be overwritten by the menu or BASIC before a title is selected.

The cursor itself uses the original CFS zero-page allocation at `&C7/&C8`.
Loaded tape programs routinely use page `&09` between OSFILE, OSFIND and FSCV
calls, so only transient vector state is stored in the ROM heap there.

`*UEF LOAD` produces the same JIM image from a file on the current MOS filing
system. It uses OSFIND and OSBGET rather than reading ADFS or DFS structures
directly. No importer state is kept in `&0900`: the open handle remains in the
OSBGET-preserved X register and the byte count remains in the final JIM page.
After each source byte, the ROM reselects JIM address `00:01:page`, so an ADFS
or MMFS read cannot redirect the destination by changing the shared selector.
Once the source file is closed, the command queues the normal tape, PAGE, NEW,
and WiCFS setup sequence. A hidden second-stage command performs the same
callable WiCFS vector installation as `*QUPCFS`, then queues only `*REWIND` and
`CHAIN ""`. This split keeps each insertion below the Electron keyboard-buffer
limit while retaining the published launch sequence.

Before entering the CFS data-copy loop, WiCFS tests the block length. A
zero-byte block skips the data read, accounts for the already-consumed header
and CRC, and returns success. This is required by applications which end a
multi-file tape with a zero-byte version or capability marker.

WiCFS records the handler address and owning ROM behind each MOS extended
filing vector before installing its own entries. Unsupported operations are
tail-called through that recorded handler. This is required for OSCLI: the
active filing system sees `*REWIND` before the service ROM gets an opportunity
to claim the command. Sending an unclaimed request back to the MOS dispatcher
without restoring the previous entry would select WiCFS repeatedly. Sideways
ROM hand-off uses a temporary trampoline in filing-system workspace so the CPU
does not fetch an instruction from a different ROM immediately after ROMSEL is
changed.

While WiCFS is active it claims its own `*REWIND` during the FSCV OSCLI pass,
before sideways-ROM command dispatch. Its original OSBYTE `&8C` trap remains
installed while a virtual tape is active. This prevents a protected
multi-stage loader's internal `*TAPE` command from disconnecting WiCFS between
files. `*MENU` is the controlled transition back to cassette state: it first
restores the BYTEV entry saved by WiCFS and then issues the normal `*TAPE`
command. Repeated MENU invocations therefore remain possible without weakening
the active virtual-tape contract.

The service command page is at JIM offset `&FFF000`; URL scratch data is at
`&FFF100`. WiCFS content occupies `&010000-&01FFFF`. The ROM keeps an
independent low-page shadow and never reads AP5's write-only `&FCFF` register.
Large transfers and simultaneous-service use remain hardware stress tests.

## Menu operation

`*MENUSRC` reads or writes `/Pi1MHz/ElkWiFi.menu`. The active URL follows this
precedence:

1. Valid saved `ElkWiFi.menu` value
2. Valid `elkwifi_menu_url` value from `Pi1MHz.cfg`
3. Compiled default URL

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

The published menu is itself cartridge-specific. It selects the second paged
RAM bank through an inlined `&FC34` sequence. After download, the ROM scans
`&0E00-&1FFF` and replaces that exact eight-byte sequence with an equal-length
Pi1MHz helper call that selects JIM address `00:01:page`. Equal length preserves
the downloaded program's addresses and relative branches. Custom payloads
without the exact signature are unchanged. The complete contract is documented in
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
successful WGET. UEF normalization operates on absolute JIM `&010000-&01FFFF`;
Pi1MHz's private disc-memory base is deliberately not involved.

An Acorn reset rebuilds Pi1MHz's emulator and poll registration tables but
does not reset the CYW43. The ElkWiFi service therefore reloads the saved
profile for comparison and preserves an existing association when SSID,
password and security mode are unchanged. Credential changes still use the
normal asynchronous rejoin path.

Unsupported OSWORD functions return before the inherited UART and flash
dispatcher. Secure transports also fail closed. TLS or SSH support must include
certificate or host-key verification before it can be enabled.
