# Third-party notices

This repository contains integration work derived from or applied to two
upstream projects:

| Project | Upstream | Revision basis |
| --- | --- | --- |
| ElkWiFi | <https://github.com/hoglet67/ElkWiFi> | `7bf366c97bec18bd238963c95e6f2aa6893cdb3a` |
| Pi1MHz | <https://github.com/dp111/Pi1MHz> | `516a267493d9f19e6bf2f4a2ea4c3e7472b12135` |
| zlib puff | <https://github.com/madler/zlib/tree/v1.3.1/contrib/puff> | `v1.3.1`, puff 2.3 |
| wolfSSL | <https://github.com/wolfSSL/wolfssl> | `65836b40693f8ea8d04daac0b1019d8e2e9394dd` |
| wolfSSH | <https://github.com/wolfSSL/wolfssh> | `c2d169872e410251a6967fc47d4fc0c6f318b79c` |
| vrEmu6502 | <https://github.com/visrealm/vrEmu6502> | `aae98cb14386d832cb7357c99626520b6590bc24` |

ElkWiFi identifies Roland Leurs as the original ROM author and credits Martin
Barr and Roland Leurs for WiCFS. Pi1MHz and its submodules contain their own
copyright and licence notices. The SD-card bundle also contains Raspberry Pi
boot files and Broadcom wireless firmware accompanied by
`LICENCE.broadcom.txt`.

No project-wide licence has been inferred for this repository. The upstream
ElkWiFi checkout used by this project does not contain a licence file. Before
publishing source or binary releases, the repository owner should confirm the
intended licence and that redistribution of the generated ROM is authorised.
Existing upstream notices must be retained.

The Pi-side UEF normalizer includes Mark Adler's `puff.c` and `puff.h` from
zlib 1.3.1. Their zlib-compatible copyright and permission notice is retained
verbatim in `puff.h`. The files are unmodified apart from their placement in
the Pi1MHz source overlay.

The Pi secure service links pinned wolfSSL and wolfSSH source revisions during
the Pi1MHz build. Their source is not vendored in this repository. Their GPLv3
licence terms and commercial licensing options remain those published by
wolfSSL Inc.; an upstream submission or binary distribution must retain and
review the corresponding notices.

The Elkulator AP5 Tube integration vendors the vrEmu6502 CPU core under its
MIT licence. The exact upstream licence is retained at
`emulator/pi1mhz-mailbox/integrations/elkulator/tube/LICENSE.vrEmu6502`.
