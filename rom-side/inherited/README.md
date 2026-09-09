# Inherited ROM material

This directory holds what the 1MHz-WiFi ROM still derives from somebody else's
work. It exists so that the licence question has a single, visible answer:
anything under `../1mhz-wifi/` is ours, and anything reached through the
patches here is not.

The base is ElkWiFi 0.23 at commit
`7bf366c97bec18bd238963c95e6f2aa6893cdb3a`, and `../build_rom.sh` requires a
checkout of it.

## What is left

One file. Every patch in `patches/` now applies to `rom/wicfs.asm` and nothing
else. The main ROM file, the helper routines, the equate header and the `JOIN`,
`LAP`, `IFCFG` and `MODE` commands were rewritten for this project and moved to
`../1mhz-wifi/src/`, and the thirteen patches that existed only to modify those
files were removed with them.

`wicfs.asm` is the cassette filing system. Roughly a third of the assembled ROM
comes from it, and about a third of its source lines are still inherited. The
part that remains is the UEF and CFS format engine: the chunk walker, the CFS
block header decode, the buffer refill, the file search and the `*LOAD` and
`*RUN` paths.

## Two upstream authors, and no licence

This is the part that matters, and it is why the directory is called
`inherited` rather than `elkwifi`.

`wicfs.asm` is not Roland Leurs' code. Its own header reads:

```
\             (c) Martin Barr 2012
\             (c) Roland Leurs 2020
\        based on UPCFS by Martin Barr
```

So the file descends from Martin Barr's UPCFS, with Leurs' ElkWiFi adaptation
on top and this project's on top of that. Neither ElkWiFi nor UPCFS ships a
licence file, so there are two copyright holders in the chain and no stated
terms from either.

Nothing here may be relicensed, published as source or offered to another
project until that is resolved, by permission from both authors or by replacing
the file. Both are contactable: UPCFS and Barr's UPURS suite are published on
retro-kit.co.uk and he is active on Stardot, and ElkWiFi already ships his code,
so Leurs faced the same question in 2020 and may be able to introduce him.

## Working here

Run `../build_rom.sh /path/to/ElkWiFi` against a clean checkout; the script
checks the revision, applies these patches, installs the 1MHz-WiFi sources over
the tree and assembles. It is not idempotent and never has been, because some
patches are detected by markers that later patches change: build from a fresh
checkout each time.

Changes to inherited files belong in a patch here, not in a private upstream
working tree. New code does not belong here at all: write it in
`../1mhz-wifi/src/` instead, so this directory only ever shrinks.
