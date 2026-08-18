# Elkulator hardware-profile tests

`run_catalogue_differential.py` runs the same published UEF with the AP5 Tube
disabled and enabled. It uses the photographed Electron ROM order, including
the +2 sideways RAM banks, RH Plus, AP5 support ROM, DFS and ADFS. The
1MHzWifi ROM and Pi mailbox remain on the host in both runs.

The runners use the integration's conservative timing fault injection by
default. This is not a calibrated physical timing claim. `--fiq-delay`
overrides the capture delay only. `--fiq-delay 0` is permitted only for an
explicitly identified synchronous fixture comparison. It is not release or
physical-hardware evidence.

The runner selects catalogue entries by their sorted index, as the published
menu builder does. It sends `*MENU` using Elkulator's Shift+quote mapping for
`*`, advances through the catalogue with Down and selects the corresponding
letter. There are no per-title loader paths or expected addresses.

Each pair must download an identical UEF payload and close the game stream.
Generic frame motion or Tube-on/off similarity is not proof of gameplay. A
release gate must also match a reviewed, title-specific gameplay reference and
reject known prompt and MOS-error screens. Every image, trace and emulator log
is retained for inspection.

Earlier differential captures remain diagnostic history. They do not satisfy
the strengthened acceptance contract by themselves because matching animated
frames can also describe the same loader or error state.

`run_uef_gameplay.py` can mount the photographed BeebSCSI LUN read-only, type
`*ADFS`, `*DIR UEF`, and `*UEF LOAD THRUST`, then wait for the reviewed title
frame. It injects Space only after that frame is visible and the Elkulator
window has explicit X11 focus. A pass requires reviewed title and gameplay
references, a substantial input-correlated change, continued gameplay motion,
no known prompt or MOS-error screen, an alive emulator at the deadline, and
identical pre/post media and configuration hashes. The report also hashes the
runner, provenance module, emulator, ROMs, media, and visual references.
With `--recovery-check`, the runner requires an explicit staged
`--pi1mhz-cfg` and reviewed `--prompt-reference`. After Break it waits for that
prompt between `*ADFS`, `*MOUNT` and `*DIR UEF`, rather than typing the commands
back-to-back. The second load must produce a new BeebSCSI READ(6) after Break,
reach the reviewed title and gameplay frames, and show continued motion. A
prompt image belongs only in `--prompt-reference`, not in the repeated
`--failure-reference` arguments for a recovery run.
When Tube mode is requested, a pass also requires Elkulator's explicit AP5
Tube startup marker. Supplying `-tube6502` without starting the parasite can no
longer produce a Tube-on pass.
Historical screenshots are not automatically a pass for the current binary.
The default deadline is 150 seconds because the conservative delayed-bus
profile can spend more than a minute walking a large ADFS directory before
the local UEF stream starts. The deadline remains bounded and reaching it is
still a failure unless reviewed gameplay has been observed.

Example using the maintained disposable Elkulator build:

