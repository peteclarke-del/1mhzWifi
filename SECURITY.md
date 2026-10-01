# Security policy

This project handles WiFi credentials and network traffic on an 8-bit host and
a bare-metal Raspberry Pi. It is not suitable for untrusted networks in its
current form.

## Supported versions

| Version | Security support |
| --- | --- |
| Current `main` hardware-test candidate | Supported |
| Current published hardware-test bundle | Supported until replaced |
| Earlier test builds | Not supported |

Security fixes are developed on `main`. A report against an older build must
be reproduced against the current candidate before a backport is considered.

## Known limits

- Saved WiFi profiles and `Pi1MHz.cfg` passwords are plaintext on the FAT partition.
- HTTP and raw TCP are plaintext.
- The ElkWiFi-compatible WGET and raw TCP paths do not provide TLS or HTTPS.
- SSH is available only through the separate native `SSH` host tool and the
  managed Pi secure service. It is not an ElkWiFi OSWORD extension.
- WEP and WPA1 are available only for compatibility with legacy access points.
- The Acorn host does not provide process or memory isolation.

Secure transport requests fail closed. A change that silently retries a secure
request over plaintext is a security defect.

## Code scanning findings that are accepted rather than fixed

Two CodeQL alerts stand against `emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c`,
`cpp/cleartext-storage-file` and `cpp/cleartext-transmission`. Both are
accurate. They describe the `ELKWIFI1` profile, which holds a network password
in cleartext.

That format is not this project's to change. Pi1MHz reads and writes it on the
SD card, it is what `ElkWiFi.wifi` has always contained, and cards in use
already carry it. The emulator keeps the same format deliberately: a fixture
that encrypted what the machine stores in the clear would stop describing the
machine, and the acceptance runs that compare the two would agree while both
were wrong.

The exposure is reduced where it can be. The emulator creates the profile
0600, so it is owner-only on a host filesystem, which FAT cannot express. The
alerts stay open rather than being dismissed, because the underlying weakness
is real and closing it needs the on-disc format to change upstream first.

## Reporting

Do not open a public issue containing a real SSID, password, packet capture,
private key, or SD-card image. Use
[GitHub private vulnerability reporting](https://github.com/peteclarke-del/1mhzWifi/security/advisories/new).
If that facility is unavailable, contact the maintainer privately through the
details on the `peteclarke-del` GitHub profile before publishing details.

Include affected ROM and kernel hashes, hardware models, the shortest command
sequence that reproduces the issue, and sanitised logs.

The maintainer will acknowledge a report when it is received, assess impact,
coordinate a correction and agree disclosure timing with the reporter. No
fixed response deadline is promised for this volunteer-maintained project.
