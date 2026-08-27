# Hardware validation plan

Use this checklist for each release candidate. Record the Acorn model and MOS,
expansion hardware, Tube parasite, Pi model, Pi1MHz upstream commit, ROM and
kernel hashes, access point, SD card, and power arrangement. Do not record real
WiFi passwords.

An item checked against an earlier binary must be repeated after a ROM, kernel,
or protocol change that can affect it.

## Current artifact identity

```text
Pi1MHz       e949f2d2714b15f314df375e52db5febb6c40e6d
1MHzWifi ROM afc0734188cb6b1b5b7068efe9ca6c937f0802773b2a2753e13942049491831a
kernel.img   fca669d1bb6714877de7ceccc1c85967c79701b21e6801e381e9e7e5d67f1145
kernel7.img  f18ecb8b374db812bbb88dfc6c500abb164f4c11c71ae0f3ffe82c6a7ad83426
nettools.ssd 7bfe26b2c8f3212466bd3bdbc7f40e6f1d72722a3dbcc7a9f25fd3858dc8d883
bundle ZIP   1b7684f494f4a97d92319b9e562305670c74e32c0139a7f6885f0b4370885047
```

The Pi1MHz commit was the official `master` tip verified on 23 August 2026. Run
`./pi-side/check_upstream.sh` before producing another hardware-test bundle.

For this update, preserve the existing `Pi1MHz.cfg` and saved `ElkWiFi.*`
files. Replace `kernel.img` or `kernel7.img` for the fitted Pi, the host
`ElkWiFi.rom`, and the separately mounted `nettools.ssd`. The universal ZIP is
for a clean card and may contain a fresh configuration template.

Also preserve `/BeebSCSI0` and its `scsi*.dat` images. The bundle supplies the
ADFS ROM and default geometry configuration, not a BeebSCSI hard-disc image.

## Vector gateway location study, 27 August 2026

### Implementing the Pi-resident trampoline

Both blocking facts are now measured. The 6502 executes code the Pi serves at
`&FD00`, and a region mirrored into every JIM page is reachable whatever the
selector holds, which matters because the selector tracks the stream cursor and
was observed at four different values during one load.

What remains is a build across the ROM, the Pi kernel and the window protocol.
The pieces and their costs, so the work can be picked up cleanly:

**The trampoline.** Four entry points, one per filing vector, and a pager which
saves the current ROM, selects the WiCFS bank, enters the handler and restores
the previous bank on return. About 48 bytes. The handlers need no change if the
trampoline synthesises the same stack frame the MOS extended dispatcher builds:
`upfscv` reads the previous ROM number from `&0104,X` at entry, so the
trampoline must push an equivalent frame before jumping. That is cheaper than
rewriting four handlers.

**The window arithmetic.** A mirror at offsets `&E0-&FF` leaves 224 usable
bytes per page. `getbyte` currently wraps on `INY` reaching zero and increments
the page; it must wrap at `&E0` instead, which is four more bytes. The Pi must
pack to match, so `uef_stream_publish` becomes a scatter copy of 224 bytes per
page rather than one linear `memcpy`.

**The length trailer.** The published window length currently sits at the top
of the last page, inside the region a top-of-page mirror would cover. It has to
move to the last usable offsets, and both sides must agree.

**Throughput.** Reserving 32 of every 256 bytes costs an eighth of the window,
taking it from 65280 to about 57000 bytes. Most titles are far smaller than one
window, so they see no extra refills at all; only images above about 57 KB pay,
which in the local corpus is Repton 3, Repton Around The World and Repton
Infinity. The practical cost is therefore much smaller than the percentage
suggests.

**The Pi kernel.** The emulator adapter mirrors and the kernel must do the same,
which is Pi-side C plus an ARM rebuild. Older kernels must keep working: a ROM
which asks for a mirror and does not get one has to fall back to the present
behaviour rather than point its vectors at unserved addresses.

None of this is speculative any more, but it is a build rather than another
placement experiment, and it should be done with the joint gate and the sixteen
title probe rerun against the measured three quarter baseline.

### Measured UEF baseline on the shipped ROM

Sixteen titles were run on the 0.1.66 ROM, chosen to span the risk groups the
corpus analysis predicts. Each was staged into a disposable copy of the
BeebSCSI image in turn, so every run used the same profile as the acceptance
gates.

| Group | Corpus share | Probed | Stream fully consumed |
| --- | --- | --- | --- |
| Touch neither region | 73.0% | 6 | 6 |
| Write `&0700-&07FF` | 6.7% | 3 | 0 |
| Write `&0D9F-&0DEF` | 14.3% | 4 | 1 |
| Write both | 5.9% | 1 | 0 |

The predictive model therefore holds: titles which avoid both regions load, and
those which write either largely do not. Projected across the corpus, about
three quarters of the collection loads on the shipped ROM, and every failure
falls into one of the two identified groups.

The figure measures whether the stream was consumed, spot checked against the
screen. It is a load-completion rate, not a proof of sustained gameplay for all
sixteen, and should be read as approximate.

### Executing the trampoline from Pi RAM is possible

Both failure groups exist only because WiCFS needs somewhere in host memory
that games treat as spare. `&FD00-&FDFF` is the JIM window: permanently mapped,
served by the Pi, and outside the address space a game writes. If the filing
vectors pointed at a trampoline the Pi serves there, neither group could reach
it.

That rests on the 6502 being able to execute code fetched across the 1MHz bus,
which was measured rather than assumed. A temporary `*JIMTEST` command selected
a JIM page, waited for the selector to publish, and called `&FD00`, where the
Pi served:

```text
A9 5A 85 70 A9 A5 85 71 60      LDA #&5A / STA &70 / LDA #&A5 / STA &71 / RTS
```

The host RAM dump afterwards holds `&0070=5A` and `&0071=A5`. Pi RAM ran as
code. `run_uef_gameplay.py --probe-command` was added to drive a single ROM
command in the real boot profile, and is how this was measured.

One assumption remains untested. `&FCFF` selects which Pi page appears at
`&FD00`, WiCFS moves it constantly while streaming, and it is write only, so it
cannot be read back and verified. A filing vector firing while the selector
points at a data page would execute UEF data. The rule would be that WiCFS
restores the selector to the trampoline page before returning to any caller,
since vectors fire from the loader and not from inside WiCFS, but that has to be
demonstrated before the design is built on, and the behaviour of other JIM users
has to be considered with it.

### Disc images avoid the problem entirely

Tape software was written for a machine whose filing system lives in the MOS
ROM and has no RAM footprint at all, so `&0700-&07FF` and `&0D9F-&0DEF` are
genuinely spare there and titles use them freely. 76% of the corpus loads
something below `&1900`.

A disc build of the same game could not do that. DFS occupies the workspace
below `&1900`, including the extended-vector table at `&0D9F`, so disc software
is by construction compatible with a sideways-ROM filing system which claims
vectors the way DFS does. Streaming SSD images should therefore need no
trampoline, no repair and no workspace juggling, and both failure groups
disappear. That argument is structural and has not been measured against real
disc images.

### Repair frequency trades directly against destroying the game

The split trap reaches sustained Repton gameplay and carries Last of the Free
through `FREE`, `SCREEN0`, `SCREEN1`, `A-CODE` and `B-CODE` before stopping
short of `C-CODE` and `FREE2`. Instrumenting that stop corrects two earlier
readings.

The MOS does clear the helper, writing zero across `&0780-&07A7` from
`PC=D902`, but the write trace places that at line 9277 of 9318, after the load
has already stopped. It is teardown, not a mid-load disarm, so the helper was
intact throughout and the self-heal added to `fillget` addresses something
which happens too late to matter. It is cheap and harmless, but it is not the
fix it was thought to be.

More importantly, the vectors are healthy at the point of failure:

```text
PC=FFF7 ... FSC=FF2D FILE=FF1B FIND=FF2A LEN=4FA5 CLI=*L.B-CODE
PC=A129 RB=B ... FSC=FF2D FILE=FF1B FIND=FF2A LEN=4FA5
```

All four vectors are still the MOS extended entries and the repair is working.
Control simply returns to BASIC. This is not a vector failure.

That points back at a tension noted earlier and then set aside. Last of the
Free loads file data across `&0D9F-&0DEF`. Those bytes are the extended-vector
table and the game's data at the same time, so every repair is also damage. The
retired gateway wrote three bytes, once, at the moment a filing vector was
entered. Reaching the repair from BYTEV instead means writing twelve bytes on
every OSBYTE, which keeps the table perfect and destroys far more of what the
game just loaded.

The frequency of repair therefore trades directly against how much of the game
is corrupted, and no BYTEV-driven design can improve on this, because BYTEV
cannot know which vector is about to be used or whether one is needed at all.
Repairing only what differs does not help either: while the game's data
occupies those bytes they always differ.

This is the strongest argument yet for the original cartridge's shape, in which
the filing vectors point at a small RAM trampoline which pages the ROM in and
jumps, and no table is consulted or repaired at all. Its single weakness is
that the trampoline can be overwritten, and the measured ownership map now
shows the cassette page is the right home for one: 3.4% of the corpus against
11.8% for `&07xx`. The obstacle is size. The original needed eighty bytes and
the cassette page currently offers about twenty six.

### Exposure of the relocated chunk header

Moving `hchunk` to `&07A8` bought the space for the split trap. Measured across
the corpus:

| Region | Titles | Share |
| --- | --- | --- |
| `hchunk` `&07A8-&07AD` | 83 | 11.4% |
| helper `&0780-&07A7` | 86 | 11.8% |
| `cfsname` `&07B8-&07C2` | 82 | 11.3% |
| trap entry `&0398-&039F` | 25 | 3.4% |
| trap body `&03CB-&03DC` | 24 | 3.3% |

