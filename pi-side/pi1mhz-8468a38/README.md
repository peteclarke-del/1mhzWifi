# Pi1MHz 8468a38 patch package

This directory contains the changes applied to Pi1MHz commit
`8468a38f63b25785007a50912a3b32a596db8ff9`. This was the tip of the official
`master` branch when verified on 7 August 2026. It is 80 commits after the
V1.30 tag and includes the later network-service foundation used by 1MHzWifi.

- `patches/` contains the ordered Pi1MHz source patches.
- `overlay/` contains the ElkWiFi service and UEF normalisation sources copied
  into the upstream tree.

Run `../install_bundle.sh /path/to/Pi1MHz all` from a clean checkout. The
installer verifies the exact upstream commit before applying this package and
building the Raspberry Pi Zero and Raspberry Pi 2/3 kernel families.
