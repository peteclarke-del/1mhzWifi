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