The trap is where it should be. The helper's exposure is tolerated because the
signature check detects it. The chunk header's is not detected: corruption
there misparses the stream silently. That is a worse failure mode than the
helper's and it affects 11.4% of the corpus, so the trade taken to buy the
trap's space should be revisited if the design changes again.

### Measured ownership of the cassette workspace

Three placements of the BYTEV trap failed for three different reasons, and each
time the layout had been inferred by reading the ROM source. That method is not
reliable here: the page is shared between the MOS, WiCFS and the loader, it is
aliased across modules, and addresses appear in both `&03B2` and `&3B2` forms,
so two of the failures were simply references that a search missed.

`PI1MHZ_WRITE_WATCH` logs every byte change in a chosen RAM window with the
program counter which caused it, and `run_uef_gameplay.py --write-watch LO:HI`
drives it. Running Last of the Free over `&03A0-&03DF` gives the first real
ownership map of the page:

| Range | Owner |
| --- | --- |
| `&03A0-&03B8` | WiCFS, the `chain_exec` trampoline |
| `&03A7-&03B1` | WiCFS, the BGET filename store, aliased over `chain_exec` |
| `&03B2-&03BC` | WiCFS, the CFS block name |
| `&03BE-&03CA` | WiCFS, the CFS block descriptors |
| `&03D1` | **the MOS**, written from `PC=F091` |
| `&03CB-&03D0`, `&03D2-&03DF` | available |

`&03D1` is the only MOS-owned byte in the range, and it sat inside both earlier
placements. That is why those failures looked title-dependent: they turned on
when the MOS next touched the byte, not on what the game loaded.

The map has one important limit. It records changes in value, not writes, so a
byte written with the value it already held is reported as untouched. The
apparently free bytes inside `&03BE-&03CA` are in the descriptor loop's range
and are written every time; they are not free.

### The signature must be compared in full

With `&03D1` known, the trap was placed at `&03CB-&03DF` and the eight-bit
signature compare was replaced by `BIT`, which tests bits 7 and 6 without
disturbing A. That failed immediately. Repton's decryptor begins `A9 00 85 70`,
and `A9` has bit 7 set and bit 6 clear, so it matched the signature and the trap
called straight into game code. `A9`, `AD`, `A5`, `A2` and `A0` are among the
most common 6502 opcodes, so against real code a two-bit test is not a weak
check, it is close to no check at all.

### One byte short

The trap therefore needs the full compare, and the arrangement which tolerates
the MOS byte costs two more bytes, because the hole has to be consumed as the
operand of a discarded instruction rather than skipped by a branch:

```text
CMP #&8C / BEQ eat        4
PHA                       1
LDA #imm                  2   operand at &03D1, value discarded
LDA guard_sig / CMP #&A5  5
BNE restore               2
JSR guard_entry           3
restore PLA               1
JMP OSBYTE                3
eat RTS                   1
                         22
```

`&03CB-&03DF` is twenty one bytes. The trap needs twenty two, and the page has
no spare byte anywhere else once the descriptor and block-name ranges are
counted as written. Splitting the trap so its entry sits in the eight bytes at
`&0398-&039F` works arithmetically, but that space is currently the chunk header
state, which is live throughout streaming and has no safe home elsewhere.

The mechanism is not in doubt. Repton has reached sustained gameplay on three
separate builds with its helper destroyed and the signature check correctly
declining to call it. What is unresolved is finding a twenty second byte, and
that is a decision about which workspace to expose rather than a measurement.

### The signature-checked design works; the deep stack does not hold it

The design above was implemented and run against both halves of the
`WICFS-016` gate. The filing vectors were left permanently on the MOS extended
entries, the repair moved into ROM behind a 40-byte pager in `&07xx`, and the
BYTEV `*TAPE` trap was relocated to `&0100` and grown from eight to twenty
bytes to check a signature before calling the helper.

Repton reaches sustained gameplay, with the timer running down and the score
panel live. Its host RAM dump shows exactly the intended behaviour:

```text
trap   &0100: c9 8c f0 0f 48 ad 80 07 c9 a5 d0 03 20 81 07 68 4c 44 e5 60
helper &0780: 16 16 1e 18 18 19 16 19 19 19 19 18 19 16 19 19
```

The helper has been replaced by game data and the trap is intact, so the
signature check refused to call it and the load completed. That is the case
which defeated every earlier design.

Last of the Free stalls at about seven percent of its stream, and its dump
shows the opposite:

```text
trap   &0100: 01 25 b4 b1 02 01 25 b4 b1 07 01 25 b4 b0 0c 01 25 b4 b1 11
helper &0780: a5 08 78 48 a5 f4 8d a5 07 a9 0c 8d 05 fe ad a4
```

The helper is intact and the trap is gone, replaced by 6502 stack frames.
BYTEV still points at `&0100`, so every OSBYTE entered stack data. The stack
descended into the trap and destroyed it.

That is the risk recorded but not measured when the placement was chosen. Only
4.1% of the corpus loads cassette blocks across `&0100-&013F`, but that counts
tape loads and not run-time stack depth, and the WiCFS call chain is itself
deep enough to reach the bottom of the page.

The mechanism is therefore validated and the placement is not. The trap needs
about twenty bytes in the cassette page, which at about 3.4% of the corpus is
the only materially safer region, and that page has about nine free bytes
scattered across it. Repacking it means relocating the CFS filename buffer at
`&03D2-&03DF` and the chunk header state at `&03CB-&03D0`, which together need
slightly more room than the trap frees.

The candidate is preserved unbuilt under `rom-side/candidates/` with its
reasoning, because only its address is wrong.

One hazard found while implementing it is worth carrying forward. The repair
must never call OSBYTE. BYTEV is the trap which reaches the repair, so reading
the extended-vector table address with `OSBYTE &A8` from inside the repair
re-enters the trap and recurses without bound. The first build did exactly that
and destroyed BASIC's workspace, printing tokenised keywords as text. The table
address is now captured once at install time, where calling OSBYTE is safe.

### Quantified design: a signature-checked repair helper

The surviving design is measured rather than argued. The filing vectors point
at the MOS extended entries, so nothing load bearing sits in `&07xx`. The
extended-vector table is repaired by a helper which does live in `&07xx`, and
the BYTEV `*TAPE` trap in the cassette page verifies a signature in that helper
before calling it. A helper replaced by game code fails the check and is
skipped, rather than being executed.

Partitioning the 727 parseable corpus images by what they overwrite shows what
that buys:

| Group | Titles | Share | Outcome |
| --- | --- | --- | --- |
| Neither `&07xx` nor `&0D9F-&0DEF` | 531 | 73.0% | unaffected |
| `&07xx` only, helper destroyed, no repair needed | 49 | 6.7% | signature check skips the helper, load continues |
| `&0D9F-&0DEF` only, helper survives, repair runs | 104 | 14.3% | table repaired before the next filing call |
| Both | 43 | 5.9% | helper destroyed while repair is needed, still fails |

Repton is in the second group and Last of the Free in the third, so the design
satisfies both halves of the `WICFS-016` gate. The failure set falls from the
92 titles which can destroy today's gateway to the 43 which need both effects
at once.

This is an improvement rather than a cure. Five percent of the catalogue still
has no answer, and closing that needs a repair helper somewhere no loader
reaches, which low RAM does not offer.

The remaining obstacle is space for the trap. A signature check costs about
twelve bytes on top of the present eight, because the OSBYTE reason code in A
must be preserved across the comparison:

```text
.osb_s   CMP #&8C / BEQ osb_eat        \ existing *TAPE swallow
         PHA / LDA sig / CMP #&A5      \ verify the helper
         BNE skip / PLA / JMP helper   \ repair then chain to OSBYTE
.skip    PLA
.osb_j   JMP OSBYTE
.osb_eat RTS
```

Candidate homes for those twenty bytes, by how much of the corpus writes them:

| Region | Titles | Share |
| --- | --- | --- |
| `&0398-&03AB` cassette trap area | 25 | 3.4% |
| `&0100-&0113` deep stack | 30 | 4.1% |
| `&0700-&07FF` | 92 | 12.7% |

The cassette trap area is the best but `chain_exec` starts at `&03A0`, and the
page has only about nine free bytes, scattered. Repacking it means relocating
the CFS filename buffer at `&03D2-&03DF` and the chunk header state at
`&03CB-&03D0`, which together need more room than the trap frees.

The deep stack needs no repacking and only 4.1% of the corpus loads across it,
but that figure counts tape block loads and not run-time stack depth. Twenty
bytes at `&0100` are reached only by a stack around 236 bytes deep, which is
already pathological, but it introduces a failure mode that does not exist
today and would be hard to attribute.

Neither placement is adopted here. The choice is a judgement about which risk
to accept, not a measurement, and it should be made deliberately.

### The &07xx page cannot hold the gateway at any address

A third candidate shrank the RAM resident to a pure ROM pager of 63 bytes,
against the previous 103, by moving the extended-vector repair, its offset
tables and the dispatcher selection into ROM. The pager records which vector
was taken, pages the WiCFS ROM in, calls the repair, restores the caller's ROM
and tail-calls the MOS dispatcher. It never touches X or Y, so the caller's
registers reach the dispatcher intact. It was placed flush against the top of
the page at `romsel = &07C1`, on the general rule that the gateway should abut
`&0800` so the largest contiguous region below it stays available to loaders.

Last of the Free passes. Repton fails with `Bad program`. The host RAM dump
explains why:

