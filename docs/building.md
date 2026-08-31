# Building and release hygiene

This repository contains the maintained 1MHz-WiFi overlays, patches, tests, and
release artifacts. It does not contain patched copies of ElkWiFi or Pi1MHz.
Both upstream projects must be checked out separately at the pinned commits.

Each upstream target has a self-contained package:

- `rom-side/elkwifi-0.23/patches/` contains the ElkWiFi source patches.
- `rom-side/elkwifi-0.23/overlay/` contains complete ROM assembly sources.
- `pi-side/pi1mhz-516a267/patches/` contains the Pi1MHz source patches.
- `pi-side/pi1mhz-516a267/overlay/` contains complete Pi service sources.

The corresponding build script is the authority for patch order. Package
files must not depend on an unrecorded change in an upstream checkout.

## Required tools

- Git
- BeebAsm for the host ROM
- Python 3 for contract tests
- `zip` and `unzip` for the SD-card archive
- CMake and Make for Pi1MHz
- Arm GNU Toolchain 13 or later, including `arm-none-eabi-gcc`

Install the Python test dependency and run the normal unified gate with:

```sh
make deps
make test
```

Use an external build directory with an absolute path containing no spaces.
The upstream Pi1MHz CMake files do not quote every generated include path. If
BeebAsm is installed as a confined Snap, its ElkWiFi checkout must also be in a
location the Snap can read. A short directory directly below the user home
directory satisfies both constraints on a normal Linux workstation.

## Verify and obtain the current reviewed upstream sources

The Pi1MHz revision was verified against the official repository on 7 August
2026. Its default branch is `master`, not `main`, and the reviewed commit was
the branch tip at that time. Before preparing a release, confirm that upstream
has not advanced:

```sh
./pi-side/check_upstream.sh
```

If the check reports a newer commit, review and rebase the integration instead
of changing the hash without qualification.

The following example uses `/home/your-user/1mhzwifi-build`. Replace it with an
explicit path suitable for the build machine.

```sh
build_root=/home/your-user/1mhzwifi-build
mkdir -p "$build_root"

git clone https://github.com/hoglet67/ElkWiFi.git "$build_root/ElkWiFi"
git -C "$build_root/ElkWiFi" checkout 7bf366c97bec18bd238963c95e6f2aa6893cdb3a

git clone https://github.com/dp111/Pi1MHz.git "$build_root/Pi1MHz"
git -C "$build_root/Pi1MHz" checkout e949f2d2714b15f314df375e52db5febb6c40e6d
git -C "$build_root/Pi1MHz" submodule update --init --recursive
./pi-side/check_upstream.sh "$build_root/Pi1MHz"
```

Do not reuse a checkout carrying unrelated local changes. The integration
scripts deliberately modify their supplied upstream checkout.

## Build the host ROM

Run this from the 1MHz-WiFi repository root:

```sh
./rom-side/build_rom.sh "$build_root/ElkWiFi"
```

The command verifies that the checkout contains the reviewed ElkWiFi commit,
applies the ROM patch series in a fixed order, installs the maintained assembly
overlays, and writes the canonical
`build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom`. A repeat invocation must report every
patch as already applied and produce the same 16 KiB ROM. The legacy
`build/elkwifi_pi1mhz.rom` name is a relative symbolic link to this file, not a
second ROM image.

The expected ROM SHA-256 is recorded in `SHA256SUMS` and enforced by
`build.sh`. The Pi build will not start unless this ROM passes its size and hash
checks.

## Build both Pi kernel families and the SD-card bundle

If the Arm compiler is not on `PATH`, set `ARM_GCC` to its executable:

```sh
ARM_GCC=/absolute/path/to/arm-none-eabi-gcc \
  ./pi-side/install_bundle.sh "$build_root/Pi1MHz" all
```

If it is already on `PATH`:

```sh
./pi-side/install_bundle.sh "$build_root/Pi1MHz" all
```

