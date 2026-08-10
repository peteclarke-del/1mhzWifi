# Elkulator AP5 Tube support

This directory adds the external Tube device needed to reproduce the Electron,
AP5 and PiTubeDirect configuration used for hardware validation.

`ap5_tube.c` implements the host and parasite sides of the Tube ULA at
`&FCE0` to `&FCEF`. Writes to offset 6 implement PiTubeDirect's coprocessor
selector. Coprocessor 1 selects the supported external 3 MHz 65C02.

The 65C02 core is vrEmu6502, imported from commit
`aae98cb14386d832cb7357c99626520b6590bc24` of
<https://github.com/visrealm/vrEmu6502>. It is distributed under the MIT
licence in `LICENSE.vrEmu6502`.

After running `../install.sh`, configure the Tube when starting Elkulator:

```sh
./elkulator -tube6502 /path/to/6502tube_120.rom [other options]
```

The configured Tube is switched on before the MOS service-ROM scan. RH Plus 1
therefore finds it during cold boot and starts the parasite without a manual
`*TUBE ON` command, matching the physical PiTubeDirect startup path.

BREAK asserts the emulated host-reset input. This resets the Tube ULA channels
and the configured parasite before the Electron CPU restarts. Real Tube
hardware derives parasite reset from host reset; retaining FIFO and processor
state across BREAK can deadlock the following RH Plus service-ROM scan.

The implementation models only the external 65C02 required by the current
hardware test profile. It does not import code from B-em or PiTubeDirect.
