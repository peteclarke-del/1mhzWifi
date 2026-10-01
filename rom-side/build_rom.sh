#!/usr/bin/env bash
# Build the 1MHz-WiFi host ROM images from dp111's Pi1MHz tree.
#
# The network ROM is Pi1MHz's beeb/1mhz-wifi, taken whole at the commit pinned
# in pi-side/upstream.env, with this project's additions applied on top. This
# repository does not keep a copy of any file upstream has: it keeps the
# patches in 1mhz-wifi/patches and the sources upstream does not carry in
# 1mhz-wifi/src. When upstream changes a file, the rebase is making those
# patches apply again, never deciding whether to take the change.
#
# The filing system ROM adds ElkWiFi 0.23's wicfs.asm with the patch stack in
# inherited/patches, and the sources around it in 1mhz-wifi/src.
#
# usage: build_rom.sh                 compose the sources and build every image
#        build_rom.sh --sources DIR   compose the sources into DIR and stop
#
# PI1MHZ_SOURCE and ELKWIFI_SOURCE name existing checkouts to use instead of
# fetching; each is checked out at its pinned commit.
set -euo pipefail

sources_only=
case "$#:${1:-}" in
    0:) ;;
    2:--sources) sources_only=$2 ;;
    *) echo "usage: $0 [--sources DIR]" >&2; exit 2 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
# shellcheck source=../pi-side/upstream.env
. "$root_dir/pi-side/upstream.env"
ELKWIFI_URL=https://github.com/AtomicRoland/ElkWiFi
# Not on any ElkWiFi branch, but still served by SHA.
ELKWIFI_COMMIT=7bf366c97bec18bd238963c95e6f2aa6893cdb3a

own_dir="$script_dir/1mhz-wifi/src"
rom_patch_dir="$script_dir/1mhz-wifi/patches"
patch_dir="$script_dir/inherited/patches"
cache=${ROM_UPSTREAM_CACHE:-"$root_dir/.build-upstream"}

fetch() {   # url commit dir [existing checkout]
    if [ -n "${4:-}" ]; then
        git -C "$4" cat-file -e "$2^{commit}" 2>/dev/null \
            || git -C "$4" fetch -q origin "$2"
        rm -rf "$3"
        git clone -q --shared --no-checkout "$4" "$3"
    elif [ ! -d "$3/.git" ]; then
        mkdir -p "$3"
        git -C "$3" init -q
        git -C "$3" remote add origin "$1"
    fi
    git -C "$3" cat-file -e "$2^{commit}" 2>/dev/null \
        || git -C "$3" fetch -q --depth 1 origin "$2"
    git -C "$3" checkout -q -f "$2"
    git -C "$3" clean -q -fdx
}

fetch "$PI1MHZ_UPSTREAM_URL" "$PI1MHZ_UPSTREAM_COMMIT" "$cache/pi1mhz" \
    "${PI1MHZ_SOURCE:-}"
fetch "$ELKWIFI_URL" "$ELKWIFI_COMMIT" "$cache/elkwifi" "${ELKWIFI_SOURCE:-}"
upstream="$cache/elkwifi"

work=${sources_only:-"$root_dir/.build-rom"}
rm -rf "$work"
mkdir -p "$work"

# Upstream's ROM, whole, then this project's changes to it. The patches are
# ordered: each assumes the ones before it.
cp "$cache/pi1mhz/beeb/1mhz-wifi/src/"*.asm "$work/"
for rom_patch in read-only-bank.patch help-long-name.patch ftp-command.patch eprom-workspace.patch; do
    # patch, not git apply: inside this repository git apply resolves the
    # paths against the repository root and silently skips them.
    patch -d "$work" -p1 --batch --forward --dry-run --quiet \
        < "$rom_patch_dir/$rom_patch"
    patch -d "$work" -p1 --batch --forward --quiet --no-backup-if-mismatch \
        < "$rom_patch_dir/$rom_patch"
