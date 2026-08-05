# Architecture

## Compatibility boundary

The host-facing contract is based on ElkWiFi 0.23. It includes the service ROM
header, retained star commands, OSWORD `&65`, response framing, and error
conventions. `*MENUSRC` is an additive extension. Cartridge-specific commands
are omitted where the required UART, printer port, or flash device does not
exist.

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

The ElkWiFi service owns command numbers 80-91. Commands 80-90 are assigned.
Command 91 returns unsupported and is reserved in the source ABI for a future
secure-open operation.

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
the net-service close path. Reinitialisation performs the same ElkWiFi cleanup
before registering the poll callback again.

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

HTTP WGET uses the existing Pi1MHz net-service commands 60, 61, and 63. Raw
TCP compatibility uses net-service commands 45-53. Host buffers are copied
through reserved JIM scratch pages instead of passing host or parasite pointers
to the Pi.

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

## Failure policy

The ROM distinguishes transport failures where the hardware permits it:

| Host error | Meaning |
| --- | --- |
| `Device not found` | Services mailbox is absent, or the Pi reports no usable WiFi hardware |
| `Not implemented` | Services mailbox responds but the command is unregistered or unsupported |
| `No response from device` | A claimed command remained busy past its deadline |

Unsupported OSWORD functions return before the inherited UART and flash
dispatcher. Secure transports also fail closed. TLS or SSH support must include
certificate or host-key verification before it can be enabled.
