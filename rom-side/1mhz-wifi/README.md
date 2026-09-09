# 1MHz-WiFi ROM source

This directory is the host sideways ROM for 1MHz-WiFi, and everything in it was
written for this project. It is kept apart from `../inherited/` so that the
question "what may we license, publish or offer upstream?" is answered by a
path rather than by a line by line comparison against somebody else's tree.

`src/1mhzwifi.asm` is the assembly root. It carries the image header, the
service entry, the command table and its search, `*HELP`, the reset banner and
the public OSWORD `&65` entry, and it includes every other source in the ROM.

## What is here, and what is not

Everything under `src/` is this project's work and carries no ElkWiFi or UPCFS
lineage. The ROM is not yet buildable from this directory alone: one file,
`wicfs.asm`, is still produced by patching an ElkWiFi 0.23 checkout, and
`../inherited/` holds those patches and explains the position. Until that file
is replaced too, `../build_rom.sh` needs an ElkWiFi checkout to build the ROM.

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
