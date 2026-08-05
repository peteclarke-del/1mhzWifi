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
install -m 0644 "$script_dir/elkwifi-0.23/version.asm" "$upstream/rom/version.asm"
for patch_name in identity.patch integration.patch command-surface.patch disconnect-response.patch wicfs-page-shadow.patch wicfs-osfile-metadata.patch wicfs-host-only.patch wicfs-vector-chain.patch wicfs-reentry-run.patch wicfs-rewind.patch rom-prune.patch routines-prune.patch; do
    patch_file="$script_dir/elkwifi-0.23/$patch_name"
    patch_present=false
    case "$patch_name" in
        integration.patch)
            grep -q 'include "menusrc.asm"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'include "service_driver.asm"' "$upstream/rom/ElkWifi.asm" &&
            grep -q '^\.service_driver_not_0' "$upstream/rom/driver.asm" &&
            patch_present=true
            ;;
        identity.patch)
            grep -q '^\.romtitle.*equs "1MHzWifi"' "$upstream/rom/ElkWifi.asm" &&
            grep -q '^\.romversion.*equs "0.1.4"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'equs "1MHzWifi 0.1.4",&EA' "$upstream/rom/ElkWifi.asm" &&
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
        wicfs-osfile-metadata.patch)
            grep -q '^\\OSFILE metadata return complete' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-host-only.patch)
            grep -q '^\\1MHz-bus filing system and must not claim' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-vector-chain.patch)
            grep -q '^filev_prev_rom = &03A0' "$upstream/rom/wicfs.asm" &&
            grep -q 'refresh the extended table pointer' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.xfscv_direct' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-reentry-run.patch)
            grep -q '^\.upv_rewind_space' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.run_code' "$upstream/rom/wicfs.asm" &&
            ! grep -q '^\.osb_s' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-rewind.patch)
            grep -q 'reload authoritative UEF length from Pi1MHz JIM and rewind' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        rom-prune.patch)
            ! grep -q 'incbin "flash.bin"' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        routines-prune.patch)
            ! grep -q '^\.test_paged_ram' "$upstream/rom/routines.asm" &&
            patch_present=true
            ;;
    esac
    if "$patch_present"; then
        echo "ElkWiFi $patch_name is already applied"
    else
        apply_options=()
        if [[ "$patch_name" = identity.patch ]]; then
            # The banner replacement is deliberately a one-line hunk so it
            # remains independent of upstream startup-flow changes.
            apply_options+=(--unidiff-zero)
        elif [[ "$patch_name" = wicfs-*.patch ]]; then
            # Upstream wicfs.asm uses CRLF. Ignore that whitespace-only
            # difference so this repository can keep a normal text patch.
            apply_options+=(--ignore-space-change --ignore-whitespace --unidiff-zero)
        fi
        git -C "$upstream" apply --check "${apply_options[@]}" "$patch_file"
        git -C "$upstream" apply "${apply_options[@]}" "$patch_file"
    fi
done

# integration.patch must first match the upstream menu source. Replace the
# patched file with the complete Pi1MHz implementation before assembly.
install -m 0644 "$script_dir/elkwifi-0.23/menu.asm" "$upstream/rom/menu.asm"
install -m 0644 "$script_dir/elkwifi-0.23/wificmd.asm" "$upstream/rom/wificmd.asm"
install -m 0644 "$script_dir/elkwifi-0.23/driver.asm" "$upstream/rom/driver.asm"
install -m 0644 "$script_dir/elkwifi-0.23/serial.asm" "$upstream/rom/serial.asm"
install -m 0644 "$script_dir/elkwifi-0.23/wget_helpers.asm" "$upstream/rom/wget.asm"

(cd "$upstream/rom" && beebasm -i ElkWifi.asm)
install -m 0644 "$upstream/rom/bbcwifi.rom" "$root_dir/build/elkwifi_pi1mhz.rom"
sha256sum "$root_dir/build/elkwifi_pi1mhz.rom"
