# Pi1MHz integration technical change record

## Scope and base

This package targets Pi1MHz commit
`516a267493d9f19e6bf2f4a2ea4c3e7472b12135`, the reviewed official `master`
revision recorded in `../upstream.env`. It extends Pi1MHz's existing bare-metal
CYW43, lwIP, services and network code. It does not install a Linux daemon.

`overlay/src` contains complete added modules. `patches` contains ordered
changes to upstream-owned files. `../upstream/1mhzwifi-pi1mhz.patch` is a
generated, binary-capable review patch and must be regenerated from these
canonical inputs rather than edited directly.

## ElkWiFi service adapter

The adapter owns service commands 80 through 93. Command 91 remains reserved
inside that range and returns unsupported. The FIQ handler captures the command pointer, publishes
busy and handles the fixed status response when firmware is already ready.
Filesystem, SDIO, scan, DNS, ICMP, NTP and UEF work runs from the cooperative
poll loop.

Only one ElkWiFi request can be pending. A second request receives busy without
replacing the active command pointer. Every asynchronous operation has a
deadline or a lower-layer bounded state machine. Cancel invalidates callback
generations, removes protocol control blocks and drops scan state.

Responses are limited to 240 bytes because the inherited host driver exposes a
single bounded response page. IFCFG deliberately returns original-style
station IP and station MAC records. Pi-specific progress is reported by
`*ONLINE`.

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

Commands 94 through 100 implement the managed NetTools secure ABI. Host calls
are synchronous, and the FIQ wrapper always latches the newest command so a
request arriving around reset cannot be stranded behind a stale BUSY result.
The poller preserves a latched request across provider reset. wolfSSH owns
private keys, session keys, host-key verification and
known-host persistence on the Pi. Password bytes are wiped after handoff.
Known-host updates use a synchronized temporary file, backup rename and
rollback.

## Persistence and configuration

The adapter stores:

- `/Pi1MHz/ElkWiFi.wifi`: versioned security mode, SSID and key.
- `/Pi1MHz/ElkWiFi.menu`: validated HTTP menu URL.
- `/Pi1MHz/ElkWiFi.lapopt`: scan field selection.

Saved WiFi and menu values take precedence over initial `Pi1MHz.cfg` values.
The installer preserves active configuration entries, requires
`Rampage_addr=0xFD`, enables the services and raw network ranges, and activates
the three BeebSCSI settings only when they are absent.

The shared services dispatcher owns its ElkWiFi, raw network and secure
command ranges whenever `Services_addr` is enabled. Per-range legacy settings
such as `ElkWiFi_addr=-1`, `net_addr=-1`, and `secure_addr=-1` are ignored.
Only `Services_addr=-1` removes the complete mailbox callbacks. Child pollers
can remain registered but are not host-visible without the parent mailbox.

Profile, menu and LAPOPT replacement is not power-failure atomic. This remains
recorded product work. Passwords are plaintext on the FAT partition.

## UEF normalization

Command 93 accepts raw UEF, gzip, single-entry ZIP and gzip inside a
single-entry ZIP. It validates headers, CRC, advertised size and the 65,534-byte
expanded limit. Decompression runs outside FIQ and uses a caller-provided
scratch buffer so source and destination cannot alias incorrectly.

## Validation status

The package builds both `kernel.img` and `kernel7.img`. Upstream service, net
and parser tests, host service-core tests and the repository contract suite are
the automated gate. Physical association, DHCP, reconnect, every supported Pi
model and long-running SSH sessions remain hardware gates and must not be
reported as passed from source inspection alone.
