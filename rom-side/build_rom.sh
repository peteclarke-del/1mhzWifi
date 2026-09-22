#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/ElkWiFi" >&2
    exit 2
fi

upstream=$1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
# Sources this project wrote, and the shrinking set of changes to material
# inherited from ElkWiFi 0.23. The split is by provenance: everything under
# 1mhz-wifi/src is ours to license and to offer upstream, everything under
# inherited/ derives from a tree whose terms are not settled.
overlay_dir="$script_dir/1mhz-wifi/src"
patch_dir="$script_dir/inherited/patches"

if [ ! -e "$upstream/.git" ] || [ ! -f "$upstream/rom/wicfs.asm" ]; then
    echo "$upstream is not an ElkWiFi source checkout" >&2
    exit 1
fi
expected=7bf366c97bec18bd238963c95e6f2aa6893cdb3a
if ! git -C "$upstream" merge-base --is-ancestor "$expected" HEAD; then
    echo "ElkWiFi commit $expected is required" >&2
    exit 1
fi

# The 1MHz-WiFi sources. These are complete files, not changes to inherited
# ones, so they are installed rather than patched. 1mhzwifi.asm is the assembly
# root and pulls in the rest.
install -m 0644 "$overlay_dir/1mhzwifi.asm" "$upstream/rom/1mhzwifi.asm"
install -m 0644 "$overlay_dir/1mhzwicfs.asm" "$upstream/rom/1mhzwicfs.asm"
install -m 0644 "$overlay_dir/machine.asm" "$upstream/rom/machine.asm"
install -m 0644 "$overlay_dir/util.asm" "$upstream/rom/util.asm"
install -m 0644 "$overlay_dir/net_transport.asm" "$upstream/rom/net_transport.asm"
install -m 0644 "$overlay_dir/wicfs_errors.asm" "$upstream/rom/wicfs_errors.asm"
install -m 0644 "$overlay_dir/ramdisk.asm" "$upstream/rom/ramdisk.asm"
install -m 0644 "$overlay_dir/join.asm" "$upstream/rom/join.asm"
install -m 0644 "$overlay_dir/lap.asm" "$upstream/rom/lap.asm"
install -m 0644 "$overlay_dir/ifcfg.asm" "$upstream/rom/ifcfg.asm"
install -m 0644 "$overlay_dir/mode.asm" "$upstream/rom/mode.asm"
install -m 0644 "$overlay_dir/service_driver.asm" "$upstream/rom/service_driver.asm"
install -m 0644 "$overlay_dir/net_wget.asm" "$upstream/rom/net_wget.asm"
install -m 0644 "$overlay_dir/ftp.asm" "$upstream/rom/ftp.asm"
install -m 0644 "$overlay_dir/pdump.asm" "$upstream/rom/pdump.asm"
install -m 0644 "$overlay_dir/online.asm" "$upstream/rom/online.asm"
install -m 0644 "$overlay_dir/ping.asm" "$upstream/rom/ping.asm"
install -m 0644 "$overlay_dir/time.asm" "$upstream/rom/time.asm"
install -m 0644 "$overlay_dir/version.asm" "$upstream/rom/version.asm"
install -m 0644 "$overlay_dir/uef.asm" "$upstream/rom/uef.asm"
install -m 0644 "$overlay_dir/wicfs_messages.asm" "$upstream/rom/wicfs_messages.asm"
install -m 0644 "$overlay_dir/wicfs_catalogue.asm" "$upstream/rom/wicfs_catalogue.asm"
# The ordered stack below can only be applied to the reviewed wicfs.asm: every
# diff assumes the ones before it, and they are zero-context. Restore that one
# file from the pinned commit first, so the result depends on the patches and
# the commit alone and not on what a previous run left behind.
#
# This replaces 45 hand-written "already applied" tests. Three of them could
# never be true on a fully patched tree - they tested for equates that a later
# patch in the same stack deletes again - so the repeat invocation the build
# procedure documents as a requirement failed on context, and the remaining
# forty-two were one upstream edit away from the same rot. git apply --check
# still refuses a patch that does not apply, which is what actually catches a
# mis-ordered or stale stack.
git -C "$upstream" checkout "$expected" -- rom/wicfs.asm

