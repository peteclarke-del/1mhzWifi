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
install -m 0644 "$script_dir/elkwifi-0.23/online.asm" "$upstream/rom/online.asm"
install -m 0644 "$script_dir/elkwifi-0.23/ping.asm" "$upstream/rom/ping.asm"
install -m 0644 "$script_dir/elkwifi-0.23/time.asm" "$upstream/rom/time.asm"
install -m 0644 "$script_dir/elkwifi-0.23/version.asm" "$upstream/rom/version.asm"
install -m 0644 "$script_dir/elkwifi-0.23/uef.asm" "$upstream/rom/uef.asm"
for patch_name in identity.patch version-0.1.10.patch version-0.1.11.patch version-0.1.12.patch version-0.1.13.patch integration.patch banner-spacing.patch command-surface.patch online-command.patch uef-command.patch disconnect-response.patch wicfs-page-shadow.patch wicfs-osfile-metadata.patch wicfs-host-only.patch wicfs-vector-chain.patch wicfs-osfile-stack.patch wicfs-reentry-run.patch wicfs-loader-compat.patch wicfs-callable-init.patch wicfs-rewind.patch wicfs-long-branches.patch wicfs-zero-length.patch wicfs-cursor-zp.patch wicfs-persistent-state.patch rom-prune.patch routines-prune.patch; do
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
            grep -Eq '^\.romversion.*equs "0\.1\.(9|10|11|12|13)"' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        version-0.1.10.patch)
            grep -Eq '^\.romversion.*equs "0\.1\.(10|11|12|13)"' "$upstream/rom/ElkWifi.asm" &&
            grep -Eq 'equs "1MHzWifi 0\.1\.(10|11|12|13)",&EA' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        version-0.1.11.patch)
            grep -Eq '^\.romversion.*equs "0\.1\.(11|12|13)"' "$upstream/rom/ElkWifi.asm" &&
            grep -Eq 'equs "1MHzWifi 0\.1\.(11|12|13)",&EA' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        version-0.1.12.patch)
            grep -Eq '^\.romversion.*equs "0\.1\.(12|13)"' "$upstream/rom/ElkWifi.asm" &&
            grep -Eq 'equs "1MHzWifi 0\.1\.(12|13)",&EA' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        version-0.1.13.patch)
            grep -q '^\.romversion.*equs "0.1.13"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'equs "1MHzWifi 0.1.13",&EA' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        banner-spacing.patch)
            grep -q 'equb &D,&EA' "$upstream/rom/ElkWifi.asm" &&
            ! grep -q 'equb &D,&D,&EA' "$upstream/rom/ElkWifi.asm" &&
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
        online-command.patch)
            grep -q 'equs "ONLINE"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'include "online.asm"' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        uef-command.patch)
            grep -q 'equs "UEF"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'equs "QUPRUN"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'include "uef.asm"' "$upstream/rom/ElkWifi.asm" &&
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
        wicfs-osfile-stack.patch)
            grep -q 'Keep the OSFILE control-block pointer below the active stack' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.upf_a1_not_found' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-reentry-run.patch)
            grep -q '^\.upv_rewind_space' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.run_code' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.osb_s' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-loader-compat.patch)
            grep -q '^\.protect_loader_vectors' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.plv_signature' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-callable-init.patch)
            grep -q '^\.wicfs_install' "$upstream/rom/wicfs.asm" &&
            grep -q 'return to the command-specific wrapper' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-rewind.patch)
            grep -q 'reload authoritative UEF length from Pi1MHz JIM and rewind' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-long-branches.patch)
            grep -q '^\.stl_newuef_ok' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.stl_skip_ok' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-zero-length.patch)
            grep -q 'zero-byte CFS files have no data byte to fetch' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.ldb_data' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-cursor-zp.patch)
            grep -Eq '^pr_y    =   (&C7|&D80)' "$upstream/rom/wicfs.asm" &&
            grep -Eq '^pr_r    =   (&C8|&D81)' "$upstream/rom/wicfs.asm" &&
            grep -q '^fscv_x         = &C9' "$upstream/rom/wicfs.asm" &&
            grep -Eq '^findv_rtn = (&CB|&D85)' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-persistent-state.patch)
            grep -q '^pr_y    =   &D80' "$upstream/rom/wicfs.asm" &&
            grep -q '^pr_r    =   &D81' "$upstream/rom/wicfs.asm" &&
            grep -q '^sbufl.*&D82' "$upstream/rom/wicfs.asm" &&
            grep -q '^sbufh.*&D83' "$upstream/rom/wicfs.asm" &&
            grep -q '^sbuft.*&D84' "$upstream/rom/wicfs.asm" &&
            grep -q '^findv_rtn = &D85' "$upstream/rom/wicfs.asm" &&
            grep -q '^slotid.*&D87' "$upstream/rom/wicfs.asm" &&
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
        if [[ "$patch_name" = identity.patch || "$patch_name" = version-0.1.10.patch || "$patch_name" = version-0.1.11.patch || "$patch_name" = version-0.1.12.patch || "$patch_name" = version-0.1.13.patch || "$patch_name" = banner-spacing.patch ]]; then
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