The `all` preset is the release build. It produces:

- `build/pi1mhz-all/kernel.img` for Pi Zero and Pi Zero W
- `build/pi1mhz-all/kernel7.img` for Pi Zero 2 W and Pi 3A+/3B/3B+
- `build/pi1mhz-all/` as the complete FAT boot-partition candidate
- `build/pi1mhz-all-hardware-test.zip` as the equivalent archive
- `build/pi1mhz-all/host-tools/nettools.ssd`, paired with the secure-service
  ABI in those kernels

The `host-tools` directory is release payload, not Pi firmware. Copy or select
`nettools.ssd` using the target machine's DFS/MMFS workflow. Updating only the
boot files cannot update an older `SSH` executable stored in an existing disc
image.

The installer applies every Pi patch, copies the maintained ElkWiFi service
and UEF normalisation sources, preserves active `Pi1MHz.cfg` values, builds
both upstream targets, and packages the firmware tree. Normal hardware-test
bundles retain each
kernel's real link timestamp so a stale SD-card copy can be detected visually.
Set `SOURCE_DATE_EPOCH` only for a release job which requires normalized
timestamps. Use the SHA-256 values and the kernel revision reported by
`*VERSION` as the authoritative image identity.

The kernel revision shown by `*VERSION` fingerprints tracked Pi1MHz changes
and the contents of the untracked 1MHz-WiFi overlay sources. Changing an
overlay source therefore produces a different revision suffix even before the
Pi1MHz integration is committed upstream.

The `rpi` and `rpi3` presets are useful for local iteration, but they are not a
substitute for the `all` release build.

The complete bundle must retain the `brcmfmac43430`, `brcmfmac43436`,
`brcmfmac43436s`, and `brcmfmac43455` firmware triplets under
`Pi1MHz/wifi/`. A plain Pi Zero has no WiFi device and is expected to run the
rest of Pi1MHz while returning `Device not found` from `*WIFI ON`.
The installer replaces the generic 43430 NVRAM template with Raspberry Pi's
GPL-2.0+ Pi 3B calibration file, which Raspberry Pi OS also uses for Zero W.
It also extracts the hardware-proven BCM43455 7.45.241 binary from Pi1MHz
revision `8468a38`, verifies its SHA-256, and installs it over the 7.45.265
binary in the current upstream tree. This is a narrow Pi 3A+/3B+ firmware
compatibility pin, not a rollback of the Pi1MHz source baseline.

## Verify the finished release

```sh
make deps
make test
sha256sum --check --strict SHA256SUMS
```

`build.sh --rom-only` is reserved for scripts which consume the ROM while
regenerating the kernels and archive. Normal release validation must use
the root `make test` target, which invokes `build.sh` without that option.

The tests enforce the ROM contract, 1MHz-bus-only implementation, patch order,
configuration defaults, absence of the retired Linux bridge and cartridge UART
paths, and source inventory. Every file in the ROM and Pi overlay directories
must be referenced by its build script. An orphan patch or source file fails
the suite.

## Keep the repository clean

Upstream checkouts and compiler output belong in the external build directory,
not in this repository. After validation, remove that external directory if it
is no longer required. Within the repository, the only generated files kept in
Git are the reviewed release artifacts under `build/`.

Use these read-only checks before committing:

```sh
git status --short
git status --short --ignored
find . -maxdepth 1 -type d -name '.build-*' -print
find . -type d -name '__pycache__' -print
```

`git status --short` and the two `find` commands should produce no output on a
clean release checkout. `git status --short --ignored` is an inventory check;
review every ignored path it reports. Use `git clean -ndX` only as a preview.
Never use a broad clean command when an upstream checkout or hardware test file
has not been backed up.

Do not commit WiFi credentials, saved `ElkWiFi.*` settings, BeebSCSI LUN data,
UEF test media, emulator captures from ad hoc runs, or patched upstream trees.