```text
07A0  a5 71 c9 43 d0 ef 4c 00 41 43 43 43 43 43 43 43
07B0  43 43 43 43 43 43 43 43 43 43 43 43 43 43 43 43
07C0  43 43 43 43 43 43 43 43 43 43 43 43 43 43 43 43
07F0  43 43 43 43 43 43 43 43 43 43 43 43 43 43 43 43
```

Repton's second stage does not stop at `&07A8`. Its decryption loop ends there
but its filler continues to `&07FF`, so the whole page is consumed. The earlier
reading that a gateway above `&07A8` would clear it was wrong.

Structural analysis of the corpus agrees, and shows the top-of-page move bought
almost nothing:

| Region | Titles | Share |
| --- | --- | --- |
| `&0780-&07E6` previous gateway | 86 | 11.8% |
| `&07C1-&07FF` candidate gateway | 82 | 11.3% |
| `&0380-&0395` state cache | 26 | 3.6% |
| `&0398-&039F` notape trap | 25 | 3.4% |
| `&03A0-&03BC` chain_exec | 25 | 3.4% |

No address in `&07xx` is materially safer than any other, because the titles
which use the page use all of it. The gateway has to leave that page entirely,
and the cassette page is the only materially safer region in low RAM.

### What remains

Three candidates have now failed, and each failure removed a design:

1. Deleting the gateway fixes Repton and breaks Last of the Free.
2. Repairing once per OSBGET refill fixes Repton and breaks Last of the Free,
   because the corruption and the next filing call fall inside one window.
3. A smaller gateway higher in the page fixes Last of the Free and breaks
   Repton, because the whole page is consumed.

What survives is the design measured earlier. The filing vectors point at the
MOS extended entries, so nothing of ours sits in `&07xx` for a loader to
destroy, and the extended-vector table is repaired from the BYTEV `*TAPE` trap
at `notape`, which lives in the cassette page. `PI1MHZ_TUPLE_TRACE` measured one
OSBYTE call between the last corrupting write and the filing call, so the
repair has an opportunity to run.

The repair stub reachable from that trap needs roughly thirty bytes, and the
cassette page has about nine free. The 22-byte state cache at `&0380` is the
only eviction candidate, and it cannot move until `upbgetv` reloads on a failed
magic check rather than reporting an invalid state. That remains the next step,
and it is the only route not yet eliminated.

### Root divergence from the original cartridge

The original ElkWiFi 0.23 WiCFS streams, unpacks and runs UEFs on the real
cartridge, so its vector strategy is proven and worth comparing against.
`.build-original-control/wicfs.asm` shows it does not use the MOS
extended-vector table at all:

```text
romsel = &07A4

.s_filev   JSR romsel+(aupurs-s_filev)   \page in the WiCFS ROM
           JMP upfilev                   \and jump straight to the handler
.s_fscv    JSR romsel+(aupurs-s_filev)
           JMP upfscv
.s_bgetv   JSR romsel+(aupurs-s_filev)
           JMP upbgetv
```

FILEV, FINDV, BGETV and FSCV point at an eighty-byte RAM trampoline which pages
the ROM in directly and jumps to the handler. `aupurs` and `bupurs` select and
restore the ROM, and `x_filev`, `x_fscv` and `actioned` provide the return
paths. Nothing reads `&0D9F-&0DEF`.

That is why Last of the Free works on the cartridge. It overwrites the
extended-vector table while loading, and the original never looks at it. This
project rewired WiCFS onto the MOS extended vectors, which created the
dependency, and the 0.1.61 gateway was then added to repair the table the new
design had made load bearing. Both of the rejected candidates above are
attempts to fix a problem the original does not have.

The present gateway is 103 bytes because it performs that repair. Its RAM
footprint is therefore larger than the original's, and it sits lower in the
page: `&0780-&07E6` against the original's `&07A4-&07F3`.

### The decomposition this suggests

Only the paging trampoline has to live in RAM. Everything else can live in ROM,
where about 460 bytes are free. A trampoline which saves the caller's context,
pages the WiCFS ROM in, jumps to a ROM entry point and returns through a short
RAM epilogue to restore the previous ROM costs roughly sixty bytes, against the
current 103. The repair, the offset tables and the dispatcher selection all move
into ROM.

Sixty bytes placed flush against the top of the page occupy `&07C4-&07FF`. That
is a general placement rule, not a title-specific one: the gateway abuts the top
of the page so the largest possible contiguous region below it stays available
to loaders. It also clears Repton's second stage, which reaches `&07A8`.

Two routes are therefore open, and both keep the joint gate in `WICFS-016`:

1. Shrink the existing gateway to a paging trampoline and move the repair into
   ROM, keeping the extended-vector handlers as they are.
2. Return to the original's design, in which the trampoline jumps straight to
   the handlers and no repair exists because no table is consulted. This is the
   proven architecture but requires the handlers to stop reading the MOS
   extended-vector stack frame.

Neither is attempted here. Both change the entry and return path of every
filing vector, which is the code both rejected candidates got wrong.

### Rejected candidate: repair once per OSBGET refill

A candidate replaced the gateway with two changes and no new RAM. The filing
vectors kept the MOS extended entries, so a loader overwriting `&0700-&07FF`
became harmless, and `fillget` called the existing ROM routine
`wicfs_publish_extended_vectors` once per 256-byte refill to undo a loader's
damage to the table. The patch was 26 lines and cost nothing on the per-byte
path.

It fixes Repton and still fails Last of the Free. On the candidate ROM Repton
drains its stream to `LEN=&0010`, reaches its high-score screen and accepts
input, where 0.1.66 stalls at `LEN=&56E7`. Last of the Free returns to the
BASIC prompt exactly as it does with the gateway removed altogether.

Refill granularity is too coarse. The table is overwritten and the loader's next
filing call follows inside the same 256-byte window, so the repair never runs
between them. Any repair reached through the extended-vector table shares this
flaw: once all four tuples are dead there is no ROM entry point left to run the
repair from.

This narrows the design to mechanisms reachable without the table. BYTEV is the
only standard vector WiCFS owns that points directly at RAM it controls, at
`notape`. A signature-checked call from that trap to a repair helper needs about
twelve more bytes than the current eight-byte trap, and the cassette page has
about nine free. The chain is therefore: make `upbgetv` recover on a failed
magic check instead of reporting an invalid state, which allows the 22-byte
state cache to leave `&0380` for a loader-exposed page, which frees the space
the enlarged trap needs.

### Measured repair window and the state cache constraint

The proposed replacement makes the gateway advisory instead of load bearing:
the filing vectors would always point at the MOS extended entries, so a loader
which overwrites the gateway is harmless, and the extended-vector table would
be repaired from the BYTEV `*TAPE` trap in the cassette page behind a signature
check. That depends on a loader issuing OSBYTE between corrupting the table and
its next filing call, which was measured rather than assumed.

`PI1MHZ_TUPLE_TRACE` records every change to the four WiCFS tuples with the
OSBYTE count since the previous change. Running Last of the Free with the
gateway present shows the table being overwritten by the game's own file data,
one byte at a time, by the WiCFS copy loop in ROM bank 3, and then repaired:

```text
PC=A3B8 RB=3 OSBYTE_SINCE=0 FILE=FEEC:FE BGET=F7F0:F7 FIND=FFFF:FF FSC=FFFF:FF
PC=07B9 RB=B OSBYTE_SINCE=1 FILE=FEEC:FE BGET=F7F0:F7 FIND=FFFF:FF FSC=FF01:FF
PC=07BF RB=B OSBYTE_SINCE=0 FILE=FEEC:FE BGET=F7F0:F7 FIND=FFFF:FF FSC=A101:FF
PC=07C5 RB=B OSBYTE_SINCE=0 FILE=FEEC:FE BGET=F7F0:F7 FIND=FFFF:FF FSC=A101:03
```

Exactly one OSBYTE call falls between the last corrupting write and the
gateway's first repair write. The premise therefore holds for this title, but
with a margin of one call rather than a comfortable one, and a single title
cannot establish it for the catalogue.

Freeing space in the cassette page is the remaining obstacle. `&03D2-&03DF` is
the CFS filename buffer and `&03E0` begins the keyboard buffer, so only about
nine scattered bytes are free. The obvious eviction candidate is the 22-byte
WiCFS state cache at `&0380`, which `wicfs_state_load` already restores on
entry to `wicfs_install`, `upfilev`, `upfindv` and `upfscv` because
applications overwrite it. `upbgetv` is the exception: OSBGET is the per-byte
hot path, so it reads `wicfs_magic` and the stream cursor directly and treats a
failed magic check as an invalid state rather than reloading. Moving the cache
into a loader-exposed page would therefore corrupt the stream cursor mid-load
with no recovery.

The state cache can only move after `upbgetv` reloads on a failed magic check
instead of failing. That touches the hot path, so it must be measured against
the existing transfer-speed gate rather than assumed to be free.



The WiCFS filing vectors must be reachable after a cassette loader has rewritten
low memory. Two candidate mechanisms both fail, for opposite reasons, and this
study fixes the requirement for a third.

`*UEF LOAD REPTON` fails on 0.1.66. The instrumented Electron, Plus 1, Plus 2,
AP5, RH Plus, ADFS and read-only BeebSCSI profile with the Tube disabled stalls
on the title screen with `LEN=&56E7` of the stream unread. A dump of host RAM
at the stall shows `&0780` holding Repton's decryption loop:

```text
0780  A9 00 85 70 A9 30 85 71   LDA #0 / STA &70 / LDA #&30 / STA &71
0788  A0 00 B9 B4 43 49 43      LDY #0 / LDA &43B4,Y / EOR #&43
078F  99 B4 43 C8 D0 F5         STA &43B4,Y / INY / BNE
0795  B1 70 45 71 91 70         LDA (&70),Y / EOR &71 / STA (&70),Y
07A6  4C 00 41                  JMP &4100
```

