# MENU retirement

ROM version 0.1.63 removes `*MENU` and `*MENUSRC`. The published Electron
menu, its run-time binary patcher, URL persistence and Pi-side cache were
specific to one upstream service and obscured defects in the generic UEF
path. They are not part of the current build.

The following facilities remain:

- `*WGET` for generic HTTP downloads
- `*PING` and `*NSLOOK` as resident ROM commands
- the ElkWiFi-compatible OSWORD `&65` network interface
- `*UEF LOAD`, `*WGET -U`, `*WICFS` and `*REWIND` for generic UEF transport
- `*TELNET`, `*SSH` and `*HWDTEST` on the NetTools SSD

The host BASIC and cassette transition formerly embedded in the MENU module
is retained in `overlay/host_launch.asm` because `*UEF LOAD` needs it. That
module contains no URL, catalogue, menu download or menu-cache behavior.

The original 1MHz-WiFi ROM still contains its own `*MENU` implementation. The
final `menu-retirement.patch` removes that command and its source include from
the 1MHz-WiFi build. Earlier ordered patches may mention the upstream labels as
patch context, but the assembled ROM contains neither command nor endpoint.
