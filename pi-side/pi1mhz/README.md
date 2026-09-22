# Pi1MHz patch package

This directory contains the changes applied to Pi1MHz commit
`4c54d8118f632465f31ecb72dcc37b4833c2507a`, the V1.35 build and the tip of the
official `master` branch when verified on 22 September 2026.

V1.35 merged most of what this package used to be. The WiFi service (now
`src/wifi_service.c`), the UEF tape (`src/uef_service.c` and
`src/uef_stream.c`), the SSH/SFTP service and its wolfSSL/wolfSSH build,
LWIP_RAW and the service command-range allocation are all upstream, and
upstream's copies carry fixes these did not, so none of them is shipped here
any more.

- `patches/` contains the ordered Pi1MHz source patches: the FTP service and
  the container decoder wired into the build, the FILEV stamp repair on
  upstream's streaming UEF path, and net command 58.
- `overlay/` contains the sources those patches add: the FTP service, the
  container decoder, and a test for the repair that joins upstream's own UEF
  suite.
- `TECHNICAL.md` records the state machines, ABI, firmware and persistence
  changes.

Run `../install_bundle.sh /path/to/Pi1MHz all` from a clean checkout. The
installer verifies the exact upstream commit before applying this package and
building the Raspberry Pi Zero and Raspberry Pi 2/3 kernel families.
