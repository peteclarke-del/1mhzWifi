# Third-party notices

This repository contains integration work derived from or applied to two
upstream projects:

| Project | Upstream | Revision basis |
| --- | --- | --- |
| ElkWiFi | <https://github.com/hoglet67/ElkWiFi> | `7bf366c97bec18bd238963c95e6f2aa6893cdb3a` |
| Pi1MHz | <https://github.com/dp111/Pi1MHz> | `4c54d8118f632465f31ecb72dcc37b4833c2507a` (V1.35) |
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

Mark Adler's `puff.c` and `puff.h` from zlib 1.3.1 were carried here while
this project supplied the Pi-side UEF decoder. Pi1MHz V1.35 merged that work
and decodes with its own vendored uzlib instead, so the files are no longer in
this repository and the notice they required no longer applies to it. uzlib's
own notice is Pi1MHz's to carry.

The Pi secure service links pinned wolfSSL and wolfSSH source revisions during
the Pi1MHz build. Their source is not vendored in this repository. Their GPLv3
licence terms and commercial licensing options remain those published by
wolfSSL Inc.; an upstream submission or binary distribution must retain and
review the corresponding notices.

wolfSSH is taken from a fork at
<https://github.com/peteclarke-del/wolfssh>, which carries two commits on top
of the revision above: a portability fix for client-only embedded builds, and
the Acorn 40-column vt100 defaults. The first was offered as wolfSSL/wolfssh
#1215 and closed unmerged, because wolfSSH can only accept a change against a
contributor agreement; the maintainer said he would recreate it as a bug fix
instead. The fork remains until that lands.

The Elkulator AP5 Tube integration vendors the vrEmu6502 CPU core under its
MIT licence. The exact upstream licence is retained at
`emulator/pi1mhz-mailbox/integrations/elkulator/tube/LICENSE.vrEmu6502`.
