# 1MHzWifi ElkWiFi ROM patch kit

This directory is the independently distributable host-ROM patch kit. It
targets the original ElkWiFi source at commit
`7bf366c97bec18bd238963c95e6f2aa6893cdb3a`.

Contents:

- `build_rom.sh`: verifies, patches and assembles an upstream checkout.
- `elkwifi-0.23/patches/`: ordered changes to retained upstream files.
- `elkwifi-0.23/overlay/`: complete replacement or added assembly sources.
- `elkwifi-0.23/README.md`: base revision and application instructions.
- `elkwifi-0.23/TECHNICAL.md`: design, ABI and change record.

Build from a clean upstream checkout:

```sh
./build_rom.sh /path/to/ElkWiFi
```

The ROM is written to `../build/elkwifi_pi1mhz.rom` relative to this
directory. The monorepo release build verifies its size and recorded SHA-256.
The source build is deterministic, but physical Electron, filing-system and
Tube coexistence tests remain separate acceptance gates.
