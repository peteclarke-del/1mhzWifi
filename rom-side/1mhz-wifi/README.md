# 1MHz-WiFi ROM source

This directory is the host sideways ROM for 1MHz-WiFi, and everything in it was
written for this project. It is kept apart from `../inherited/` so that the
question "what may we license, publish or offer upstream?" is answered by a
path rather than by a line by line comparison against somebody else's tree.

There are two assembly roots here, one per image.

`src/1mhzwifi.asm` builds `1mhz-wifi.rom`, the network ROM. It carries the
image header, the service entry, the command table and its search, `*HELP`,
the reset banner, the public OSWORD `&65` entry and the RAM disk. Nothing it
includes derives from anyone else's work, and it assembles with no ElkWiFi
source present.

`src/1mhzwicfs.asm` builds `1mhz-wicfs.rom`, the filing system ROM. It carries
the UEF commands, the host language transition and `wicfs.asm`, which is the
only inherited file left. It answers its own reset service call and releases
its own vectors, so the network ROM does not reach into it.

The two images do not call each other. What passes between them is data in the
JIM window, together with the four bytes `machine.asm` documents as the
contract: the stream length in `sbufl` and `sbufh`, and the cursor in `pr_y`
and `pr_r`. Either image works with the other absent.

Several sources are compiled into both: `machine.asm`, `util.asm`,
`errors.asm`, `serial.asm`, `service_driver.asm`, `net_transport.asm` and
`driver.asm`. Shared code is compiled twice rather than called across banks,
because a cross-ROM call would make each image depend on the other being
fitted.

`src/ramdisk.asm` is the RAM disk: 65,024 bytes in up to 15 files, held in the
low 64 KiB JIM window. It stays in bank 0, which is the only bank an
unmodified Electron AP5 forwards, so it behaves the same on the Electron and
on the BBC family. Page 0 is the OSWORD `&65` service reply buffer and is left
alone; page 1 is the catalogue; files follow from page 2 on page boundaries.
Catalogue entries are 16 bytes so an entry's offset is four shifts and an add,
and load, execution and length are stored adjacently because they are read and
written as one six byte run.

## What is here, and what is not

Everything under `src/` is this project's work and carries no ElkWiFi or UPCFS
lineage.

The network ROM builds from this directory alone. That was verified by
deleting every WiCFS and UEF source from a copy of `src/` and assembling
`1mhzwifi.asm` against what remained: it produced an image byte for byte
identical to the one built alongside them.

The filing system ROM still needs an ElkWiFi 0.23 checkout, because one file,
`wicfs.asm`, is produced by patching it. `../inherited/` holds those patches
and explains the position. When that file is replaced, the checkout is no
longer needed for either image.

Several files here began as complete replacements written earlier in the
project, and were always ours: the Pi1MHz service driver, the network commands,
FTP, the UEF and host launch paths, `nslook`, `errors` and `serial`. The rest
were rewritten to remove inherited code, and say so in their own headers.

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
