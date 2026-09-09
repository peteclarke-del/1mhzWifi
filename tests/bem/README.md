# B-Em BBC-family tests

`run_bem_hardware.py` runs a reviewed command against the 1MHz-WiFi ROM on a
BBC-family host under B-Em, and captures screens and a mailbox trace. It is the
counterpart to the Elkulator runners, which cover the Electron: between them
the four target machines are the BBC B, BBC B+, BBC Master and Electron, and a
ROM change is not verified until it has been seen on both families.

Three machine profiles are provided, selected with `--machine-profile`:

| profile | machine | OS | ROM slot |
| ------------- | ----------------- | ------ | -------- |
| `bbc-b-32k`   | BBC B 32K         | os12   | 14 |
| `bbc-b-plus`  | BBC B+ 64K        | bpos   | 14 |
| `master-128`  | BBC Master 128    | mos320 | 7 |

## Preparing an emulator

B-Em must be recent enough to support `-cfg` and `-paste`, which the runner
uses to load a generated configuration and type the command. Older snapshots
have neither, and will start with default configuration and no window, which
the runner reports as "expected a B-Em window". Build from current upstream:

```sh
git clone --depth 1 https://github.com/stardot/b-em.git
emulator/pi1mhz-mailbox/integrations/b-em/install.sh /path/to/b-em
(cd /path/to/b-em && ./autogen.sh && ./configure && make -j4)
```

B-Em finds its fonts and ROMs relative to the executable, so with an in-tree
build link them beside it once:

```sh
ln -sfn ../fonts /path/to/b-em/src/fonts
ln -sfn ../roms  /path/to/b-em/src/roms
```

Without the `saa5050` font B-Em cannot draw MODE 7 at all and every capture is
a black screen, which is easy to mistake for a ROM that never started.

## Xvfb

The runners default to `/tmp/elkulator-tools/usr/bin/Xvfb`, which is an
extracted package rather than an installed one, so it survives on a machine
where X is already running on the real display:

```sh
cd /tmp && apt-get download xvfb
dpkg-deb -x xvfb_*.deb /tmp/elkulator-tools
```

Pass `--xvfb` to use a different one.

## Running

```sh
python3 tests/bem/run_bem_hardware.py \
  --bem /path/to/b-em/src/b-em \
  --runtime-dir /path/to/b-em \
  --wifi-rom build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom \
  --machine-profile master-128 \
  --command "help wifi" \
  --output /tmp/1mhzwifi-bem-master
```

`--runtime-dir` supplies the OS and BASIC ROMs under `roms/`, and `cmos.bin`
for the Master. The output directory must not already exist or must be empty;
it receives the generated configuration, the emulator log, the mailbox and bus
traces, the numbered screen captures and `report.json`, which records the
SHA-256 of every immutable input so a capture can be tied to the exact ROM.

The Master reads its configured ROM set from CMOS, so the runner copies the
image into the private `XDG_CONFIG_HOME` it creates for the run. A Master that
boots reporting `This is not a language` and answers `Bad command` has not
found its CMOS, and that result says nothing about the ROM under test.

As with the Elkulator runners, a capture is evidence rather than a verdict.
Use `--require-screen` with reviewed references, and read the screens.