```sh
python3 tests/elkulator/run_catalogue_differential.py \
  --elkulator /tmp/elkulator-native-audit.H4MofS/elkulator/elkulator \
  --runtime-dir /tmp/elkulator-current.cRHZ8Z \
  --index /path/to/ElkWiFi/menu/data/index.txt \
  --wifi-rom build/pi1mhz-all/Pi1MHz/ElkWiFi.rom \
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
The runner types only `*MENU` during boot. It waits for the traced TITLES close
event, focuses Elkulator, and then selects the requested catalogue letter.
This avoids guessing how long ADFS and the live title-data transfer will take.

## NetTools hardware-profile diagnostic

`run_nettools_hardware.py` records SHA-256 provenance for Elkulator, every ROM,
the 1MHzWifi image, mounted media, the Tube ROM and configuration files. Mutable
media and configuration hashes are recorded separately before and after the
run. The report also records the runtime source revision when it is a Git
checkout and the exact filing-system setup commands.

The photographed MMFS/ADFS machine reports OSHWM `&0800` and HIMEM `&1D00`
before a tool changes mode. The earlier direct-DFS runner reported OSHWM
`&1F00`; that is a different memory envelope and is not evidence for the
physical failure. Use `--sd-image`, replace the appropriate ROM slot with
`--extra-rom SLOT=/path/to/your-mmfs.rom`, and provide the actual MMFS selection
with one or more `--setup-command` options. `--disc` remains available for a
separate DFS profile.

The public NetTools files are host bootstraps at `&2000`. They move the screen
to MODE 4 and run internal host images at `&2200`. Both stages carry `FFFF`
host addresses, so enabling a Tube must not redirect them to the parasite.
The runner requires Elkulator to remain alive through the observation period
and command-specific final evidence. HWDTEST requires a reviewed final screen
containing `HWDTEST RESULT PASS`. SSH requires ordered `SSH_OPEN`, `SSH_USER`
and `CLOSE` records. TELNET requires ordered `OPEN` and `CLOSE` records.
NSLOOK requires both a DNS record and a reviewed final address screen. A lone
trace event cannot pass a command. HWDTEST specifically requires
`--hwd-pass-screen`; an unrelated `--require-screen` cannot satisfy that gate.
`--reject-header-screen` and `--reject-memory-screen` accept captured known
failure frames and return a nonzero status when a generated frame reaches the
configured NCC similarity. `--require-trace-event` requires named mailbox
events for commands which produce them. Frame references must be captures from
the same emulator window geometry. Camera photographs are evidence for manual
comparison, not valid pixel-level NCC references.

`--wifi-rom-slot BANK` installs 1MHzWifi in any sideways bank from 0 through
15. It defaults to bank 3 only to reproduce the photographed machine. If that
bank contains a profile ROM, relocate the displaced ROM explicitly with
`--extra-rom OTHER_BANK=/path/to/rom`. The requested 1MHzWifi bank is applied
last. This makes bank relocation part of the test input rather than an
assumption in the ROM or runner.

Example MMFS invocation, using the ROM slot and image number from the SD build
under test:

```sh
python3 tests/elkulator/run_nettools_hardware.py \
  --elkulator /path/to/patched/elkulator \
  --runtime-dir /path/to/runtime \
  --wifi-rom build/pi1mhz-all/Pi1MHz/ElkWiFi.rom \
  --sd-image /path/to/pi1mhz-sd.img \
  --extra-rom 2=/path/to/your-mmfs.rom \
  --setup-command "din 0" \
  --command hwdtest \
  --hwd-pass-screen /path/to/known-good-hwd-d2-pass.png \
  --reject-header-screen /path/to/header-only.png \
  --reject-memory-screen /path/to/emulator-memory-failure.png \
  --output /tmp/1mhzwifi-mmfs-hwd
```

The D2 HWDTEST screen must show `Entry/opcode`, both before/after markers for
OSBYTE `&82` and `&81`, the requested and read-back FCA6-FCA9 selector bytes,
and all ten secure capability bytes. `Loader OSHWM=&0800 HIMEM=&1D00` proves
the pre-MODE envelope from the exact public loader path. A last line of
`Before OSBYTE &81`
identifies a MOS/Tube call boundary. A CAPS result of zero with incorrect raw
bytes identifies stale or partly published JIM data.

The DFS and MMFS profiles are approximations. They do not emulate the
photographed BeebSCSI LUN. Pass `--beebscsi-lun /path/to/scsi0.dat` with
`--profile adfs-beebscsi`. The runner mounts that image as LUN 0 at `&FC40`,
selects the full-FRED AP5 profile and records the image before and after the
run. Acceptance runners mount the LUN read-only so an emulator defect cannot
change the hardware image. They refuse the adfs-beebscsi profile when the LUN
is absent and only mark BeebSCSI available when Elkulator confirms the mount
in its log. Do not
label a DFS or MMFS report as ADFS BeebSCSI. `--beebscsi-dsc` supplies the
22-to-33-byte geometry sidecar; a sibling file is selected automatically when it
exists. NetTools uses the live backend in this profile, so SSH and DNS cannot
pass against deterministic fixture responses.
