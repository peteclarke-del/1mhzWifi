# Security policy

This project handles WiFi credentials and network traffic on an 8-bit host and
a bare-metal Raspberry Pi. It is not suitable for untrusted networks in its
current form.

## Known limits

- Saved WiFi profiles and `Pi1MHz.cfg` passwords are plaintext on the FAT partition.
- HTTP and raw TCP are plaintext.
- TLS, HTTPS, and SSH are not implemented.
- WEP and WPA1 are available only for compatibility with legacy access points.
- The Acorn host does not provide process or memory isolation.

Secure transport requests fail closed. A change that silently retries a secure
request over plaintext is a security defect.

## Reporting

Do not open a public issue containing a real SSID, password, packet capture,
private key, or SD-card image. Use GitHub private vulnerability reporting when
it is enabled for the repository. Otherwise contact the repository owner
privately before publishing details.

Include affected ROM and kernel hashes, hardware models, the shortest command
sequence that reproduces the issue, and sanitised logs.