for patch_name in wicfs-page-shadow.patch wicfs-osfile-metadata.patch wicfs-host-only.patch wicfs-vector-chain.patch wicfs-osfile-stack.patch wicfs-host-addresses.patch wicfs-reentry-run.patch wicfs-callable-init.patch wicfs-rewind.patch wicfs-long-branches.patch wicfs-zero-length.patch wicfs-cursor-zp.patch wicfs-safe-state.patch wicfs-lifecycle.patch wicfs-jim-state.patch wicfs-vector-entry-state.patch wicfs-jim-atomic.patch wicfs-oscli-prefix.patch wicfs-opt.patch wicfs-private-workspace.patch wicfs-basic-host.patch wicfs-rom-switch.patch wicfs-transactional-state.patch wicfs-stream-checkpoint.patch wicfs-invalid-state.patch wicfs-stream-finish.patch wicfs-pre-tape-predecessor.patch wicfs-bget-exhaustion.patch wicfs-run-return.patch wicfs-run-owner.patch wicfs-dual-predecessor.patch wicfs-native-predecessor.patch wicfs-opt-forward.patch wicfs-chain-target.patch wicfs-vector-flags.patch wicfs-page-select-fast.patch wicfs-incremental-stream.patch wicfs-low-loader-guard.patch wicfs-bget-refill-detection.patch wicfs-reply-buffer-page.patch wicfs-relocatable-guard.patch wicfs-guard-in-jim.patch wicfs-messages-out.patch wicfs-catalogue-out.patch wicfs-mos-equates-out.patch; do
    patch_file="$patch_dir/$patch_name"
    apply_options=()
    if [[ "$patch_name" = wicfs-*.patch ]]; then
        # Upstream wicfs.asm uses CRLF. Ignore that whitespace-only
        # difference so this repository can keep a normal text patch.
        apply_options+=(--ignore-space-change --ignore-whitespace --unidiff-zero)
    fi
    git -C "$upstream" apply --check "${apply_options[@]}" "$patch_file"
    git -C "$upstream" apply "${apply_options[@]}" "$patch_file"
done

# Replace the patched files with the complete Pi1MHz implementations before
# assembly. MENU itself is deliberately absent; host_launch.asm contains only
# the generic host-language transition shared by UEF loading.
install -m 0644 "$overlay_dir/host_launch.asm" "$upstream/rom/host_launch.asm"
install -m 0644 "$overlay_dir/nslook.asm" "$upstream/rom/nslook.asm"
install -m 0644 "$overlay_dir/wificmd.asm" "$upstream/rom/wificmd.asm"
install -m 0644 "$overlay_dir/driver.asm" "$upstream/rom/driver.asm"
install -m 0644 "$overlay_dir/errors.asm" "$upstream/rom/errors.asm"
install -m 0644 "$overlay_dir/serial.asm" "$upstream/rom/serial.asm"
install -m 0644 "$overlay_dir/wget.asm" "$upstream/rom/wget.asm"

# Audit the fully patched source, after every patch and overlay has landed.
# The checker resolves source equates, so aliases into &03E0-&03FF cannot hide
# a mutation of the MOS keyboard input buffer used by UEF command queues.
python3 "$script_dir/check_wicfs_keyboard_buffer.py" "$upstream/rom/wicfs.asm"
if grep -q 'jsr wicfs_reset' "$upstream/rom/1mhzwicfs.asm"; then
    echo "reset service still calls wicfs_reset" >&2
    exit 1
fi
autorun_source=$(sed -n '/^\.autorun/,/^\.autorun_released/p' "$upstream/rom/1mhzwicfs.asm")
if grep -Eq '\b(pagereg|uptype)\b' <<<"$autorun_source"; then
    echo "reset service still touches AP5 JIM or obsolete printer workspace" >&2
    exit 1
fi

beebasm_command=$(command -v beebasm)
if [[ "$beebasm_command" = /snap/bin/beebasm && -x /snap/beebasm/current/usr/bin/beebasm ]]; then
    # Calling the packaged executable directly avoids snap-confine failures in
    # restricted builders while using the identical assembler payload.
    beebasm_command=/snap/beebasm/current/usr/bin/beebasm