Repton's second stage executes at `&0700` and spans `&0700-&07A8`, so it
replaces the 0.1.61 low-loader gateway while `FILEV=&0780`, `FINDV=&078E` and
`FSCV=&0795` still point into it. Every later filing call enters the decryptor.
That single defect produces both the stalled load and the filing system which
only a power cycle restores.

Removing the gateway fixes Repton and regresses Last of the Free. A candidate
ROM without it reaches sustained Repton gameplay and passes every acceptance
gate. On the same staged image and profile it returns Last of the Free to the
BASIC prompt, while 0.1.66 with the gateway reaches `HIT A KEY TO START`. Last
of the Free overwrites `&0D9F-&0DEF`, so it needs the extended-vector repair the
gateway performs. This is the `WICFS-007` failure returning.

Every other paired title was indifferent to the gateway. Thrust, Arcadians,
Repton 2, Bumble Bee, Mr Wiz and Repton Infinity produced identical stream
states and end screens in both builds; Repton 3 and Repton Around The World
reach their title menus without it. Repton Infinity stops at `Searching` in both
builds and is recorded separately as `WICFS-017`.

Structural analysis of the 727 parseable corpus images counts the titles whose
cassette blocks write each candidate location:

| Region | Titles | Share |
| --- | --- | --- |
| `&0380-&03FF` cassette workspace | 26 | 3.6% |
| `&0780-&07E6` current gateway | 86 | 11.8% |
| `&0D9F-&0DEF` MOS extended vectors | 147 | 20.2% |

Those counts are a lower bound because they follow direct block loads only.
Repton is not among the 86: it reaches `&0700` through a run-time copy. A
gateway location can therefore never be qualified by load addresses alone.

The requirement this fixes for the replacement:

- The repair mechanism must be kept. Last of the Free proves it is load
  bearing, and 147 corpus titles are in its class.
- It must not occupy `&0700-&07FF`. Repton proves that page is executed by real
  loaders, and 86 titles write it directly.
- The cassette workspace is the least contended location in low RAM, but the
  present gateway needs 103 bytes and only about 21 scattered bytes are free
  below the keyboard buffer at `&03E0`. The 22-byte WiCFS state cache at
  `&0380` must move before a gateway can live there.

No ROM change is promoted from this study. The gateway remains at `&0780` and
Repton remains an open failure until the relocation is implemented.

## 0.1.61 emulator evidence, 24 August 2026

The final ROM is version 0.1.61 with SHA-256
`239222cc53e973cf19e801b8bcfaab14ba0bf7196de79be5a8dce5d7e2967ee8`.
It was run in the Electron, Plus 1, Plus 2, AP5, RH Plus, ADFS and read-only
BeebSCSI profile with the photographed ROM order and Tube disabled. The live
MENU downloaded Last of the Free as 30,997 bytes with SHA-256
`c0fa7b26c8cf9d79adc82ed0f330ff5831562ab91609381219d1084eca7bab5b`.
The first machine-code file launched with `*RUN ""` and every subsequent
cassette file loaded. The strict runner then used the documented Space, X and
Return controls. It observed the reviewed title state, an input-correlated
transition into gameplay, subsequent movement, a live emulator process,
preserved BeebSCSI access, and no MOS error or known failure screen. The exact
final artifact therefore passed the complete Tube-off acceptance gate. Evidence
is retained in `/tmp/lotf-0161-final2/report.json` on the validation host.

The same final ROM also passed local `*UEF LOAD THRUST` from the staged ADFS
BeebSCSI image. This exercises the complementary tokenised-BASIC path: the
declared line boundary selected `CHAIN ""`, both reviewed gameplay inputs were
accepted, motion continued to the observation deadline, and the 6.6 MiB 1MHz
bus trace was valid. No MOS error or known failure screen appeared. Evidence is
retained in `/tmp/thrust-0161-classifier-final4/report.json` on the validation
host.

Physical Tube-off testing must still confirm that the earlier
`FREE 06 06FF Bad Program` failure and subsequent MENU hang are gone. Tube-on
behavior is not covered by the low-memory gateway and remains a separate gate.

## 0.1.62 repeated MENU candidate evidence, 24 August 2026

This section is historical evidence. Version 0.1.63 removes the MENU command
and its cache; none of these steps apply to the current ROM.

The 0.1.62 ROM and matched kernels add an explicit two-entry Pi RAM cache for
the MENU executable and TITLES catalogue. The default lifetime is one hour and
can be changed with `elkwifi_menu_cache_seconds` in `Pi1MHz.cfg`; zero disables
it. Only a complete successful HTTP body replaces a cached entry. Ordinary
`*WGET` and game UEF downloads bypass the cache.

The exact Electron, Plus 1, Plus 2, AP5, RH Plus, ADFS and read-only BeebSCSI
profile completed this sequence in one Elkulator process: `*MENU`, Arcadians
download, reviewed runnable state, gameplay input, Break, second `*MENU`,
second Arcadians download, reviewed runnable state and changing gameplay
frames. The mailbox trace recorded cache hits for both `/MENU` and `/TITLES`;
the game was downloaded normally. Evidence is retained in
`/tmp/arcadians-0162-repeat-menu/report.json` on the validation host. This is
emulator evidence only. The physical post-game MENU and ADFS recovery gates
remain open.

## Confirmed physical Tube-off milestone, 18 August 2026

The tested host ROM was
`build/pi1mhz-all/Pi1MHz/ElkWiFi.rom`, version 0.1.55, SHA-256
`ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb`.
The machine used the Electron, Plus 1, Plus 2, AP5, Pi1MHz, RAM expansion,
ADFS/BeebSCSI and MMFS installation with the Tube disabled.

With the full-stream candidate `kernel7.img`, HWDTEST, PING, NSLOOK and SSH
pass. `*MENU` completes, although WGET takes about two minutes per tested game.
Frak and Arcadians both load and play. Local `*UEF LOAD THRUST` also loads and
plays. MENU, WGET and UEF transfers remain painfully slow and require measured
optimisation.

ADFS returns after every tested Break, including after MENU games and local
Thrust. A subsequent `*UEF LOAD REPTON2` opens from ADFS, proving recovery
across consecutive WiCFS sessions, but Repton 2 still stalls after loading.
Bumble Bee completes. Plan B 2 reaches its application, but Break then loses
ADFS. Mr Wiz stops at `MRWIZ4 1710`. Repton reaches its title and then reports
`End of UEF`, `Searching`, `Loading` and `Cannot write!`. No Tube-enabled
result is inferred from this milestone.

NetTools preserves a suitable caller mode and falls back to MODE 4 only when
the measured host boundary is too low. The relocated ElkChat client restores
the full JIM selector before each page access, but its dual-ROM Elkulator
journey is not hardware-faithful. On the physical Tube-off machine User List
works, Public Chat displays Settings entries, and Private Chat exits with `Bad
Program`. Treat the emulator journey as a rejected false pass until it
reproduces these failures with the exact live SSD and host memory envelope.

An experimental snapshot of host workspace `&0E00-&1CFF` produced a positive
emulator differential for the ADFS loss, but peer review rejected it. Restoring
filing-system workspace from this ROM's reset service depends on ROM service
order and can overwrite a newer ADFS, DFS or MMFS owner. The experiment is not
part of the build. The replacement must recover only vector components still
owned by WiCFS and must pass the full Break, ADFS catalogue/read and second-load
sequence before physical Tube-off confirmation.

## Physical Tube-off milestone, 21 August 2026

The matched 0.1.58 ROM and Pi Zero 2 kernel were exercised on the Electron,
Plus 1, Plus 2, AP5, Pi1MHz, RAM expansion and ADFS/BeebSCSI configuration with
the Tube disabled. MENU launches Frak and Arcadians to playable gameplay. Plan
B also runs. Local `*UEF LOAD REPTON` now reaches gameplay, but has a long delay
before starting.

Two post-run recovery failures remain. After Frak, another `*MENU` hangs until
a cold start. After Plan B, ADFS remains unavailable until a cold start. These
are treated as evidence of one generic WiCFS vector, ownership or filing-system
teardown defect. No title-specific production workaround is permitted.

`*UEF LOAD MRWIZ` reports `UEF GZIP OK &3077 bytes in JIM` and then hangs. This
places the observed failure after Pi-side gzip normalization but before the
visible cassette-loading sequence, rather than at the final `MRWIZ4` block.
SSH works, but entering its password from MODE 0 incorrectly changes the
display to MODE 4. Tube-on behavior is not inferred from this milestone.

The 0.1.59 candidate captures the omitted pre-TAPE BYTEV pair alongside the
extended filing vectors and refuses a new MENU installation if the previous
WiCFS owner cannot be released cleanly. Its assembled launch gate passes with
delayed mailbox publication from 1 through 255 accesses and with a balanced
6502 stack. This is candidate evidence, not a replacement for repeating the
MENU, Break, ADFS read, second MENU and local UEF sequences on hardware.

The exact 0.1.59 ROM also reaches input-responsive Thrust gameplay in the
instrumented Electron, Plus 1, Plus 2, AP5, RH Plus and ADFS/BeebSCSI profile.
The run recorded 184,780 bus events, no Tube-register access, unchanged media
and configuration, and sustained gameplay motion after reviewed title-screen
input. This proves the emulated Tube-off path, not the pending physical or
Tube-enabled gates.

