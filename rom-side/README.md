# 1MHz-WiFi host ROM

The host sideways ROM for 1MHz-WiFi: a 16 KiB image for a BBC Micro or Acorn
Electron that talks to Pi1MHz over the 1 MHz bus.

The directory is split by provenance, so that what may be licensed, published
or offered upstream is decided by a path rather than by a diff:

- `1mhz-wifi/src/`: the ROM sources, written for this project. `1mhzwifi.asm`
  is the assembly root.
- `inherited/patches/`: what still derives from ElkWiFi 0.23 and, through it,
  Martin Barr's UPCFS. All of it now applies to one file, `wicfs.asm`.
- `inherited/TECHNICAL.md`: transport, ABI and loader change record.
- `build_rom.sh`: applies the patches, installs the sources and assembles.
- `candidates/`: changes kept for reference that are not in the build.

Read `inherited/README.md` before reusing anything: two upstream authors have a
claim on `wicfs.asm` and neither has stated terms.

## Building

```sh
./build_rom.sh /path/to/ElkWiFi
```

The checkout must be at ElkWiFi commit
`7bf366c97bec18bd238963c95e6f2aa6893cdb3a`, and must be clean: the script is
not idempotent, because some patches are detected by markers that later patches
change.

An ElkWiFi checkout is needed only for `wicfs.asm`, and only for the filing
system image. `1mhzwifi.asm` assembles on its own with no ElkWiFi source
present at all, which is what makes the network ROM licensable separately.

Two images are written:

- `../build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom`, the network ROM, entirely this
  project's own code, with `../build/elkwifi_pi1mhz.rom` kept as a
  compatibility symbolic link to it.
- `../build/pi1mhz-all/Pi1MHz/1mhz-wicfs.rom`, the filing system ROM, which
  carries the inherited `wicfs.asm`.

The release build checks the size and recorded SHA-256 of the network image.
The source build is deterministic; physical Electron, filing system and Tube
coexistence tests remain separate acceptance gates.
