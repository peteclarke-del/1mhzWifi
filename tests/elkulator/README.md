# Elkulator hardware-profile tests

`run_catalogue_differential.py` runs the same published UEF with the AP5 Tube
disabled and enabled. It uses the photographed Electron ROM order, including
the +2 sideways RAM banks, RH Plus, AP5 support ROM, DFS and ADFS. The 1MHzWifi ROM
and Pi mailbox remain on the host in both runs.

The runner selects catalogue entries by their sorted index, as the published
menu builder does. It sends `*MENU` using Elkulator's Shift+quote mapping for
`*`, advances through the catalogue with Down and selects the corresponding
letter. There are no per-title loader paths or expected addresses.

Each pair must download an identical UEF payload, close the game stream and
produce a sufficiently similar post-launch display. The no-Tube run is the
behavioural reference because the published catalogue is already known to run
on a non-Tube Electron. Three screen samples reduce false failures from simple
animation phase differences. Every image, trace and emulator log is retained
for inspection.

The first ten-entry differential slice for ROM 0.1.37 produced identical UEF
hashes in every pair. Nine pairs met the strict framebuffer threshold. The
remaining pair reached the same animated Starcade attract screen in both runs,
but at different animation positions, so it remains a visual review result
rather than a byte-image pass. The earlier E-Type Tube stall is included in
this slice and now produces an exact screen match. No title name or title
address appears in the ROM fix or runner. The experimental 0.1.38
caller-return handoff was rejected after the emulator reproduced a return to
BASIC. ROM 0.1.40 restores the proven 0.1.37 launch path. Frak and Zalaga reach
gameplay in Tube-off and Tube-on runs. Arcadians also reaches gameplay in both
modes, although its animated screens do not satisfy a single-frame similarity
threshold. Last of the Free still reports `Bad program` in both modes.

`run_uef_gameplay.py` mounts the local Thrust DFS fixture, types `*DISC` and
`*UEF LOAD THRUST`, then presses Space after the multi-stage loader completes.
The exact final 0.1.40 ROM reaches gameplay with the Tube disabled and enabled.
The retained captures are `uef-thrust-gameplay-0.1.40-final-no-tube.png` and
`uef-thrust-gameplay-0.1.40-final-tube.png` in the screenshots directory.

Example using the maintained disposable Elkulator build:

```sh
python3 tests/elkulator/run_catalogue_differential.py \
  --elkulator /tmp/elkulator-native-audit.H4MofS/elkulator/elkulator \
  --runtime-dir /tmp/elkulator-current.cRHZ8Z \
  --index /path/to/ElkWiFi/menu/data/index.txt \
  --wifi-rom build/elkwifi_pi1mhz.rom \
  --output /tmp/1mhzwifi-catalogue-gate \
  --range 0:20
```

Use repeated `--title` arguments for a short sample or `--all` for the complete
catalogue. A pair which produces the same static failure screen can still look
similar, so release evidence must also include review of the generated contact
sheets or screenshots. Each title directory contains a side-by-side
`comparison.png`, the original samples, network traces and emulator logs. This
limitation is stated deliberately: an emulator cannot infer that every
arbitrary title has reached interactive gameplay from one framebuffer alone.
Animated screens can also be valid while failing a strict pixel comparison.
Treat such results as review items, not automatic product failures or passes.
