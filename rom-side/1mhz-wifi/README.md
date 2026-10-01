# 1MHz-WiFi ROM: this project's additions

The 1MHz-WiFi host ROM lives in dp111's Pi1MHz as `beeb/1mhz-wifi`. He merged
it from this project at V1.34 and has maintained it since, fixing faults this
project's copy still carried. This directory does not keep a copy of it. It
keeps what this project adds on top, and `../build_rom.sh` composes the two at
the Pi1MHz commit pinned in `../../pi-side/upstream.env`.

When upstream changes a file, its version is the input to the next build, and
the rebase is limited to making the patches here apply again. There is no
per-file decision about whether to take an upstream change.

## Patches to upstream's files

Applied in this order; each assumes the ones before it.

| patch | what it does | upstream? |
| --- | --- | --- |
| `read-only-bank.patch` | In a read-only bank, decline service call 4 instead of raising an error that the MOS cannot read back, and say why once at reset | candidate |
| `help-long-name.patch` | `*HELP WIFI` no longer runs `DISCONNECT` into its description | candidate |
| `ftp-command.patch` | `*FTP`, behind `INCLUDE_FTP`, which is off | no: the Pi-side FTP service is this project's |
| `eprom-workspace.patch` | `WS_IN_IMAGE=0`: the same sources as a real EPROM, with workspace claimed from the OS | possible |

## Images

| image | root and switches | use |
| --- | --- | --- |
| `1mhz-wicfs.rom` | `1mhzwifi.asm`, upstream's merged configuration: `INCLUDE_WICFS=1`, `INCLUDE_RAMDISK=1`, `INCLUDE_PDUMP=0`, `HELP_BRIEF=1` | what Pi1MHz serves: helper 16 loads it |
| `1mhz-wifi.rom` | `1mhzwifi.asm`, upstream's non-merged switches | the network ROM on its own |
| `1mhz-wicfs-only.rom` | `src/1mhzwicfs.asm` | the filing system on its own |
| `1mhz-wifi-eprom.rom`, `1mhz-wicfs-only-eprom.rom` | the two above with `WS_IN_IMAGE=0` | a burnt EPROM |

`1mhz-wicfs.rom` is upstream's image with this project's additions compiled
in; this project does not ship its own image under that name. The split
images are for the emulator runners, a ROM board and the EPROM builds, and no
Pi1MHz helper loads them.

`*FTP` is built only with `INCLUDE_FTP=1`, and is off in every image. It costs
1,295 bytes and the merged image has 268 free, so it fits only with
`INCLUDE_RAMDISK=0`, and which of upstream's features gives way is upstream's
decision. The Pi-side FTP service is built regardless, so turning it on is a
ROM rebuild.

`src/1mhzwicfs.asm` carries the UEF commands, the host language transition and
`wicfs.asm`, which is the only inherited file. It answers its own reset
service call and releases its own vectors, so the split network ROM does not
reach into it.

## Sources upstream does not carry

The sources in `src/` are:

- `1mhzwicfs.asm`, the root of the split filing system image.
- `ftp.asm`, the `*FTP` client, which talks to the Pi-side FTP service on
  service commands 128 to 133. Assembled only with `INCLUDE_FTP=1`.
- `uef.asm`, `host_launch.asm`, `wicfs_errors.asm`, `wicfs_messages.asm` and
  `wicfs_catalogue.asm`, the filing system's own sources. dp111's
  `build-merged.sh` fetches these five from this path, so they stay here.

The build refuses a file in `src/` with the same name as one of upstream's.

## The contract between the split images

The split images do not call each other. `*WGET -U` leaves a UEF image in the
public JIM window with its length in the last two bytes of page `&FF`, and
the filing system ROM reads it there when it is selected. Since Pi1MHz
`0851ad5` the network ROM no longer writes `&C7`, `&C8`, `&F8` or `&F9`, which
belong to the current filing system and the MOS. Either image works with the
other absent.

## Provenance

The network ROM is now built from Pi1MHz's GPL-3.0 tree plus the patches
here. Every file in that tree began as this project's work, and upstream's
changes to it since V1.34 are dp111's. Nothing inherited from ElkWiFi or UPCFS
is in it; that lineage is confined to `wicfs.asm` in the filing system image.
See `../inherited/README.md`.

## Names that are deliberately kept

Three kinds of name are retained on purpose, and none of them implies inherited
code.

Short functional entry point names such as `printtext`, `skipspace` and
`printhex` are the interface every other file in the ROM calls through. They
are conventional, they carry no design of their own, and renaming them would
churn every caller for no benefit.

The command table format is kept because the entries are written in it: a name
in ASCII followed by the handler address, high byte first, with the high byte of
an address doubling as the end of name marker. The search that walks it is new;
the layout is what the data is.

The ElkWiFi compatibility ABI keeps its ElkWiFi names, because that is what it
is. OSWORD `&65`, its function numbers, and the Pi-side `elkwifi_service` exist
specifically to implement the interface ElkChat and other third party clients
already call. Renaming them would break those clients and would misdescribe the
component.

## Attribution

Attribution belongs to the parts that still derive from ElkWiFi, not to the ROM
as a whole, and it is carried in `*VERSION` rather than in the banner. The
credit is not to be removed; it is to be accurate about scope.
