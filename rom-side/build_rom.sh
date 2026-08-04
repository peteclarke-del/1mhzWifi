#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/ElkWiFi" >&2
    exit 2
fi

upstream=$1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)

if [ ! -e "$upstream/.git" ] || [ ! -f "$upstream/rom/ElkWifi.asm" ]; then
    echo "$upstream is not an ElkWiFi source checkout" >&2
    exit 1
fi
expected=7bf366c97bec18bd238963c95e6f2aa6893cdb3a
if ! git -C "$upstream" merge-base --is-ancestor "$expected" HEAD; then
    echo "ElkWiFi commit $expected is required" >&2
    exit 1
fi

install -m 0644 "$script_dir/elkwifi-0.23/menusrc.asm" "$upstream/rom/menusrc.asm"
install -m 0644 "$script_dir/elkwifi-0.23/service_driver.asm" "$upstream/rom/service_driver.asm"
install -m 0644 "$script_dir/elkwifi-0.23/net_wget.asm" "$upstream/rom/net_wget.asm"
install -m 0644 "$script_dir/elkwifi-0.23/ping.asm" "$upstream/rom/ping.asm"
install -m 0644 "$script_dir/elkwifi-0.23/time.asm" "$upstream/rom/time.asm"
for patch_name in integration.patch command-surface.patch disconnect-response.patch wicfs-page-shadow.patch; do
    patch_file="$script_dir/elkwifi-0.23/$patch_name"
    patch_present=false
    case "$patch_name" in
        integration.patch)
            grep -q 'include "menusrc.asm"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'Pi1MHz WiFi is managed by the kernel' "$upstream/rom/serial.asm" &&
            patch_present=true
            ;;
        command-surface.patch)
            ! grep -q 'include "printer.asm"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'jmp service_driver_lapopt' "$upstream/rom/driver.asm" &&
            grep -q 'jmp service_driver_date' "$upstream/rom/driver.asm" &&
            grep -q 'Usage: \*MODE <1|?>' "$upstream/rom/mode.asm" &&
            ! grep -q 'CRC error, aborted' "$upstream/rom/errors.asm" &&
            patch_present=true
            ;;
        disconnect-response.patch)
            grep -q 'equb >disconnect_cmd, <disconnect_cmd' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        wicfs-page-shadow.patch)
            grep -q 'FCFF is write-only through AP5/Pi1MHz' "$upstream/rom/wicfs.asm" &&
            ! grep -q 'inc pagereg.*increment page register' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
    esac
    if "$patch_present"; then
        echo "ElkWiFi $patch_name is already applied"
    else
        apply_options=()
        if [ "$patch_name" = wicfs-page-shadow.patch ]; then
            # Upstream wicfs.asm uses CRLF. Ignore that whitespace-only
            # difference so this repository can keep a normal text patch.
            apply_options+=(--ignore-space-change --unidiff-zero)
        fi
        git -C "$upstream" apply --check "${apply_options[@]}" "$patch_file"
        git -C "$upstream" apply "${apply_options[@]}" "$patch_file"
    fi
done

# integration.patch must first match the upstream menu source. Replace the
# patched file with the complete Pi1MHz implementation before assembly.
install -m 0644 "$script_dir/elkwifi-0.23/menu.asm" "$upstream/rom/menu.asm"
install -m 0644 "$script_dir/elkwifi-0.23/wificmd.asm" "$upstream/rom/wificmd.asm"

if [ ! -f "$upstream/rom/flash.bin" ]; then
    truncate -s 512 "$upstream/rom/flash.bin"
fi
(cd "$upstream/rom" && beebasm -i ElkWifi.asm)
install -m 0644 "$upstream/rom/bbcwifi.rom" "$root_dir/build/elkwifi_pi1mhz.rom"
sha256sum "$root_dir/build/elkwifi_pi1mhz.rom"
