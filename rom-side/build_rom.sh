#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/ElkWiFi" >&2
    exit 2
fi

upstream=$1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
package_dir="$script_dir/elkwifi-0.23"
patch_dir="$package_dir/patches"
overlay_dir="$package_dir/overlay"

if [ ! -e "$upstream/.git" ] || [ ! -f "$upstream/rom/ElkWifi.asm" ]; then
    echo "$upstream is not an ElkWiFi source checkout" >&2
    exit 1
fi
expected=7bf366c97bec18bd238963c95e6f2aa6893cdb3a
if ! git -C "$upstream" merge-base --is-ancestor "$expected" HEAD; then
    echo "ElkWiFi commit $expected is required" >&2
    exit 1
fi

install -m 0644 "$overlay_dir/menusrc.asm" "$upstream/rom/menusrc.asm"
install -m 0644 "$overlay_dir/service_driver.asm" "$upstream/rom/service_driver.asm"
install -m 0644 "$overlay_dir/net_wget.asm" "$upstream/rom/net_wget.asm"
install -m 0644 "$overlay_dir/online.asm" "$upstream/rom/online.asm"
install -m 0644 "$overlay_dir/ping.asm" "$upstream/rom/ping.asm"
install -m 0644 "$overlay_dir/time.asm" "$upstream/rom/time.asm"
install -m 0644 "$overlay_dir/version.asm" "$upstream/rom/version.asm"
install -m 0644 "$overlay_dir/uef.asm" "$upstream/rom/uef.asm"
for patch_name in identity.patch integration.patch banner-spacing.patch command-surface.patch online-command.patch uef-command.patch disconnect-response.patch wicfs-page-shadow.patch wicfs-osfile-metadata.patch wicfs-host-only.patch wicfs-vector-chain.patch wicfs-osfile-stack.patch wicfs-host-addresses.patch wicfs-reentry-run.patch wicfs-callable-init.patch wicfs-rewind.patch wicfs-long-branches.patch wicfs-final-block.patch wicfs-loader-compat.patch wicfs-zero-length.patch wicfs-cursor-zp.patch wicfs-safe-state.patch wicfs-lifecycle.patch wicfs-jim-state.patch wicfs-vector-entry-state.patch wicfs-jim-atomic.patch wicfs-oscli-prefix.patch wicfs-opt.patch wicfs-private-workspace.patch wicfs-basic-host.patch wicfs-rom-switch.patch wicfs-reset-passive.patch wicfs-transactional-state.patch wicfs-stream-checkpoint.patch wicfs-invalid-state.patch rom-prune.patch routines-prune.patch; do
    patch_file="$patch_dir/$patch_name"
    patch_present=false
    case "$patch_name" in
        integration.patch)
            grep -q 'include "menusrc.asm"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'include "service_driver.asm"' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        identity.patch)
            grep -q '^\.romtitle.*equs "1MHzWifi"' "$upstream/rom/ElkWifi.asm" &&
            grep -q '^\.romversion.*equs "0.1.55"' "$upstream/rom/ElkWifi.asm" &&
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
            { grep -q '^\\1MHz-bus filing system and must not claim' "$upstream/rom/wicfs.asm" ||
              grep -q 'Tube is used only as the MOS OSFILE destination' "$upstream/rom/wicfs.asm"; } &&
            patch_present=true
            ;;
        wicfs-vector-chain.patch)
            grep -Eq '^filev_prev_rom += (&03A0|&03EA|wicfs_state_ram\+5)' "$upstream/rom/wicfs.asm" &&
            grep -q 'refresh the extended table pointer' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.xfscv_direct' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-osfile-stack.patch)
            grep -q 'Keep the OSFILE control-block pointer below the active stack' "$upstream/rom/wicfs.asm" &&
            { grep -q '^\.upf_a1_not_found' "$upstream/rom/wicfs.asm" ||
              grep -q "leave the caller's OSFILE block unchanged" "$upstream/rom/wicfs.asm"; } &&
            patch_present=true
            ;;
        wicfs-host-addresses.patch)
            grep -q 'portable host-memory representation' "$upstream/rom/wicfs.asm" &&
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
        wicfs-final-block.patch)
            grep -q 'BEQ.*stl_a2.*continue before any helper changes flags' "$upstream/rom/wicfs.asm" &&
            grep -q 'JMP.*stl_end.*yes, load complete' "$upstream/rom/wicfs.asm" &&
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
            grep -Eq '^pr_y    =   (&C7|&03E0)' "$upstream/rom/wicfs.asm" &&
            grep -Eq '^pr_r    =   (&C8|&03E1)' "$upstream/rom/wicfs.asm" &&
            grep -q '^fscv_x         = &C9' "$upstream/rom/wicfs.asm" &&
            grep -Eq '^findv_rtn += (&CB|&03E6|wicfs_state_ram\+1)' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-safe-state.patch)
            { grep -q '^pr_y    =   &03E0' "$upstream/rom/wicfs.asm" ||
              grep -Eq '^wicfs_state_ram = (heap\+&E8|&0380)' "$upstream/rom/wicfs.asm"; } &&
            patch_present=true
            ;;
        wicfs-lifecycle.patch)
            grep -q '^\.wicfs_reset' "$upstream/rom/wicfs.asm" &&
            grep -Eq '^bget_prev_rom.*(&03ED|wicfs_state_ram\+8)' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-jim-state.patch)
            grep -Eq '^wicfs_state_ram = (heap\+&E8|&0380)' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_state_load' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-vector-entry-state.patch)
            grep -q '^chain_exec     = &03A0' "$upstream/rom/wicfs.asm" &&
            grep -q 'restore state which applications may overwrite' "$upstream/rom/wicfs.asm" &&
            grep -q 'restore state before any vector forwarding' "$upstream/rom/wicfs.asm" &&
            grep -q 'restore predecessor FSCV after saving arguments' "$upstream/rom/wicfs.asm" &&
            { grep -q 'restore lifecycle state on every external entry' "$upstream/rom/wicfs.asm" ||
              { grep -q '^\.upbgetv_state_valid' "$upstream/rom/wicfs.asm" &&
                grep -q 'bounded EOF; no persisted transaction per byte' "$upstream/rom/wicfs.asm"; }; } &&
            patch_present=true
            ;;
        wicfs-opt.patch)
            grep -q '^\.upv_opt_default' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.upv_opt_retry_values' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-private-workspace.patch)
            grep -q '^wicfs_state_ram = &0380' "$upstream/rom/wicfs.asm" &&
            { { grep -q '^wicfs_state_size = 22' "$upstream/rom/wicfs.asm" &&
                grep -q 'persist cursor and lifecycle changes' "$upstream/rom/wicfs.asm"; } ||
              { grep -q '^wicfs_state_size = 17' "$upstream/rom/wicfs.asm" &&
                grep -q '^wicfs_state_generation = wicfs_state_ram+17' "$upstream/rom/wicfs.asm" &&
                grep -q '^filev_x =   &0396' "$upstream/rom/wicfs.asm" &&
                grep -q '^bget_y  =   &03B1' "$upstream/rom/wicfs.asm"; }; } &&
            patch_present=true
            ;;
        wicfs-basic-host.patch)
            grep -q '^\.upv_basic_match' "$upstream/rom/wicfs.asm" &&
            grep -q 'JMP.*menu_enter_host_basic' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-rom-switch.patch)
            grep -q '^chain_machine  *= &C3' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.chain_preselect' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.run_preselect' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-reset-passive.patch)
            grep -q 'Never read persisted WiCFS' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'Do not touch the AP5 JIM selector' "$upstream/rom/ElkWifi.asm" &&
            ! grep -q 'jsr wicfs_reset' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        wicfs-transactional-state.patch)
            grep -q '^wicfs_record_valid_value = &A5' "$upstream/rom/wicfs.asm" &&
            grep -q '^wicfs_state_generation = wicfs_state_ram+17' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_state_save_payload' "$upstream/rom/wicfs.asm" &&
            grep -q 'commit immutable vector ownership record' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-stream-checkpoint.patch)
            grep -q '^wicfs_state_size = 22' "$upstream/rom/wicfs.asm" &&
            grep -q '^wicfs_machine = &C3' "$upstream/rom/wicfs.asm" &&
            grep -q 'checkpoint cursor before executing loaded code' "$upstream/rom/wicfs.asm" &&
            grep -q 'checkpoint before a loaded program runs' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-invalid-state.patch)
            grep -q '^\.upfilev_state_valid' "$upstream/rom/wicfs.asm" &&
            grep -q 'bounded OSFILE failure; no predecessor is trusted' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.upbgetv_invalid' "$upstream/rom/wicfs.asm" &&
            grep -q 'bounded EOF; no persisted transaction per byte' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-jim-atomic.patch)
            grep -q 'keep bank, page and data read one atomic transaction' "$upstream/rom/wicfs.asm" &&
            { grep -q 'leave the complete public JIM address at 00:00:00' "$upstream/rom/wicfs.asm" ||
              grep -q 'wicfs_select_public_zero.*leave public JIM at 00:00:00' "$upstream/rom/wicfs.asm"; } &&
            grep -q 'recover data before the older saved flags below it' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-oscli-prefix.patch)
            grep -q '^\.upv_about_to_process' "$upstream/rom/wicfs.asm" &&
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
        if [[ "$patch_name" = identity.patch || "$patch_name" = banner-spacing.patch ]]; then
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
install -m 0644 "$overlay_dir/menu.asm" "$upstream/rom/menu.asm"
install -m 0644 "$overlay_dir/wificmd.asm" "$upstream/rom/wificmd.asm"
install -m 0644 "$overlay_dir/driver.asm" "$upstream/rom/driver.asm"
install -m 0644 "$overlay_dir/errors.asm" "$upstream/rom/errors.asm"
install -m 0644 "$overlay_dir/serial.asm" "$upstream/rom/serial.asm"
install -m 0644 "$overlay_dir/wget_helpers.asm" "$upstream/rom/wget.asm"

# Audit the fully patched source, after every patch and overlay has landed.
# The checker resolves source equates, so aliases into &03E0-&03FF cannot hide
# a mutation of the MOS keyboard input buffer used by MENU and UEF command
# queues.
python3 "$script_dir/check_wicfs_keyboard_buffer.py" "$upstream/rom/wicfs.asm"
if grep -q 'jsr wicfs_reset' "$upstream/rom/ElkWifi.asm"; then
    echo "reset service still calls wicfs_reset" >&2
    exit 1
fi
autorun_source=$(sed -n '/^\.autorun/,/^\.autorun_l1/p' "$upstream/rom/ElkWifi.asm")
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
labels_file="$upstream/rom/1mhzwifi-labels.json"
(cd "$upstream/rom" && "$beebasm_command" -i ElkWifi.asm -dd -labels "$labels_file")
python3 "$script_dir/check_combined_ram_layout.py" "$upstream/rom" "$labels_file"
mkdir -p "$root_dir/build"
install -m 0644 "$upstream/rom/bbcwifi.rom" "$root_dir/build/elkwifi_pi1mhz.rom"
sha256sum "$root_dir/build/elkwifi_pi1mhz.rom"