The extracted BeebSCSI corpus contains 11 structurally valid images:
Arcadians, Bumble Bee, Mr Wiz, Plan B, Plan B 2, Repton, Repton 2, Repton 3,
Repton Around the World, Repton Infinity and Thrust. Every image has complete
UEF chunks, continuous CFS block sequences and valid CRCs. Repton 3, Around
the World and Infinity exceed the legacy 64 KiB JIM capacity. The current
candidate supplies them through the generic incremental stream protocol.
Structural and emulator boundary tests pass; physical gameplay remains a
required acceptance result.

The SSH renderer now reads the active MOS text window and preserves a suitable
80-column mode through password authentication. Stock non-shadow MODE 0 cannot
contain the current SSH image because its `HIMEM=&3000`; the one entry-time
MODE 4 fallback is therefore expected on that memory layout.

## Pi target matrix

| Board | Image | Required result |
| --- | --- | --- |
| Pi Zero | `kernel.img` | Boot succeeds; `*WIFI ON` reports no WiFi device |
| Pi Zero W | `kernel.img` | WiFi on, scan, join, reconnect, WGET |
| Pi Zero 2 W | `kernel7.img` | WiFi on, scan, join, reconnect, WGET |
| Pi 3A+, 3B, 3B+ | `kernel7.img` | WiFi on, scan, join, reconnect, WGET |

Run the same command sequence on every wireless board. Record the exact board
revision because the bundle selects among CYW43430, CYW43436/43436s, and
CYW43455 firmware at runtime.

## Automated and emulator gate

- [x] Verify the ROM is exactly 16 KiB and matches the recorded SHA-256.
- [x] Run all Python contract tests.
- [x] Verify the universal ZIP and the ROM embedded within it.
- [x] Cold-boot the current ROM with the photographed ROM order and reach the
  BASIC prompt with the AP5 Tube disabled.
- [ ] Repeat the 0.1.55 cold boot with the AP5 Tube enabled. The run must
  contain the exact `AP5 Tube: external 3MHz 65C02 enabled` startup marker.
- [x] Boot ROM 0.1.55 with Electron OS, BASIC and ADFS in Elkulator. Confirm
  both ROM banners and a BASIC prompt.
- [x] Run `*UEF LOAD THRUST` with ROM 0.1.55, Tube disabled, the photographed
  ROM order and the real read-only BeebSCSI LUN. The complete three-file load
  reaches the instruction screen. Two separate Space inputs advance through
  the score screen into active gameplay. The automated runner now requires
  the full two-key sequence and uses a longer conservative timing window.
- [ ] Repeat the same 0.1.55 Thrust test with the Tube enabled. Earlier Tube-on
  results used 0.1.54 and must not sign off this binary.
- [ ] Run `*VERSION` in Elkulator and verify both copyright lines.
- [ ] Run `*WICFS`, then literal `*REWIND`, and verify an immediate prompt
  return. Elkulator's expansion ROM becomes unavailable after `*TAPE`, so this
  transition must be proved on AP5 hardware.
- [ ] Run uppercase `*HELP WIFI` and `*VERSION`; verify the ROM identifies as
  `1MHzWifi 0.1.55` before recording any further hardware test result.
- [ ] Boot the minimum supported layout in Elkulator: 32K Electron, Plus 1,
  AP5-constrained Pi1MHz mailbox, 1MHzWifi 0.1.55 and a user-supplied MMFS ROM.
  No Plus 2, sideways RAM, ADFS or Tube is present.
  Mount a FAT32 Pi SD-card image containing `BEEB.MMB`, select fixture disc
  507, catalogue `DESK`, run `*UEF LOAD DESK`, and satisfy an application-state
  reference rather than generic screen motion.
- [x] Run `*IFCFG` with no services-mailbox device. Confirm a bounded error and no rows of spaces.
- [x] Add a Pi1MHz services-mailbox and JIM bridge to Elkulator and run live
  Internet command tests.

Existing captures are stored under `tests/elkulator/screenshots/`. They are
reference material, not proof for a later binary. The
maintained adapter models the Pi1MHz mailbox, JIM, AP5 address decoder, Tube
ULA and an external 3 MHz 65C02. A configured Tube starts during cold boot,
matching PiTubeDirect. Earlier catalogue runs established identical UEF bytes
between Tube states, but their generic framebuffer comparisons do not meet the
current gameplay acceptance rule. Physical hardware remains the final gate.

## Filing-system matrix

Use the same ROM and matched Pi kernel for every row. Changing the filing
system must not require a 1MHzWifi ROM rebuild, a different command path, or a
fixed sideways-bank allocation. For every source filing system, run `*UEF
LOAD` on the same raw UEF and compressed Desk Diary fixture, reach the
application rather than the BASIC prompt, then reselect and catalogue the
source filing system after WiCFS finishes or after Break.

Repeat the ROM-level smoke test with 1MHzWifi in at least three materially
different banks, including one below bank 8 and one above it. The automated
OSWORD harness exercises all sixteen MOS-supplied ROM numbers. Full emulator
runs select the bank with `--wifi-rom-slot`; relocate any displaced profile ROM
explicitly. Sideways RAM may also occupy any bank. `*WGET -S` must succeed for
each writable bank under test and reject a ROM bank without damaging it.

| Source filing system | Required setup | Entry and recovery checks | Status |
| --- | --- | --- | --- |
| BeebSCSI ADFS | Acorn ADFS 1.00, AP5 and the existing `/BeebSCSI0/scsi0.dat` | `*ADFS`, `*CAT`, load, Break, `*ADFS`, `*CAT` | Physical gate |
| Normal ADFS | Plus 3 or equivalent 1770 ADFS media | `*ADFS`, `*CAT`, load, Break, `*ADFS`, `*CAT` | Pending with a MOS-valid writable fixture |
| DFS | 1770 DFS media containing the fixture | `*DISC`, `*.` (`@.` in Elkulator), load, Break, `*DISC`, `*.` | Desk Diary launch passed; recovery pending |
| MMFS | Electron MMFS in any suitable ROM or sideways-RAM bank with its normal SD/MMB backing | select image, `*CAT`, load, Break, reselect image, `*CAT` | Minimum-profile emulator launch passed; recovery and physical runs pending |
| TAPE/CFS | Native cassette UEF selected before 1MHzWifi use | `*TAPE`, catalogue/load, MENU or UEF launch, Break, `*TAPE` | Pending exact-profile rerun |

The ROM-side import is deliberately filing-system neutral. It opens the
caller's filename with MOS `OSFIND`, consumes it with `OSBGET`, and reselects
the Pi1MHz JIM window after every byte. Tests must nevertheless exercise each
row because ADFS, DFS and MMFS have different vector owners and workspace
usage. A DFS pass is not evidence for either ADFS variant or MMFS.

The first normal-ADFS fixture created with the legacy host `fstool` is not
valid acceptance evidence. Acorn ADFS itself reports `Bad FS map` from a plain
`*TYPE DESK`, before 1MHzWifi is entered. Keep that image out of regression
results and use media which passes a native ADFS open/read check first.

## Supported configuration profiles

The minimum release profile is a 32K Electron with a Plus 1, AP5, Pi1MHz on
the 1MHz bus, 1MHzWifi and a user-supplied compatible filing-system ROM. This
profile must not require a Plus 2, sideways RAM, ADFS or Tube. Filing-system
ROMs are test inputs and are not distributed by this project.

The stress profile reproduces the photographed machine: Plus 2, Plus 1, AP5,
Pi1MHz, BeebSCSI ADFS, MMFS, 32K sideways RAM and an optional Tube. Its ROM
order is useful regression evidence but is not an ABI. 1MHzWifi must discover
and coexist with the installed filing systems and expansion ROMs regardless
of their bank numbers.

## Cold boot and bus gate

- [ ] Before running any WiFi or MENU command, run `*ADFS` and `*CAT`. Confirm
  the expected BeebSCSI volume mounts from `/BeebSCSI0/scsi0.dat`.
- [ ] After a failed or successful MENU/WiCFS launch, run `*ADFS` and `*CAT`
  again. Confirm ADFS reclaims the filing-system vectors without resetting.
- [ ] Repeat the same pre-flight and recovery sequence with `*DISC` and `*.`.
  Confirm DFS remains available after Break and after a completed WiCFS load.
- [ ] Boot the current ROM with the Pi powered down. Confirm the BASIC prompt appears without a hang or `Buffer full`.
- [ ] Boot the current matched kernel and ROM. Confirm the BASIC prompt appears before a WiFi command is issued.
- [ ] Run `*HELP WIFI`; confirm the current command list and no screen-row corruption.
- [ ] Run `*WIFI ON`; confirm a WiFi-capable Pi reports ready and a Pi without WiFi reports `Device not found`.
- [ ] Run `*WIFI ON` twice; confirm both calls complete and the second call does not lose the service registration.
- [ ] With the Tube disabled, confirm the WiFi banner consumes one line and
  does not add a blank line.
- [ ] With the Tube enabled, confirm there is no blank line between the WiFi
  and Tube banners. Their relative order is determined by MOS ROM service
  order.
- [ ] Run `*LAP`; confirm the rows describe nearby access points rather than the configured SSID alone.
- [ ] Capture `nRST`, `PHI2`, `R/W`, address, data, and buffer enable for `&FCA6-&FCAA`.
- [ ] Compare setup and hold timing with an unmodified Pi1MHz V1.30-descended build.
- [ ] Run storage, AUN, audio, and ElkWiFi services concurrently; confirm command ranges and poll callbacks do not collide.

Expected error meanings:

| Error | Interpretation |
| --- | --- |
| `Device not found` before dispatch | Services mailbox is absent or not forwarded |
| `Device not found` after dispatch | Pi reports no usable WiFi hardware |
| `Not implemented` | Service range or requested function is unsupported |
| `No response from device` | A claimed request remained busy past its deadline |

