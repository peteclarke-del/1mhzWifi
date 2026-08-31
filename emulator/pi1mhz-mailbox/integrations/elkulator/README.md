# Elkulator Pi1MHz and AP5 patch kit

This directory contains the Elkulator-specific part of the reusable Pi1MHz
mailbox emulator. Distribute it as part of the complete
`emulator/pi1mhz-mailbox` directory so the shared headers, device core and
network backend remain available to `install.sh`.

The reviewed clean Elkulator base is Stardot Elkulator commit
`6cab45aba68fc3d3bdaea4c28b5de4de0307e00e`. The installer also recognises the
ElkChat tree which already contains the legacy ElkWiFi command-line changes.
The two small `*-elkwifi.patch` files are compatibility variants for that
source shape, not duplicate runtime implementations.
`elkulator-autokeys-upgrade.patch` replaces ElkChat's older raw-host-key
injector with the same logical Electron-key implementation used for a clean
Elkulator tree. This is required for configured key maps, including the
Electron `@` key used to enter `*` commands.

## Getting a built Elkulator

The supported source is our fork, which already carries everything in this
directory as a branch:

```sh
git clone -b pi1mhz-integration https://github.com/peteclarke-del/elkulator.git
cd elkulator && git checkout d5ef26c
autoreconf -fi && ./configure && make
```

Prefer the fork. A branch is always consistent with itself, whereas the patch
kit below has to be applied in a fixed order into shared anchors and has twice
gone stale without anyone noticing, because the tests that would catch it skip
when no Elkulator source is present.

The fork tracks Stardot `master`; the patches are offered upstream from it, and
if they are taken the fork goes away and we build stock Elkulator again.

## Applying the patch kit by hand

Still supported, for an ElkChat tree or any base the fork does not match.
Install into a disposable checkout:

```sh
./integrations/elkulator/install.sh /path/to/elkulator
```

Then rebuild Elkulator with its normal Autotools process. Enable the emulated
Pi1MHz device with `PI1MHZ_MAILBOX=fixture` or `PI1MHZ_MAILBOX=live`. See
`TECHNICAL.md` for the hardware model and acceptance limits.

Set `PI1MHZ_BEEBSCSI_LUN=/path/to/scsi0.dat` to mount an explicit raw,
256-byte-sector BeebSCSI LUN 0 at `&FC40-&FC44`. The image is opened read/write
when possible. Set `PI1MHZ_BEEBSCSI_READ_ONLY=1` for a non-mutating diagnostic
run. Use `PI1MHZ_AP5_PROFILE=expanded-snoop` while this separate BeebSCSI
adapter owns FC40 reads. The `full` NPFC-direct profile can coexist when nOE
is enabled, which is the default. Set `PI1MHZ_NOE=0` only for firmware
configured to drive every forwarded read; that mode requires Pi-side FC40.
Set `PI1MHZ_BEEBSCSI_DSC=/path/to/scsi0.dsc` to use a specific 22-to-33-byte
geometry sidecar. A sibling `scsi0.dsc` is selected automatically by default.
Without one, the model derives fallback geometry from the image size.

Set `PI1MHZ_FIQ_DELAY_ACCESSES=5` to enable the conservative timing fault
model used by the release smoke tests. It delays selector-to-data publication
and FCA9 cursor acknowledgement instead of giving tight 6502 code an
unrealistically synchronous mailbox.

Set `PI1MHZ_BUS_TRACE=/path/to/bus.trace` when a test needs the exact order of
host accesses to the services registers, JIM selector/window, and Tube
register block. The trace includes emulated host cycles and mapped JIM byte
addresses. It is diagnostic evidence from the emulator, not a physical bus
timing measurement.
