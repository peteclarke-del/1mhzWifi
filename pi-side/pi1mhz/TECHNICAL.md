# Pi1MHz integration technical change record

## Scope and base

This package targets Pi1MHz commit
`4c54d8118f632465f31ecb72dcc37b4833c2507a` (V1.35), the reviewed official
`master` revision recorded in `../upstream.env`. It extends Pi1MHz's existing
bare-metal CYW43, lwIP, services, WiFi, UEF and secure code. It does not
install a Linux daemon.

The sections below that describe the WiFi service adapter and the UEF tape
describe upstream's code as this package configures and patches it, not code
this package supplies. V1.35 merged both.

`overlay/src` contains complete added modules. `patches` contains ordered
changes to upstream-owned files. `../upstream/1mhzwifi-pi1mhz.patch` is a
generated, binary-capable review patch and must be regenerated from these
canonical inputs rather than edited directly.

## WiFi service adapter (upstream src/wifi_service.c)

The adapter owns service commands 80 through 93, and is Pi1MHz's as of V1.35,
where it is `src/wifi_service.c` with the UEF half split into
`src/uef_service.c`. It is described here because the host ROM's ABI is this
project's and has to keep matching it; the numbers and command-block layouts
below are the ROM's and did not move when the file was renamed. It is off
unless `wifi_service_enable=1`. Command 91 starts radio setup
for public driver function 24 and acknowledges the accepted request without
waiting for firmware startup or association. The FIQ handler captures the
command pointer, publishes busy and handles the fixed status response when
firmware is already ready.
Filesystem, SDIO, scan, DNS, ICMP, NTP and UEF work runs from the cooperative
poll loop.

The UEF stream window is published flat, a whole JIM page at a time, starting
at page 1. Page 0 is reserved for the service reply buffer, which OSWORD `&65`
clients read in full and which used to corrupt the stream when a reply landed
during a load; the last page carries the length trailer. That leaves 254 pages,
so the window is `&FE00` bytes rather than the `&FF00` it was when the stream
started at page 0.

Command 86 published a host filing-vector trampoline into every JIM page. It
has been removed from the kernel along with the scattered window it required:
the host-side trampoline was withdrawn because pointing the filing vectors at
it broke the `*/` multi-file handover, so nothing sent the command. The patch
is kept under `rom-side/candidates` with the analysis in
`docs/hardware-validation.md`, and reviving it means restoring the kernel side
as well as reworking the `*RUN` transfer to be frame-agnostic.

The stub exists because the host has nowhere safe in RAM to keep its filing
vectors. WiCFS's gateway below `&0800` and the MOS extended vector table at
`&0D9F` are both inside the region cassette loaders reuse, which is why a fifth
of the corpus could not be loaded. JIM is served by the Pi, so a loader cannot
reach it. Each stub pages the host's ROM in, calls the handler and pages the
caller's ROM back, reproducing the MOS dispatcher's stack frame exactly, the
displaced ROM number sits four bytes into the stack, because filing calls
nest and a single saved copy would be overwritten by the inner call.

Only one ElkWiFi request can be pending. A second request receives busy without
replacing the active command pointer. Every asynchronous operation has a
deadline or a lower-layer bounded state machine. Cancel invalidates callback
generations, removes protocol control blocks and drops scan state.

Responses are limited to 240 bytes because the inherited host driver exposes a
single bounded response page. IFCFG deliberately returns original-style
station IP and station MAC records. Pi-specific progress is reported by
`*ONLINE`.

Command 93 retains its legacy raw, gzip and ZIP normalization response. An
exact `IUEF`, version-1 request adds begin, append, finalize, rewind, refill and
close operations without allocating another command number. Source windows are
at most `&FF00` bytes in public JIM; normalized streams are retained in two
16 MiB Pi-private buffers and republished on demand. The response includes a
session token, 32-bit generation, window length and final flag. The ROM carries
the low 16 generation bits, which covers every window in the 16 MiB limit, so
a timed-out refill can be retried without advancing twice. Normalization and
window publication execute in the cooperative poll loop, never in FIQ.

## WiFi startup and association