done
# Sources upstream does not carry. Refuse one that shadows an upstream file:
# that would be a fork of it, which is what this layout exists to prevent.
for own in "$own_dir"/*.asm; do
    if [ -e "$cache/pi1mhz/beeb/1mhz-wifi/src/$(basename -- "$own")" ]; then
        echo "$(basename -- "$own") is upstream's; change it with a patch" >&2
        exit 1
    fi
    install -m 0644 "$own" "$work/"
done

# The ordered stack below can only be applied to the reviewed wicfs.asm: every
# diff assumes the ones before it, and they are zero-context. The checkout was
# reset to the pinned commit above, so the result depends on the patches and
# the commit alone and not on what a previous run left behind.
#
# dp111's build-merged.sh reads the patch order from the next line, so it
# stays a single "for patch_name in ...; do" line.
for patch_name in wicfs-page-shadow.patch wicfs-osfile-metadata.patch wicfs-host-only.patch wicfs-vector-chain.patch wicfs-osfile-stack.patch wicfs-host-addresses.patch wicfs-reentry-run.patch wicfs-callable-init.patch wicfs-rewind.patch wicfs-long-branches.patch wicfs-zero-length.patch wicfs-cursor-zp.patch wicfs-safe-state.patch wicfs-lifecycle.patch wicfs-jim-state.patch wicfs-vector-entry-state.patch wicfs-jim-atomic.patch wicfs-oscli-prefix.patch wicfs-opt.patch wicfs-private-workspace.patch wicfs-basic-host.patch wicfs-rom-switch.patch wicfs-transactional-state.patch wicfs-stream-checkpoint.patch wicfs-invalid-state.patch wicfs-stream-finish.patch wicfs-pre-tape-predecessor.patch wicfs-bget-exhaustion.patch wicfs-run-return.patch wicfs-run-owner.patch wicfs-dual-predecessor.patch wicfs-native-predecessor.patch wicfs-opt-forward.patch wicfs-chain-target.patch wicfs-vector-flags.patch wicfs-page-select-fast.patch wicfs-incremental-stream.patch wicfs-low-loader-guard.patch wicfs-bget-refill-detection.patch wicfs-reply-buffer-page.patch wicfs-relocatable-guard.patch wicfs-guard-in-jim.patch wicfs-messages-out.patch wicfs-catalogue-out.patch wicfs-mos-equates-out.patch; do
    patch_file="$patch_dir/$patch_name"
    # Upstream wicfs.asm uses CRLF. Ignore that whitespace-only difference so
    # this repository can keep a normal text patch.
    apply_options=(--ignore-space-change --ignore-whitespace --unidiff-zero)
    git -C "$upstream" apply --check "${apply_options[@]}" "$patch_file"
    git -C "$upstream" apply "${apply_options[@]}" "$patch_file"
done
install -m 0644 "$upstream/rom/wicfs.asm" "$work/wicfs.asm"

# Audit the fully patched source, after every patch and overlay has landed.
# The checker resolves source equates, so aliases into &03E0-&03FF cannot hide
# a mutation of the MOS keyboard input buffer used by UEF command queues.
python3 "$script_dir/check_wicfs_keyboard_buffer.py" "$work/wicfs.asm"
if grep -q 'jsr wicfs_reset' "$work/1mhzwicfs.asm"; then
    echo "reset service still calls wicfs_reset" >&2
    exit 1
fi
autorun_source=$(sed -n '/^\.autorun/,/^\.autorun_released/p' "$work/1mhzwicfs.asm")
if grep -Eq '\b(pagereg|uptype)\b' <<<"$autorun_source"; then
    echo "reset service still touches AP5 JIM or obsolete printer workspace" >&2
    exit 1
fi

if [ -n "$sources_only" ]; then
    echo "composed ROM sources in $work"
    exit 0
fi

beebasm_command=${BEEBASM:-$(command -v beebasm)}
if [[ "$beebasm_command" = /snap/bin/beebasm && -x /snap/beebasm/current/usr/bin/beebasm ]]; then
    # Calling the packaged executable directly avoids snap-confine failures in
    # restricted builders while using the identical assembler payload.
    beebasm_command=/snap/beebasm/current/usr/bin/beebasm
fi
# *FTP is off unless INCLUDE_FTP=1. It costs 1,295 bytes, and the image
# Pi1MHz serves has 268 free; which of upstream's features would give way for
# it is upstream's decision. The Pi-side service is built either way.
include_ftp=${INCLUDE_FTP:-0}
ws_wifi_page=0x0E
ws_wicfs_page=0x11
assemble() {   # root, then defines
    local root=$1
    shift
    (cd "$work" && "$beebasm_command" -i "$root" -D INCLUDE_FTP="$include_ftp" "$@")
}

# The image Pi1MHz serves: upstream's merged network and filing system bank,
# with the switches upstream's build-merged.sh selects, which are the one
# configuration that fits. Helper 16 loads it as 1mhz-wicfs.rom. WS_IN_IMAGE=1
# because Pi1MHz loads it into sideways RAM, so the workspace lives in the
# bank; WS_HOST_PAGE is unused then, but beebasm needs every symbol an IF
# might reach to be defined.
assemble 1mhzwifi.asm -D INCLUDE_WICFS=1 -D INCLUDE_RAMDISK=1 \
    -D INCLUDE_PDUMP=0 -D HELP_BRIEF=1 -D WS_IN_IMAGE=1 \
    -D WS_HOST_PAGE=$((ws_wifi_page))

# The same sources as two images, network and filing system, at upstream's
# non-merged switches. Neither is loaded by a Pi1MHz helper: they are for the
# emulator runners, a ROM board, and the EPROM builds below.
split_defines=(-D INCLUDE_WICFS=0 -D INCLUDE_RAMDISK=1 -D INCLUDE_PDUMP=1
    -D HELP_BRIEF=0)
labels_file="$work/1mhzwifi-labels.json"
assemble 1mhzwifi.asm -dd "${split_defines[@]}" \
    -D WS_IN_IMAGE=1 -D WS_HOST_PAGE=$((ws_wifi_page)) -labels "$labels_file"
wicfs_labels_file="$work/1mhzwicfs-labels.json"
assemble 1mhzwicfs.asm -dd "${split_defines[@]}" \
    -D WS_IN_IMAGE=1 -D WS_HOST_PAGE=$((ws_wicfs_page)) -labels "$wicfs_labels_file"

# WS_IN_IMAGE=0 builds the split images for a real EPROM. There is no writable
# image to keep the workspace in, so it is three pages of host RAM claimed
# from the OS at service call 1. Each image claims a different fixed range so
# that two of them fitted together do not collide, and PAGE rises by three
# pages per fitted image, which is why this is a separate build and not the
# default.
assemble 1mhzwifi.asm "${split_defines[@]}" \
    -D WS_IN_IMAGE=0 -D WS_HOST_PAGE=$((ws_wifi_page))
assemble 1mhzwicfs.asm "${split_defines[@]}" \
    -D WS_IN_IMAGE=0 -D WS_HOST_PAGE=$((ws_wicfs_page))
# Every absolute store in the network ROM must land in memory a sideways ROM
# owns. This is dp111's check, extended for two roots and the EPROM build; it
# is what catches the class of fault that had this ROM keeping its scratch at
# &0900, &0A00 and &0D90, the last of which runs into the extended vector
# table at &0D9F.
python3 "$script_dir/check_rom_memory.py" --src "$work" 1mhzwifi.asm
python3 "$script_dir/check_rom_memory.py" --src "$work" 1mhzwifi.asm --eprom

# The RAM layout audit belongs to the image that installs filing system
# vectors and persists state, which is the WiCFS ROM.
python3 "$script_dir/check_combined_ram_layout.py" "$work" \
    "$wicfs_labels_file" "$labels_file"

out_dir=$(dirname -- "${ELKWIFI_ROM_OUTPUT:-"$root_dir/build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom"}")
mkdir -p "$out_dir"
images=(1mhz-wicfs.rom 1mhz-wifi.rom 1mhz-wicfs-only.rom
    1mhz-wifi-eprom.rom 1mhz-wicfs-only-eprom.rom)
for image in "${images[@]}"; do
    install -m 0644 "$work/$image" "$out_dir/$image"
done
(cd "$out_dir" && sha256sum "${images[@]}")