## Association and persistence gate

- [ ] With no saved profile, confirm `*JOIN ?` reports `No AP`.
- [ ] Join an automatic WPA/WPA2 access point and wait for DHCP.
- [ ] Confirm `*JOIN ?` reports the associated SSID.
- [ ] Confirm `*IFCFG` reports the assigned IPv4 address and real station MAC.
- [ ] Run `*ONLINE` while DHCP is pending and confirm `OFFLINE CONNECTING`.
- [ ] Run `*ONLINE` after DHCP and confirm `ONLINE` followed by the assigned IPv4 address.
- [ ] Power-cycle the Pi and Acorn; confirm the saved profile associates automatically.
- [ ] Run `*LEAVE`; confirm disassociation and no automatic rejoin until another `*JOIN`.
- [ ] Immediately run `*IFCFG` after `*LEAVE`; confirm a zero IP address, then
  run `*ONLINE` and confirm the interface is offline.
- [ ] Run `*WIFI OFF`; confirm `WIFI OFF` and `OK`, then confirm `*IFCFG`
  reports a zero IP address and `*ONLINE` reports `OFFLINE WIFI OFF`.
- [ ] Run `*ONLINE` after `*WIFI OFF` and confirm `OFFLINE WIFI OFF`.
- [ ] Run `*WIFI ON`; confirm `WLC_UP` succeeds and the saved profile starts
  associating again without restarting the Pi.
- [ ] Test forced WPA, forced WPA2, WEP40, WEP104, and open profiles on isolated test access points.
- [ ] Test invalid keys, association rejection, DHCP failure, and access-point loss.
- [ ] Test SSIDs and passwords containing spaces, commas, quotes, and boundary lengths.
- [ ] Confirm configuration and profile precedence matches the documented order.

## HTTP gate

- [ ] Confirm `*MENU` and `*MENUSRC` are absent from `*HELP WIFI` and return
  `Bad command` rather than entering downloaded code.
- [ ] Run `*NSLOOK` against a hostname and confirm the printed IPv4 address.
- [ ] Cancel WGET with Escape during DNS, connect, empty wait, and body transfer.
- [ ] Run `*WGET <url> <filename>` under ADFS, DFS and MMFS. Verify the file's
  exact byte count and hash, and confirm the filing system remains selected.
- [ ] Test text modes, maximum transfer size, and a 30-minute repeated-transfer loop.
- [ ] Test redirects, chunked bodies, content length, and connection-close bodies; record unsupported cases.

## FTP and SFTP gate

- [ ] Run `*FTP ftp://host[:port]` against a controlled FTP server. Exercise
  USER, PASS, PWD, CD, DIR, LS, ASCII, BINARY, GET, PUT, DELETE, MKDIR,
  RMDIR and QUIT.
- [ ] Compare uploaded and downloaded binary files byte for byte under ADFS,
  DFS and MMFS. Confirm failed remote opens do not truncate local files.
- [ ] Press Escape during DNS, control connect, passive data connect, download
  and upload. Every cancellation must return to the MOS prompt and leave the
  next FTP session usable.
- [ ] Run `*SFTP user@host [port]` from the released NetTools SSD. Exercise
  host-key acceptance, key authentication, password fallback, PWD, CD, DIR,
  LS, GET, PUT, DELETE, MKDIR, RMDIR and QUIT.
- [ ] Repeat FTP and SFTP with the Tube absent, fitted but unused, and active.
  Trace `&FEE0-&FEFF`; neither client may address or claim the Tube.

## WiCFS and JIM gate

### Local physical-hardware evidence

The ignored `samples/` directory is retained as local test evidence. It is not
build output and must not be removed by repository cleanup. The current files
record tests on the Electron installation with Plus 2, Plus 1, AP5, a 6502
Tube, Pi1MHz on the 1MHz bus, ADFS, MMFS/SWRAM and BeebSCSI support present.

The 7 August 2026 photographs record these ROM 0.1.22 results:

- `20260807_180750.jpg`: raw Zalaga downloads as `&7462` bytes, WiCFS starts,
  `CHAIN ""` loads `ZALAGA 05 05EE`, then returns to the Tube BASIC prompt.
- `20260807_180801.jpg`: `*ROMS` and `*VERSION` identify 1MHzWifi 0.1.22,
  Acorn Tube 6502 64K, Acorn ADFS, RH Plus 1 and BASIC. The Pi reports kernel
  `V1.30-80-g8468a38-dirty.5cd08bdf`.
- `20260807_181024.jpg`: `*ONLINE` succeeds, but the native `*SSH` capability
  probe returns local timeout `&2A`.

`samples/sdcard.zip` is the complete FAT boot-partition capture from that
test. Its ROM and both kernels match the then-current 0.1.22 release hashes,
so these failures are not stale-deployment results. It also preserves the
active AP5, Services, BeebSCSI and WiFi configuration for comparison.

`Acornsoft Desk Diary (198x)(Acornsoft).uef` is the local compressed-UEF test
fixture used by the normalisation test. It remains ignored because it is
third-party test media. These files are observations from physical hardware,
not emulator acceptance evidence.

Map a candidate image before testing it:

```sh
python3 scripts/uef_map.py "samples/Thrust (1986)(Superior Software).uef"
python3 scripts/uef_map.py --json "samples/Acornsoft Desk Diary (198x)(Acornsoft).uef"
```

The mapper validates every chunk boundary and reports the complete decoded
length separately from the former firmware trim point. The normal candidate
must use the complete length. `elkwifi_uef_trim_tail=1` exists only to reproduce
the earlier behaviour in a controlled A/B/C hardware test.

HWDTEST D4 is observational with respect to the WiCFS persistence record. Its
write/read probe is at `&FFEE00`; it reads but never writes
`&FFEF00-&FFEF19`. Capture D4 after cold boot, after WiCFS installation, after
the last cassette file, immediately after Break, after `*ADFS`, and after a
known ADFS file read. Compare BYTEV, FILEV, BGETV, FINDV, FSCV, the four
extended handler/ROM-owner tuples and all `WSTATE` bytes. Running HWDTEST D2 or
D3 is not valid lifecycle evidence because those builds do not provide the
complete vector and state report. D2 additionally wrote over the WiCFS record.

On 18 August 2026 the rebuilt behavioural model completed the Tube-off Thrust
journey in full-stream mode with the photographed ROM order and read-only
BeebSCSI LUN. It matched the reviewed title and gameplay frames after both
input events, retained sustained motion, showed no failure frame or MOS error,
and remained live at the deadline. The bus trace contained 248,956 relevant
events, 70,742 mapped JIM accesses, 135,152 `&FCFF` writes and no Tube-register
access. This validates the software-visible sequence and the candidate's full
UEF length in the emulator. It does not validate AP5 electrical timing, Pi FIQ
latency, SDIO scheduling or contention on physical hardware.

`samples/RHPLUS133.rom` is the exact RH Plus 1.33 dump from the test Electron.
Its SHA-256 is
`cda520a110b160af2c750b2d28c84353ad2c3ede15b4821cf96452ee4dc3b5f8`.
Exact-profile emulator runs load it in bank C. The earlier `ap6v133t.rom`
substitute is not acceptance evidence for this AP5 configuration.

Earlier releases corrected the AP5 selector and WiCFS state corruption.
Versions 0.1.24 and 0.1.25 attempted Tube transfers, which was the wrong
architecture. Version 0.1.55 contains no Tube transfer path and preserves the
stock cassette sequence. The private host launch enters Electron BASIC and
queues `PAGE=&E00` before WiCFS so a Tube-active cold BASIC does not retain its
`&23xx` program workspace. Physical Tube-enabled gameplay remains the
acceptance gate.

The maintained Elkulator Tube model now provides a repeatable diagnostic gate.
With the photographed ROM order, live Pi1MHz Internet backend, ROM 0.1.54 and
the Acorn 1.20 Tube boot ROM, cold boot starts `Acorn TUBE 6502 64K`
automatically. `*MENU`, entered using `@` for the emulator's `*` key mapping,
waits for the traced `TITLES` close before selecting a title. Fresh FrakV2
runs complete the stock `*TAPE`, `*WICFS`, `*REWIND`, `CHAIN ""` sequence and
reach moving gameplay in both Tube states. The current batch runner applies
the same menu selection and WiCFS path to arbitrary sorted catalogue ranges.
An earlier first ten-entry 0.1.37 run
produced identical UEF hashes in every Tube-on/off pair. The experimental
0.1.38 MOS-managed handoff returned to the prompt and was rejected. ROM 0.1.40
restored the proven launch path and reached Frak, Zalaga and Arcadians gameplay
Tube off and Tube on. Last of the Free remained a `Bad program` failure in both
modes. ROM 0.1.54 retains the host-only architecture and current FrakV2
evidence. It does not copy a UEF
or game into parasite memory, issue `TUBE OFF`, reset the fitted Tube, or access
a Tube register.

- [ ] Confirm `Pi1MHz.cfg` contains active `Rampage_addr=0xFD`. Boot with ADFS,
  DFS, MMFS/SWRAM and other JIM users present; verify each can reselect its own
  address after 1MHzWifi commands.
- [ ] Download a known UEF with `*WGET -U` and verify the stored length metadata.
- [ ] Run `*WICFS`, `*CAT`, `*LOAD`, and `*RUN` against that UEF. Confirm the
  selected program reaches its execution address rather than returning to the
  BASIC prompt after the download.
