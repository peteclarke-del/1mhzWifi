# Candidate patches

These are not part of any build. `rom-side/build_rom.sh` does not reference
them, and the ROM in `build/` is unaffected. They are kept because they carry a
validated design whose only remaining problem is where a small resident block
lives, and re-deriving them would cost more than storing them.

## wicfs-signature-checked-repair.patch.candidate

Points the filing vectors permanently at the MOS extended entries, so no RAM
address is ever a filing vector target and a cassette loader cannot replace the
filing system with its own code. The extended-vector table is repaired instead
by a helper in `&07xx`, and the BYTEV `*TAPE` trap verifies a signature byte in
that helper before calling it, so a helper overwritten by game code is skipped
rather than executed. The repair body, its offset tables and the handler
addresses live in ROM; only a 40-byte pager is resident.

The design is confirmed working. With the trap at `&0100`, Repton reaches
sustained gameplay: the host RAM dump shows the helper at `&0780` overwritten
by game data and the trap intact, so the signature check skipped the helper and
the load completed. That is the exact case which defeated every earlier design.

The trap placement is wrong. Last of the Free stalls at about seven percent of
its stream, and its RAM dump shows `&0100-&0113` holding stack frames rather
than the trap, while the helper is intact. The 6502 stack descended into the
trap and destroyed it, after which every OSBYTE entered stack data. Only
4.1% of the corpus loads cassette blocks across `&0100-&013F`, but that figure
counts tape loads and not run-time stack depth, and the WiCFS call chain is
itself deep enough to reach the bottom of the page.

To finish this the trap needs about twenty bytes in the cassette page, which is
the only materially safer region at about 3.4% of the corpus. The page has
about nine free bytes, scattered, so it must be repacked: the CFS filename
buffer at `&03D2-&03DF` and the chunk header state at `&03CB-&03D0` are the
relocation candidates, and together they need slightly more room than the trap
frees.

One hazard this candidate already fixes is worth keeping. The repair must never
call OSBYTE. BYTEV is the trap which reaches the repair, so an `OSBYTE &A8` to
read the extended-vector table address re-enters the trap and recurses without
bound, overflowing the stack. The table address is captured once at install
time instead, where calling OSBYTE is safe.

## Progress log

Each candidate failed for a distinct, identified cause. None was a guess
overturned by another guess; every one was settled from a RAM dump or an
emulator trace.

| Placement | Repton | Last of the Free | Cause |
| --- | --- | --- | --- |
| gateway as vector target, `&0780` | fails | passes | loader replaces the gateway the vectors point at |
| gateway deleted | passes | fails | no repair, and Last of the Free needs one |
| repair per OSBGET refill | passes | fails | corruption and the next filing call fall in one window |
| smaller gateway, `&07C1` | fails | passes | Repton's filler runs to `&07FF`; the page is wholly consumed |
| trap at `&0100` | passes | fails | the 6502 stack descends into the trap |
| trap at `&03CB`, `BIT` signature | fails | passes | `A9` matches a two-bit test, so the trap called game code |
| trap split, `&0398` and `&03CB` | passes | stops after `B-CODE` | the MOS zeroes `&0780`, disarming the helper |
| plus helper self-heal from `fillget` | passes | stops after `B-CODE` | five of seven files load; cause not yet identified |

The current candidate reaches sustained Repton gameplay and carries Last of the
Free through `FREE`, `SCREEN0`, `SCREEN1`, `A-CODE` and `B-CODE` before
stopping. `C-CODE` and `FREE2` do not load. On the shipped 0.1.66 ROM that
title reaches its start prompt, so this is still a regression for it and the
candidate is not promotable.

## Accepted exposure

`hchunk`, the UEF chunk type and remaining length, now lives at `&07A8` in the
loader-exposed page. That was a deliberate choice: the cassette workspace had no
room, and the alternative was shortening the CFS filename limit below the ten
characters the format allows, which would reject names real games use. The
Repton dump shows `&07A8` full of game data during a load, so the exposure is
real and active, and it has not yet been measured against the corpus.
