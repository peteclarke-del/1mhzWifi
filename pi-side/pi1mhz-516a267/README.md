# Pi1MHz patch package

This directory contains the changes applied to Pi1MHz commit
`d08242ee1b35cf1285b72c9ec1869e98081a8c3e`. This was the tip of the official
`master` branch when verified on 15 August 2026. It is 84 commits after the
V1.30 tag and includes the later network-service foundation, H.264 decoder
work and updated CYW43455 firmware.

- `patches/` contains the ordered Pi1MHz source patches.
- `overlay/` contains the ElkWiFi service and UEF normalisation sources copied
  into the upstream tree.
- `TECHNICAL.md` records the state machines, ABI, firmware and persistence
  changes.

Run `../install_bundle.sh /path/to/Pi1MHz all` from a clean checkout. The
installer verifies the exact upstream commit before applying this package and
building the Raspberry Pi Zero and Raspberry Pi 2/3 kernel families.