fi
# Two images are built. 1mhz-wifi.rom is entirely this project's work.
# 1mhz-wicfs.rom carries the filing system, and with it the only inherited
# file, so that the network ROM can be licensed and shipped on its own.
labels_file="$upstream/rom/1mhzwifi-labels.json"
# WS_IN_IMAGE=1 is the image Pi1MHz serves: it loads the ROM into sideways
# RAM, so the workspace lives in the bank and costs the host nothing.
# WS_HOST_PAGE is unused in that build but beebasm needs every symbol an IF
# might reach to be defined.
ws_wifi_page=0x0E
ws_wicfs_page=0x11
(cd "$upstream/rom" && "$beebasm_command" -i 1mhzwifi.asm -dd \
    -D WS_IN_IMAGE=1 -D WS_HOST_PAGE=$((ws_wifi_page)) -labels "$labels_file")
wicfs_labels_file="$upstream/rom/1mhzwicfs-labels.json"
(cd "$upstream/rom" && "$beebasm_command" -i 1mhzwicfs.asm -dd \
    -D WS_IN_IMAGE=1 -D WS_HOST_PAGE=$((ws_wicfs_page)) -labels "$wicfs_labels_file")

# WS_IN_IMAGE=0 builds the same sources for a real EPROM. There is no writable
# image to keep the workspace in, so it is three pages of host RAM claimed
# from the OS at service call 1. Each image claims a different fixed range so
# that two of them fitted together do not collide, and PAGE rises by three
# pages per fitted image - which is why this is a separate build and not the
# default.
(cd "$upstream/rom" && "$beebasm_command" -i 1mhzwifi.asm \
    -D WS_IN_IMAGE=0 -D WS_HOST_PAGE=$((ws_wifi_page)))
(cd "$upstream/rom" && "$beebasm_command" -i 1mhzwicfs.asm \
    -D WS_IN_IMAGE=0 -D WS_HOST_PAGE=$((ws_wicfs_page)))
# The RAM layout audit belongs to the image that installs filing system
# vectors and persists state, which is now the WiCFS ROM.
# Every absolute store in the network ROM must land in memory a sideways ROM
# owns. This is dp111's check, repointed at these sources; it is what catches
# the class of fault that had this ROM keeping its scratch at &0900, &0A00 and
# &0D90 - the last of which runs into the extended vector table at &0D9F.
python3 "$script_dir/check_rom_memory.py" 1mhzwifi.asm
# The same check for the EPROM build, where the workspace is host RAM claimed
# at service call 1 rather than part of the image.
python3 "$script_dir/check_rom_memory.py" 1mhzwifi.asm --eprom

python3 "$script_dir/check_combined_ram_layout.py" "$upstream/rom" \
    "$wicfs_labels_file" "$labels_file"
mkdir -p "$root_dir/build"
rom_output=${ELKWIFI_ROM_OUTPUT:-"$root_dir/build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom"}
mkdir -p "$(dirname -- "$rom_output")"
install -m 0644 "$upstream/rom/1mhz-wifi.rom" "$rom_output"
wicfs_output=${ELKWIFI_WICFS_ROM_OUTPUT:-"$(dirname -- "$rom_output")/1mhz-wicfs.rom"}
install -m 0644 "$upstream/rom/1mhz-wicfs.rom" "$wicfs_output"
# The EPROM images sit beside them. Pi1MHz serves the two above; these are for
# anyone burning a real ROM, and are not part of the SD-card bundle.
eprom_dir=$(dirname -- "$rom_output")
install -m 0644 "$upstream/rom/1mhz-wifi-eprom.rom" "$eprom_dir/1mhz-wifi-eprom.rom"
install -m 0644 "$upstream/rom/1mhz-wicfs-eprom.rom" "$eprom_dir/1mhz-wicfs-eprom.rom"
sha256sum "$rom_output" "$wicfs_output" \
    "$eprom_dir/1mhz-wifi-eprom.rom" "$eprom_dir/1mhz-wicfs-eprom.rom"