Pi1MHz preloads the firmware candidates, detects the CYW43 family and SOCRAM
revision, boots SDIO cooperatively, reads the active chip MAC, initializes lwIP
and starts DHCP or the configured static network. Pi Zero W uses CYW43430,
Zero 2 W uses the ARMv8 image and supported Pi 3 models select the 43430,
43436 or 43455 assets at runtime. Plain Pi Zero has no onboard radio and
reports device absent through the host command.

The BCM43455 binary is pinned to firmware 7.45.241 from Pi1MHz revision
`8468a38`. Firmware 7.45.265 associated on the Pi 3A+ validation unit but did
not pass DHCP traffic. This pin is an evidence-based compatibility measure and
still requires a fresh physical DHCP pass.

The WiFi profile validator is the single authority for configuration-file and
`*JOIN` credentials. It accepts open networks with an empty key, WEP 5/13-byte
ASCII or 10/26-digit hexadecimal keys, and WPA/WPA2 passphrases of 8 to 63
bytes. AUTO means open with an empty key and WPA2-PSK otherwise. Invalid input
is rejected before `ElkWiFi.wifi` is overwritten. Joining after `*WIFI OFF`
first sends WLC_UP, then starts association.

JOIN persists the profile before scheduling association and returns promptly.
Association, WPA keying and DHCP continue from the poll loop. `*JOIN ?`,
`*ONLINE` and `*IFCFG` expose progress without holding the shared command page.
Unchanged credentials do not force an already-live link through another slow
association after an Acorn reset.

`*LEAVE` disassociates, releases DHCP and pauses automatic rejoin. `*WIFI OFF`
sends WLC_DOWN while retaining firmware and the service mailbox. `*WIFI ON`
sends WLC_UP and rejoins when a profile is present. The recovery loop retries
lost associations with backoff and can restart the chip after repeated dead
transmit state.

## Network and secure services

The existing Pi1MHz raw network service is corrected for HTTP status,
Content-Length truncation, diagnostic errors and an ElkWiFi-compatible user
agent. The ElkWiFi ROM uses it for WGET and OSWORD TCP operations.

Raw command 58 is a Pi1MHz-private receive accelerator. It copies at most 240
bytes from the fixed raw-network scratch page to a validated offset in the
standard 64K public JIM window. The scratch source is relative to
`DISC_RAM_BASE`, while the host-visible `&FCFF`/`&FDxx` window maps to
`JIM_ram[0..65535]` and therefore takes an unbased destination. The ROM uses
it only after raw receive command 51 succeeds,
then maintains the public ElkWiFi page cursor, length and terminator exactly as
before. Applications continue to call OSWORD `&65` function 13 and cannot see
or invoke a new ElkWiFi function number. The ROM falls back to the original
copy loop when an older kernel reports command 58 as unsupported. Raw paged
WGET destinations use the same operation, while transformed text and
host-memory destinations remain on the byte path.

Commands 94 through 100 implement the managed NetTools secure ABI. Host calls
are synchronous, and the FIQ wrapper always latches the newest command so a
request arriving around reset cannot be stranded behind a stale BUSY result.
The poller preserves a latched request across provider reset. wolfSSH owns
private keys, session keys, host-key verification and
known-host persistence on the Pi. Password bytes are wiped after handoff.
Known-host updates use a synchronized temporary file, backup rename and
rollback.

The BCM hardware RNG discards its first `0x40000` oscillator bits. Provider
initialisation waits against the SoC microsecond timer for up to 750 ms. The
previous fixed iteration count expired at different wall-clock times on Pi
Zero and Pi 3 and could leave the managed SSH feature disabled until reboot.

The Services dispatcher first publishes the standard selector echo, completing
the physical host write transaction, then routes the fixed raw-network,
ElkWiFi and secure command ranges directly. Each fixed handler replaces that
echo with `BUSY` or its final result. Dynamic and unknown commands retain the
upstream selector-echo behaviour. Host clients treat every bit-7-set value as
busy until their bounded deadline.
Secure capability discovery is a fixed synchronous reply. Its result does not
depend on the poll table, but its feature and readiness bytes report the
current wolfSSH provider state. Host NetTools mask IRQ while
selecting and using the shared FCA6-FCA9 JIM cursor, preventing MMFS, ADFS or
another interrupt-side JIM client from redirecting a request mid-block.
ElkWiFi reset cleanup masks Pi IRQ and FIQ while it publishes a terminal result
and clears the request latch, so a new FIQ request cannot be discarded with
`FCAA` left at `BUSY`.