- [ ] Retest Zalaga, Arcadians, Last of the Free, E-Type, Frak, Chuckie Egg
  and DeskDiary with ROM 0.1.55 on
  the physical Electron and AP5. Earlier physical builds failed on Zalaga and
  DeskDiary. Zalaga and Arcadians reach gameplay through the live Elkulator
  bridge without a Tube.
  Confirm every requested cassette file stops on its own final CFS block.
  Earlier ROMs called the loader compatibility helper before branching on
  that block's last-block bit. The helper changed the processor flags, so an
  OSFILE load could consume later files and finally report `End of UEF` or an
  invalid chunk type. Version 0.1.46 branches on the bit first, preserves the
  OSFILE control-block pointer on the active 6502 stack, returns catalogue
  metadata through that block, and does not touch the `&03E0-&03FF` keyboard
  command queue.
- [ ] After a title finishes or an explicit catalogue operation reaches the
  physical end of its UEF, press Break and
  confirm `*ADFS` is immediately available. Repeat with `*DISC`, Ctrl-Break
  and with a Tube enabled. MOS must rebuild the vectors and 1MHzWifi must not
  restore stale cassette predecessors over the filing system selected during
  the reset service pass.
- [ ] Run `*MENU`, press `L` for Zalaga, and confirm the private host entry
  queues the original `*REWIND` followed by `CHAIN ""` after the download. The
  ROM must not substitute `*RUN`, `*/`, or another launch command.
- [x] In the live Elkulator bridge, execute the complete published Zalaga UEF
  through WiCFS and confirm the title reaches gameplay. This covers the
  second-stage vector-reset signature and subsequent `Scrunch` and
  `ElkZalaga3` files without changing the stock launch commands.
- [x] Trace the initial Zalaga file under the photographed non-Tube ROM order.
  Confirm its relocated entry at `&13DA` matches the UEF byte for byte, issues
  the original `/` OSCLI shorthand, and reaches WiCFS FSCV reason 2 after the
  reason-8 notification is handled locally.
- [x] Select Arcadians as menu entry `O`; confirm the live 24,946-byte
  `Acornsoft/Arcadians_E.uef` download reaches its runnable game screen.
- [x] Resolve the Arcadians Tube-off final-file transition. The full-stream
  physical candidate passes `4C 4C49` and reaches gameplay. Tube-on remains a
  separate coexistence gate. Do not add a title-specific loader path.
- [ ] Reproduce and trace the exact BeebSCSI Mr Wiz and Repton failures. The
  source volume validates, gzip decoding succeeds, every UEF chunk is complete,
  and every CFS header/data CRC and block sequence is valid. Mr Wiz includes a
  valid final `MRWIZ4` block. Native cassette loading of the exact Repton image
  enters the game after Space, while WiCFS corrupts the title and hardware
  reports an end-of-stream/search/load/write sequence. Trace the first divergent
  OSFIND, FILEV or FSCV request against original ElkWiFi behaviour. Review found
  that the earlier host-only patch rejected OSFIND `&C0`, whereas original
  ElkWiFi accepts OPENUP through its input-capable path. The 0.1.58 candidate
  ROM restores that behavior and makes Service 1 passive after BYTEV release.
  It reaches the Repton title in the exact emulator profile, but still does not
  enter gameplay. Do not sign off the UEF path until the emulator reproduces
  and passes the photographed transition.
- [x] Put the gzip DeskDiary sample on an emulated DFS disc as `DESK`, run
  `*UEF LOAD DESK`, confirm normalization from 10,631 to 20,580 bytes, and
  reach the application's `ADDRESS`/`PLANNER` menu without another command.
- [ ] With the exact RH Plus dump and Tube enabled, select Planner. Both the
  WiCFS stream and Elkulator's untouched native cassette path currently stop
  after the final `23 2301` block. Treat this as a Tube-model or application
  compatibility investigation, not evidence of missing WiCFS bytes.
- [ ] Put the 29,794-byte Zalaga UEF on a DFS image, run
  `*UEF LOAD ZALAGA`, verify `UEF RAW OK &7462 bytes in JIM`, and confirm the
  game reaches its title screen through the two-stage queued WiCFS launch with
  no additional keystrokes.
- [ ] Repeat `*UEF LOAD` from hardware DFS, the ADFS hard disc and MMFS, including
  a path-qualified filename, Escape, missing file, empty file, an exact
  `&FF00` boundary, and a multi-window image larger than `&FFFE` bytes.
- [x] Differentially test the exact staged Thrust image through WiCFS and
  Elkulator's untouched native cassette path under the same AP5, ADFS and
  BeebSCSI profile. Both paths reach input-responsive gameplay. After a soft
  Break, both paths report `Bad command` for `*ADFS`. This is not a WiCFS
  divergence and must not be hidden with title-specific ROM logic. Confirm the
  same native-cassette behavior on physical hardware before classifying it as
  an AP5 reset-model issue or software behavior. A power-on recovery remains a
  separate hardware expectation.
- [ ] Run `*UEF LOAD DESKDIARY` with the 20,580-byte expanded image. Confirm
  the final zero-byte `V1` CFS marker completes without `Unexpected EOF` and
  the application continues through its intended launch path on physical
  hardware. This path has passed under Elkulator from an emulated DFS disc.
- [ ] Repeat the local import with raw UEF, gzip UEF, a single-entry ZIP
  containing raw UEF, and a ZIP containing gzip UEF. Verify the reported
  format and expanded byte count, then test bad CRC, truncated deflate data,
  multiple-entry ZIP, an image above the 16 MiB stream limit, and expanded
  images spanning one, two and three public windows.
- [x] Run the first ten published catalogue entries through the automated
  Tube-on/off differential. Confirm identical UEF byte counts and SHA-256
  values for all pairs. Retain strict screen mismatches for visual review.
- [ ] Test sequential open/read, EOF, rewind, Escape, malformed UEF, and recovery.
- [ ] While associated, press BREAK and time `*ONLINE`. Confirm the preserved
  Pi-side association is available within seconds and no full rejoin starts.
- [ ] On a direct BBC-family connection, confirm `*PRD 0 0` and `*PRD 0 1`
  inspect the two defined JIM windows and restore selector `00:00`.
- [ ] On Electron AP5, confirm `*PRD 0 0` works and `*PRD 0 1` reports
  `Unknown option`; AP5 does not forward the high JIM selectors.
- [ ] Test `*WGET -S` with valid sideways RAM and with no writable sideways RAM.
- [ ] Run WiCFS and another Pi1MHz JIM-using service concurrently; check for scratch-page collision.

## Ping and time gate

- [ ] Ping an IP literal and a DNS hostname.
- [ ] Test unreachable host, DNS failure, ICMP error, timeout, and repeated commands.
- [ ] Press Escape during DNS, ICMP reply wait, and the delay between PING
  attempts. Confirm the command returns promptly and the next PING succeeds.
- [ ] Run `*DATE` and `*TIME`; compare with a trusted clock and configured UTC offset.
- [ ] Test DNS and NTP failures, repeated queries, invalid server packets, and reset during an outstanding request.

## Tube coexistence gate

- [ ] Run `*HELP WIFI`, `*PING`, `*NSLOOK`, `*WGET`, and `*WICFS` from the I/O processor.
- [ ] Repeat applicable commands while each supported Tube is fitted and active.
  Any Pi, network or JIM traffic must remain on the 1MHz bus. Tube traffic is
  permitted only for application activity outside 1MHzWifi.
- [ ] Trace calls and confirm only the I/O processor accesses `&FCxx` and `&FDxx`.
- [ ] Exercise every pointer-bearing OSWORD `&65` call with buffers in parasite memory.
- [ ] Trace a complete UEF load. Confirm 1MHzWifi never accesses Tube
  registers, claims a Tube channel or disables the Tube. Confirm the loader
  executes in Electron host memory and a Tube-aware game can still use the
  fitted processor itself.
- [ ] Confirm no WiCFS vector code occupies Tube workspace `&0400-&07FF` and no
  parasite pointer is passed to JIM or the 1MHz-bus Pi service.
- [ ] Run the current 0.1.59 `*UEF LOAD THRUST` candidate with Tube disabled
  and enabled. Confirm both reach live gameplay and the Tube-enabled path does
  not use Tube registers or a parasite destination. Earlier candidates reached
  gameplay in both profiles, but that evidence does not promote 0.1.59.

## OSWORD application compatibility gate

- [x] Assemble the unchanged original-ElkWiFi ElkChat client and pass all 16
  deterministic bridge fixture tests. This checks the client and reference
  protocol fixtures, but does not replace entry through the Pi ROM's OSWORD
  service handler.
- [x] Enter 1MHzWifi through MOS service reason 8 and execute ElkChat-shaped
  OSWORD `&65` calls for functions 9, 18, 4, 8, 13 and 14. The executable
  test forces zero and partial TCP sends, waits through empty receive gaps and
  receives a response spanning several public JIM pages. It also checks
  bounded functions 0, 3, 5 and 24. This test uses
  ElkChat's original ABI and does not call private ROM labels.
- [ ] Run ElkChat's `ELKNET` diagnostic with `*RUN ELKNET` against the original
  ElkWiFi 0.23 ROM. Record function 18 IFCFG, function 4 JOIN query and
  function 8 TCP-open responses.
- [ ] Repeat the unchanged original-ElkWiFi ElkChat path with the 1MHzWifi
  0.1.55 hardware-test ROM
  and the kernel revision reported by the bundled `*VERSION`. None of the
  calls may block or
  raise `Not implemented`.
- [ ] Call function 9 with a CR-terminated `0` parameter before function 8.
  Confirm it returns `OK`, reports response length `&0004`, and leaves JIM
  selected at `00:00:00` with the single connection available.
- [ ] Send an HTTP request with function 13, receive through functions 13/20,
  and close through function 14. Confirm the Chat64 response is present in JIM
  `00:00:page` across at least 16 pages and not in a DFS/MMFS-selected bank.
