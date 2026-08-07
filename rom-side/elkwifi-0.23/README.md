# ElkWiFi 0.23 patch package

This directory contains the ROM changes applied to the upstream ElkWiFi source.
The build requires upstream commit `7bf366c97bec18bd238963c95e6f2aa6893cdb3a`.

- `patches/` contains the ordered source patches applied by `../build_rom.sh`.
- `overlay/` contains complete assembly files installed into the upstream tree.

Run `../build_rom.sh /path/to/ElkWiFi` from a clean upstream checkout. The
script checks the upstream revision, applies this package and builds the ROM.
Changes to the ROM must be recorded here, not left in a private upstream
working tree.
