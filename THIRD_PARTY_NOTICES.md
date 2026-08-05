# Third-party notices

This repository contains integration work derived from or applied to two
upstream projects:

| Project | Upstream | Revision basis |
| --- | --- | --- |
| ElkWiFi | <https://github.com/hoglet67/ElkWiFi> | `7bf366c97bec18bd238963c95e6f2aa6893cdb3a` |
| Pi1MHz | <https://github.com/dp111/Pi1MHz> | `8468a38f63b25785007a50912a3b32a596db8ff9` |
| zlib puff | <https://github.com/madler/zlib/tree/v1.3.1/contrib/puff> | `v1.3.1`, puff 2.3 |

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