## Persistence and configuration

The adapter stores:

- `/Pi1MHz/ElkWiFi.wifi`: versioned security mode, SSID and key.
- `/Pi1MHz/ElkWiFi.menu`: validated HTTP menu URL.
- `/Pi1MHz/ElkWiFi.lapopt`: scan field selection.

Saved WiFi and menu values take precedence over initial `Pi1MHz.cfg` values.
The installer preserves active configuration entries, requires
`Rampage_addr=0xFD`, enables the services and raw network ranges, and activates
the three BeebSCSI settings only when they are absent.

The shared services dispatcher owns its WiFi, raw network, secure and FTP
command ranges whenever `Services_addr` is enabled. Per-range legacy settings
such as `WiFiSvc_addr=-1`, `net_addr=-1`, and `secure_addr=-1` are ignored.
Only `Services_addr=-1` removes the complete mailbox callbacks. Child pollers
can remain registered but are not host-visible without the parent mailbox.

The WiFi service is opt-in as of Pi1MHz 7077688 and tests `wifi_service_enable`
before it claims commands 80 to 93. Where a service tests its config key is an
ABI decision: before the claim it disappears, and the dispatcher echoes the
command byte back, which the ROM reads as "no such service"; after the claim it
would instead answer with its own error. The ROM depends on the first, so the
installer writes `wifi_service_enable=1` into a generated bundle.

Profile, menu and LAPOPT replacement is not power-failure atomic. This remains
recorded product work. Passwords are plaintext on the FAT partition.

## UEF normalization

Commands 86 and 93 are Pi1MHz's, in `src/uef_service.c` and `src/uef_stream.c`,
as of V1.35. They accept raw UEF, gzip, single-entry ZIP and gzip inside a
single-entry ZIP, and validate headers, CRC and advertised size. The one-shot
path is still bounded by the 65,534-byte aperture; the incremental path is not,
because it no longer holds the decompressed tape at all. It keeps DEFLATE's
32 KB history and pulls compressed bytes on demand, so a 5 MB UEF costs the
same 34 KB as a 20 KB one. The two static 16 MB buffers this package used to
carry are gone with it.

The `elkwifi_uef_trim_tail` diagnostic is gone with them. It shortened the
published length to the end of the last `&0100` chunk, reproducing an earlier
1MHzWifi candidate for comparison; the original WiCFS consumes the complete
image, including terminal carrier and integer-gap chunks, and that is what both
paths now do. The emulator keeps its own copy behind `PI1MHZ_UEF_TRIM_TAIL`.

### FILEV stamp repair

`uef-filev-repair.patch` is what this package still adds here. A large minority
of Electron titles load with `?&212=&D6:?&213=&F1`, which stamps the MOS 1.00
cassette entry over whatever filing system owns FILEV, WiCFS included. The
repair redirects the address token to `&900/&901`, which leaves the program the
same length so block layout and every stored offset are untouched, and only the
affected block's payload CRC is recomputed. `wifi_service_uef_filev_repair=0`
switches it off.

Because the tape is now streamed, the repair sees it a 63 KB window at a time
and a cassette block can straddle a boundary. It rewrites the payload and then
the payload CRC that follows it, so a block split across two windows cannot be
repaired from either half: the service holds the tail of an incomplete chunk
back and re-offers it at the head of the next window. A `&0100` chunk longer
than the 1 KB carry is not a cassette block, so framing steps over it rather
than carrying it, and resumes at the chunk after. `src/tests/uef/test_uef_filev.c`,
which the patch adds to upstream's UEF suite, drives the whole protocol with
the block placed at, before and after a window boundary.

## Validation status

The package builds both `kernel.img` and `kernel7.img`. The automated gate is
`make test-pi-integration`, which applies this integration to the pinned Pi1MHz
and runs the host suites in that tree (services, net, uef, secure, config),
plus the repository contract suite. Running upstream's suites against the
patched tree matters more than it did: upstream owns the WiFi, UEF, secure and
net services now, and a patch that still applies can still be wrong. Physical association, DHCP, reconnect, every supported Pi
model and long-running SSH sessions remain hardware gates and must not be
reported as passed from source inspection alone.
