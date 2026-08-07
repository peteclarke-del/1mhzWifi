# Third-party notices

This repository contains integration work derived from or applied to two
upstream projects:

| Project | Upstream | Revision basis |
| --- | --- | --- |
| ElkWiFi | <https://github.com/hoglet67/ElkWiFi> | `7bf366c97bec18bd238963c95e6f2aa6893cdb3a` |
| Pi1MHz | <https://github.com/dp111/Pi1MHz> | `8468a38f63b25785007a50912a3b32a596db8ff9` |
| MMFS | <https://github.com/hoglet67/MMFS> | 1.60 Electron Pi1MHz `EMMFS.rom` |
| zlib puff | <https://github.com/madler/zlib/tree/v1.3.1/contrib/puff> | `v1.3.1`, puff 2.3 |
| wolfSSL | <https://github.com/wolfSSL/wolfssl> | `65836b40693f8ea8d04daac0b1019d8e2e9394dd` |
| wolfSSH | <https://github.com/wolfSSL/wolfssh> | `c2d169872e410251a6967fc47d4fc0c6f318b79c` |

ElkWiFi identifies Roland Leurs as the original ROM author and credits Martin
Barr and Roland Leurs for WiCFS. Pi1MHz and its submodules contain their own
copyright and licence notices. The SD-card bundle also contains Raspberry Pi
boot files and Broadcom wireless firmware accompanied by
`LICENCE.broadcom.txt`.

`pi-side/firmware/EMMFS.rom` is the unmodified Electron normal-ROM build for
the Pi1MHz device from the official MMFS 1.60 release. MMFS identifies Martin
Mather as the original developer and David Banks as the current maintainer;
its source repository is licensed under GPL-3.0.

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
