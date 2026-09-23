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

The EPROM build has its own frames, taken with the image in a read-only bank,
which is what a burnt ROM is:

| frame | shows |
| --- | --- |
| `eprom-ifcfg-read-only-bank-0.1.67.png` | `*IFCFG` working from a read-only bank, so the workspace claim at service call 1 succeeded and the signature check passed. |
| `eprom-page-raised-to-1400-0.1.67.png` | `PRINT PAGE` reading 5120, being `&1400`, with both EPROM images fitted and the network one in the higher bank. PAGE is `&0E00` with neither fitted and `&1100` with the network image alone, so each claim raises it by exactly the three pages it reserves. |
| `eprom-wrong-bank-order-declines-0.1.67.png` | the same two images with the banks swapped. The filing system claims first and takes Y past `&0E00`, so the network image cannot prove its range is free, prints the reason and declines its commands. PAGE is still `&1400`. |

The read-only frame is the negative control for the writable one. Before the
faults it exposed were fixed it showed BASIC's keyword table instead: the
workspace test sat ahead of the command table search, so the ROM answered for
every unrecognised command on the machine, and the error it raised was a `BRK`
whose message was inline in the bank and therefore unreadable once the MOS had
paged the ROM out.

These are not pixel references for an automated gate. `--require-screen`
comparisons need captures from the same window geometry as the run under test,
and a frame recorded here for a different profile would silently not match.