- [ ] Repeat with AP5, DFS and MMFS active, then with a Tube fitted. The Pi transport
  must remain the 1MHz bus and the application must not depend on the Tube.

## Reset and fault-recovery gate

- [ ] Reset during scan, association, DHCP, DNS, ICMP, NTP, connect, send, receive, and filesystem writes.
- [ ] After each reset, run `*WIFI ON` and one network command without rebooting the Pi.
- [ ] Repeat `*WIFI OFF`/`*WIFI ON` cycles before, during and after association.
- [ ] Confirm `*WIFI SR` and `*WIFI HR` return the documented explicit
  `Not implemented` error without changing radio state.
- [ ] Confirm late callbacks cannot complete a newer request.

## Secure transport gate

Managed SSH is implemented in the Pi firmware and native `SSH` host tool.
HTTPS and TLS are not implemented.

The 0.1.44 physical diagnostic trace failed before useful Pi progress was
visible: NSLOOK printed `>2D S00 <2A`, and SSH printed `>5E S5E <2A`. Pi 3A+
and Zero 2 W tests failed consistently, while a second Zero 2 W produced
intermittent NSLOOK success. This was not a board-specific protocol difference.
The diagnostic printed through MOS after selecting the global FCA6-FCA9 cursor,
so another active ROM could redirect the pending write. In 0.1.46 the trace is
emitted before selection, cursor ownership is interrupt-safe and the emulator
fixture redirects the cursor on every MOS output call to enforce the rule.

The subsequent 0.1.45 hardware run produced the same trace, corrupted
`*VERSION` immediately after the two ROM-local lines and blocked ElkChat's
public OSWORD calls. The shared failure identified the Pi bus publication path.
The pinned upstream tree contained a shadow-based optimisation for
`Pi1MHz_MemoryWrite` whose own change record said it had not been exercised
against a live Beeb read. Host/VPU writes are not guaranteed to update the ARM
shadow first, so publishing one byte could restore a stale value into the
adjacent FRED register in the same VPU word. In the Services pair this is
`&FCA8/&FCA9`, directly explaining a response byte being observed as the cursor
diagnostic. Version 0.1.46 restores the authoritative VPU-window
read/modify/write. The automated model starts with a deliberately stale ARM
shadow and verifies that the live adjacent selector survives publication.

The 14 August physical `*HWDTEST` capture then measured a separate emulator
discrepancy. The Electron reported `00 F0 FF 5E`, the sixteen-byte sequential
JIM test failed, and secure capability discovery timed out with `&2A`. The
emulator had completed every FCA9 auto-increment synchronously and therefore
reported `01 F0 FF 5E`. Pi1MHz performs that update from an asynchronous FIQ
callback, so a following host access cannot assume that the read-back cursor
has advanced. Version 0.1.49 makes every ROM and NetTools byte transfer
explicitly select its complete software-shadowed 24-bit address and then waits
for the bounded FCA9 callback acknowledgement before selecting the following address.
The executable tests run NSLOOK and a complete managed SSH session with
hardware auto-increment disabled, ensuring that the emulator no longer
conceals this dependency.

The Tube-off hardware capture also reported OSHWM `&1D00` while the 0.1.47
NetTools image was loaded at `&1900`. Its later text corruption is therefore
explained by filing-system workspace overlap, independently of the mailbox
failure. Version 0.1.49 loads at `&1D00` and every application checks both
OSHWM and HIMEM before continuing. This protects the measured configuration;
a future two-stage relocatable loader remains required for arbitrary workspace
layouts because a program cannot query MOS until after its initial load.

The first 0.1.48 hardware run refused HWDTEST with the generic memory-envelope
message and then produced only `r` for the Pi line of `*VERSION`. The latter is
ROM code and cannot be caused by the NetTools load address. Inspection found
that 0.1.48 acknowledged asynchronous FCA9 cursor updates in NetTools only,
while the ROM's ElkWiFi response copier still consumed consecutive FCA9 bytes
without waiting. Version 0.1.49 applies the same bounded acknowledgement to
the ROM command, OSWORD, WGET and response-copy paths. The HWDTEST refusal now
prints the actual OSHWM, HIMEM and executable range.

The matched 0.1.49 physical run then provided the missing distinction. With
the Tube disabled, HWDTEST passed, TELNET worked and NSLOOK resolved correctly,
but SSH reported `&27`, `*VERSION` still printed only `r` for its Pi line and
ElkChat blocked in User List and chat operations. The ROM had waited for the
FCA9 auto-increment callback after each data access, but it consumed FCA9
immediately after writing FCA6-FCA8. Pi1MHz publishes the newly selected data
byte from that selector callback too. A fast ROM or assembled NetTools client
could therefore consume stale FCA9 data before the selector callback ran.
The rejected 0.1.51 candidate added a bounded settling interval to every ROM
selector and data transaction. Although it passed the delayed-selector model,
it regressed MENU and local UEF loading on physical hardware. The current WGET
path still contains bounded mailbox and JIM settling and must not be described
as byte-identical to 0.1.49. The conservative emulator measures about 42
seconds for the 11,498-byte TITLES transfer. NetTools retains a CPU-local
bounded delay in its own mailbox transport. It
must not read FRED or JIM while waiting because another bus transaction can
replace the pending one-slot FIQ event. Automated tests
complete IFCFG, delayed `*VERSION`, SSH capability discovery, NSLOOK and a
managed SSH session, but the response timing changes still require hardware
validation.

Before repeating application tests, run the same released diagnostic binary in
Elkulator and on the physical machine:

```text
*HWDTEST
```

Capture each of the three screens through the final `*VERSION` output. The raw
auto-increment line is diagnostic rather than a pass gate: the current hardware
observation is `00 F0 FF 5E FAIL`, while the synchronous emulator reports
`01 F0 FF 5E PASS`. The release gate is `FCA9 callback ACK: PASS`,
`Addressed JIM block: PASS`, `Secure CAPS result=&00`, capability feature bits
`&03` or greater, and provider readiness byte `&01`. Version 0.1.55 correctly
reports FAIL for the physical `CAPS 1-5: 01 01 01 ...` result because managed
SSH is not ready. Compare the machine
byte, Tube byte, OSHWM, MEMTOP,
FILEV, FSCV, WORDV and complete ROM order between both runs. This separates a
MOS or ROM-layout mismatch from an `&FCA6-&FCAA` bus publication failure without
modifying ADFS, MMFS or DFS data and without touching Tube state.

- [ ] With the packaged 0.1.55 kernel and matching SSD, run `*NSLOOK example.com` with
  Tube disabled and enabled. It must print an IPv4 address, return normally,
  and never report `&2A` or `Bad program`.
- [ ] Run `*SSH user@host` with Tube disabled and enabled. Capability command
  94 must return immediately, then the managed wolfSSH session must reach host
  key verification or authentication without `&2A`.
- [ ] If the debug SSD is used, confirm NSLOOK starts `>2D <00` and SSH starts
  `>5E <00`. `S00` or `S5E` followed by `<2A` is still a failed dispatch, not
  an acceptable retry.
- [ ] Run ElkChat Network Status immediately after cold boot and after BREAK.
  OSWORD function 18 must return STAIP and STAMAC without blocking. Repeat with
  MMFS and ADFS active to exercise interrupt-side JIM cursor contention.
- [ ] Exercise ElkChat User List, Private Chat and Public Chat from the same
  SWRAM build. Verify each public response remains intact while MMFS or ADFS
  also uses JIM. Version 0.1.46 reselects the AP5 page for every response byte
  with interrupts masked and does not cache machine type in volatile heap.
  The physical result is currently User List working, Settings text inside
  Public Chat, and `Bad Program` from Private Chat. The existing emulator uses
  a DFS-only `32k.cfg` path and cannot validate the physical ADFS/SWR loader.
  Its fixed `&1900` loader and `&1B00` staging/workspace overlap ADFS OSHWM
  `&1D00`. Require an OSHWM-safe streamed SWR loader, atomic Pi1MHz JIM access,
  16-bit chat request lengths, an embedded build ID, and state-segmented UI
  assertions before repeating this gate.

On 19 August the full Electron/AP5/ADFS profile was run against the exact
read-only BeebSCSI LUN, with RAM banks 6 and 7 and the photographed ROM order.
The automation first had to learn the Electron mapping for `$` (Shift+4), so
that `*DIR $.UTILS.ELKCHAT` selected the real directory rather than testing an
invalid path. The directory catalogued correctly. Both the staged ELKCHAT and
the current unchanged build then failed after `*RUN ELKCHAT`, with `Bad name`
and, for the staged build, `Bad program`. No Pi1MHz mailbox operation preceded
the failure.

The same profile entered BASIC after `*ADFS` and `*MOUNT`; `PRINT PAGE`
returned 7936, or `&1F00`. The ELKCHAT file is loaded and executed at host
`&1900`, below that live MOS boundary. The physical capture reported `&1D00`,
which is also above `&1900`. This is now a reproduced loader-memory defect,
not a reason to relax Elkulator's ADFS or sideways-RAM behaviour. A compatible
launcher must itself load at or above the supported OSHWM, stream the sideways
image without a 16K staging overwrite, and place its main-RAM workspace above
the runtime OSHWM. It must retain the direct host-side SWR entry so an installed
Tube is not selected as a destination.
- [ ] Qualify SSH host keys, public-key and password authentication,
  known-host persistence, cancellation and long sessions on physical hardware.
- [ ] Implement HTTPS before testing certificate chains, hostnames, clock
  policy, protocol minimums and failure paths.
- [ ] Capture traffic and confirm that every verification failure remains
  closed rather than retrying in plaintext.
