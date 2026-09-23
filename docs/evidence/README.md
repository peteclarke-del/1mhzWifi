# Emulator evidence

Frames captured by `tests/elkulator/run_nettools_hardware.py` against the
`minimum-electron` profile, ROM 0.1.67, with the Pi1MHz mailbox fixture
backend. They are kept because the change they record moved where the ROM
writes, and a description of a screen is not the screen.

| frame | shows |
| --- | --- |
| `ifcfg-sideways-ram-0.1.67.png` | `*IFCFG` in a writable bank, returning the fixture address and MAC. The workspace now lives in the image, so this is the frame that proves it works. |
| `ifcfg-read-only-bank-declines-0.1.67.png` | the same ROM in a read-only bank. The banner states the reason once, and both `*DISC` and `*IFCFG` fall through to `Bad command` rather than being answered. |
| `help-wifi-table-driven-0.1.67.png` | `*HELP WIFI` walked out of the command table, with `DISCONNECT` listed and separated from its description. |

The read-only frame is the negative control for the writable one. Before the
faults it exposed were fixed it showed BASIC's keyword table instead: the
workspace test sat ahead of the command table search, so the ROM answered for
every unrecognised command on the machine, and the error it raised was a `BRK`
whose message was inline in the bank and therefore unreadable once the MOS had
paged the ROM out.

These are not pixel references for an automated gate. `--require-screen`
comparisons need captures from the same window geometry as the run under test,
and a frame recorded here for a different profile would silently not match.
