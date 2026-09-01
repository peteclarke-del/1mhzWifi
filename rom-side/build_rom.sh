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

install -m 0644 "$overlay_dir/service_driver.asm" "$upstream/rom/service_driver.asm"
install -m 0644 "$overlay_dir/net_wget.asm" "$upstream/rom/net_wget.asm"
install -m 0644 "$overlay_dir/ftp.asm" "$upstream/rom/ftp.asm"
install -m 0644 "$overlay_dir/pdump.asm" "$upstream/rom/pdump.asm"
install -m 0644 "$overlay_dir/online.asm" "$upstream/rom/online.asm"
install -m 0644 "$overlay_dir/ping.asm" "$upstream/rom/ping.asm"
install -m 0644 "$overlay_dir/time.asm" "$upstream/rom/time.asm"
install -m 0644 "$overlay_dir/version.asm" "$upstream/rom/version.asm"
install -m 0644 "$overlay_dir/uef.asm" "$upstream/rom/uef.asm"
for patch_name in identity.patch integration.patch banner-spacing.patch command-surface.patch online-command.patch uef-command.patch disconnect-response.patch wicfs-page-shadow.patch wicfs-osfile-metadata.patch wicfs-host-only.patch wicfs-vector-chain.patch wicfs-osfile-stack.patch wicfs-host-addresses.patch wicfs-reentry-run.patch wicfs-callable-init.patch wicfs-rewind.patch wicfs-long-branches.patch wicfs-zero-length.patch wicfs-cursor-zp.patch wicfs-safe-state.patch wicfs-lifecycle.patch wicfs-jim-state.patch wicfs-vector-entry-state.patch wicfs-jim-atomic.patch wicfs-oscli-prefix.patch wicfs-opt.patch wicfs-private-workspace.patch wicfs-basic-host.patch wicfs-rom-switch.patch wicfs-reset-passive.patch wicfs-transactional-state.patch wicfs-stream-checkpoint.patch wicfs-invalid-state.patch wicfs-stream-finish.patch wicfs-pre-tape-predecessor.patch wicfs-bget-exhaustion.patch wicfs-run-return.patch wicfs-run-owner.patch wicfs-dual-predecessor.patch wicfs-native-predecessor.patch wicfs-opt-forward.patch wicfs-chain-target.patch wicfs-vector-flags.patch wicfs-message-preserve.patch wicfs-page-select-fast.patch wicfs-incremental-stream.patch wicfs-low-loader-guard.patch wicfs-bget-refill-detection.patch rom-prune.patch routines-prune.patch menu-retirement.patch ftp-command.patch wicfs-reply-buffer-page.patch wicfs-relocatable-guard.patch wicfs-guard-in-jim.patch wicfs-run-frame-agnostic.patch rom-headroom.patch; do
    patch_file="$patch_dir/$patch_name"
    patch_present=false
    case "$patch_name" in
        integration.patch)
            grep -q 'include "service_driver.asm"' "$upstream/rom/ElkWifi.asm" &&
            { grep -q 'include "menusrc.asm"' "$upstream/rom/ElkWifi.asm" ||
              grep -q 'include "host_launch.asm"' "$upstream/rom/ElkWifi.asm"; } &&
            patch_present=true
            ;;
        wicfs-guard-in-jim.patch)
            grep -q 'romsel.*&FD00+jim_page_usable' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-run-frame-agnostic.patch)
            grep -q '^\.actioned_run' "$upstream/rom/wicfs.asm" &&
            grep -q 'JMP\t(chain_target)\t' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-relocatable-guard.patch)
            grep -q 'guard_kind = wicfs_state_ram' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-reply-buffer-page.patch)
            grep -q 'lda #uef_first_page' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        identity.patch)
            grep -q '^\.romtitle.*equs "1MHzWifi"' "$upstream/rom/ElkWifi.asm" &&
            grep -q '^\.romversion.*equs "0.1.67"' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        banner-spacing.patch)
            grep -q 'equb &D,&EA' "$upstream/rom/ElkWifi.asm" &&
            ! grep -q 'equb &D,&D,&EA' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        command-surface.patch)
            ! grep -q 'include "printer.asm"' "$upstream/rom/ElkWifi.asm" &&
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
        ftp-command.patch)
            grep -q 'equs "FTP"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'include "ftp.asm"' "$upstream/rom/ElkWifi.asm" &&
            patch_present=true
            ;;
        wicfs-mirrored-vectors.patch)
            grep -q '^\\.wicfs_publish_mirror_vectors' "$upstream/rom/wicfs.asm" &&
            grep -q '^jim_page_usable' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        rom-headroom.patch)
            grep -q '^rom_content_end = P%' "$upstream/rom/ElkWifi.asm" &&
            grep -q '^ASSERT rom_content_end <= &BF00' "$upstream/rom/ElkWifi.asm" &&
            ! grep -q 'jsr test_wifi_ena' "$upstream/rom/routines.asm" &&
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
            grep -q '^\.chain_from_stack' "$upstream/rom/wicfs.asm" &&
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
            { { grep -q '^\.upv_opt_default' "$upstream/rom/wicfs.asm" &&
                grep -q '^\.upv_opt_retry_values' "$upstream/rom/wicfs.asm"; } ||
              { grep -q 'local \*OPT support follows' "$upstream/rom/wicfs.asm" &&
                ! grep -q '^\.upv_opt_default' "$upstream/rom/wicfs.asm"; }; } &&
            patch_present=true
            ;;
        wicfs-private-workspace.patch)
            grep -q '^wicfs_state_ram = &0380' "$upstream/rom/wicfs.asm" &&
            { { grep -q '^wicfs_state_size = 22' "$upstream/rom/wicfs.asm" &&
                grep -q '^filev_x =   &0396' "$upstream/rom/wicfs.asm" &&
                grep -q '^bget_y  =   &03B1' "$upstream/rom/wicfs.asm"; } ||
              { grep -q '^wicfs_state_size = 17' "$upstream/rom/wicfs.asm" &&
                grep -q '^wicfs_state_generation = wicfs_state_ram+17' "$upstream/rom/wicfs.asm" &&
                grep -q '^filev_x =   &0396' "$upstream/rom/wicfs.asm" &&
                grep -q '^bget_y  =   &03B1' "$upstream/rom/wicfs.asm"; }; } &&
            patch_present=true
            ;;
        wicfs-basic-host.patch)
            grep -q '^\.upv_basic_match' "$upstream/rom/wicfs.asm" &&
            grep -Eq 'JMP.*(menu_enter_host_basic|host_enter_basic)' "$upstream/rom/wicfs.asm" &&
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
            grep -Eq '^wicfs_state_generation = (wicfs_state_ram\+17|&C5)' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_state_save_payload' "$upstream/rom/wicfs.asm" &&
            grep -q '^wicfs_record_payload = 4' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-stream-checkpoint.patch)
            grep -q '^wicfs_state_size = 22' "$upstream/rom/wicfs.asm" &&
            grep -q '^wicfs_machine = &C3' "$upstream/rom/wicfs.asm" &&
            grep -q 'checkpoint cursor before executing loaded code' "$upstream/rom/wicfs.asm" &&
            grep -q 'checkpoint before a loaded program runs' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-stream-finish.patch)
            grep -q '^\.wicfs_finish_if_exhausted' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_install_byte_trap' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_any_vector_owned' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_install_check_partial' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_prepare_byte_trap' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_publish_byte_trap' "$upstream/rom/wicfs.asm" &&
            grep -q 'commit rollback record before publishing hooks' "$upstream/rom/wicfs.asm" &&
            grep -q 'capture any BYTEV owner installed by service &0F' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_release_invalid_byte_trap' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.autorun_wicfs_abort' "$upstream/rom/ElkWifi.asm" &&
            grep -q '^\.uef_run_failed' "$upstream/rom/uef.asm" &&
            grep -q '^ bcs uef_run_failed' "$upstream/rom/uef.asm" &&
            grep -q '^\.bUPCFS_installed' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.error_wicfs_state' "$upstream/rom/errors.asm" &&
            patch_present=true
            ;;
        wicfs-pre-tape-predecessor.patch)
            grep -q '^\.wicfs_snapshot_pre_tape' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_apply_pre_tape' "$upstream/rom/wicfs.asm" &&
            grep -q 'retain the pre-\*TAPE standard BYTEV as well' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-bget-exhaustion.patch)
            grep -q 'retire vectors after the final BGET byte' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-run-return.patch)
            grep -q '^\.run_call' "$upstream/rom/wicfs.asm" &&
            grep -q 'return through the intact MOS extended-vector frame' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-run-owner.patch)
            grep -q '^wicfs_pending_run_rom = 13' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.run_owner_ready' "$upstream/rom/wicfs.asm" &&
            grep -q 'Preserve the displaced cassette FSCV owner separately' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-dual-predecessor.patch)
            grep -q '^\.wicfs_load_pre_tape' "$upstream/rom/wicfs.asm" &&
            grep -q 'Keep the cassette predecessors live while WiCFS owns the stream' "$upstream/rom/wicfs.asm" &&
            grep -q $'^\tSTA\tbytev_rtn+1$' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-native-predecessor.patch)
            grep -q 'Do not issue filing-system shutdown here' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-opt-forward.patch)
            ! grep -q '^\.upv_opt_default' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.upv_not_about_to_process' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-chain-target.patch)
            sed -n '/^\.xfilev$/,/^\.xfilev_direct$/p' "$upstream/rom/wicfs.asm" | grep -q $'^\tLDA\tFILVRTN$' &&
            sed -n '/^\.xfindv$/,/^\.xfindv_direct$/p' "$upstream/rom/wicfs.asm" | grep -q $'^\tLDA\tfindv_rtn$' &&
            sed -n '/^\.xfscv$/,/^\.xfscv_direct$/p' "$upstream/rom/wicfs.asm" | grep -q $'^\tLDA\tFSCVRTN$' &&
            patch_present=true
            ;;
        wicfs-vector-flags.patch)
            grep -q '^\.chain_entry_flags' "$upstream/rom/wicfs.asm" &&
            grep -q 'saved P precedes the MOS extended-vector frame' "$upstream/rom/wicfs.asm" &&
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
            grep -q '^\.wicfs_select_public_page_a' "$upstream/rom/wicfs.asm" &&
            grep -q 'recover data before the older saved flags below it' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-oscli-prefix.patch)
            grep -q '^\.upv_about_to_process' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-message-preserve.patch)
            grep -q 'OSASCI may alter A; retain the byte used as terminator' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-page-select-fast.patch)
            grep -q '^\.wicfs_select_public_page_a' "$upstream/rom/wicfs.asm" &&
            grep -q $'^\tLDA\t#64$' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-incremental-stream.patch)
            grep -q '^\.wicfs_refill_if_available' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.cfsinit_incremental' "$upstream/rom/wicfs.asm" &&
            grep -q 'another Pi window remains' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-low-loader-guard.patch)
            grep -q '^romsel.*&0780.*Tube-off resilient vector guard' "$upstream/rom/wicfs.asm" &&
            grep -q '^\.wicfs_publish_guards_if_host_only' "$upstream/rom/wicfs.asm" &&
            grep -q '^ASSERT romsel+(e_guard-s_guard) <= &0800' "$upstream/rom/wicfs.asm" &&
            patch_present=true
            ;;
        wicfs-bget-refill-detection.patch)
            ! sed -n '/^\.upbgetv/,/^\\=\{20\}/p' "$upstream/rom/wicfs.asm" |
                grep -q 'JSR[[:space:]]*wicfs_detect_machine' &&
            sed -n '/^\.fillget/,/^\\-\{20\}/p' "$upstream/rom/wicfs.asm" |
                grep -q 'Detect it once per 256-byte refill' &&
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
        menu-retirement.patch)
            ! grep -q 'equs "MENU"' "$upstream/rom/ElkWifi.asm" &&
            ! grep -q 'equs "MENUSRC"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'equs "NSLOOK"' "$upstream/rom/ElkWifi.asm" &&
            grep -q 'include "host_launch.asm"' "$upstream/rom/ElkWifi.asm" &&
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
        elif [[ "$patch_name" = wicfs-*.patch || "$patch_name" = menu-retirement.patch ]]; then
            # Upstream wicfs.asm uses CRLF. Ignore that whitespace-only
            # difference so this repository can keep a normal text patch.
            apply_options+=(--ignore-space-change --ignore-whitespace --unidiff-zero)
        fi
        git -C "$upstream" apply --check "${apply_options[@]}" "$patch_file"
        git -C "$upstream" apply "${apply_options[@]}" "$patch_file"
    fi
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
install -m 0644 "$overlay_dir/wget_helpers.asm" "$upstream/rom/wget.asm"

# Audit the fully patched source, after every patch and overlay has landed.
# The checker resolves source equates, so aliases into &03E0-&03FF cannot hide
# a mutation of the MOS keyboard input buffer used by UEF command queues.
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
rom_output=${ELKWIFI_ROM_OUTPUT:-"$root_dir/build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom"}
mkdir -p "$(dirname -- "$rom_output")"
install -m 0644 "$upstream/rom/bbcwifi.rom" "$rom_output"
sha256sum "$rom_output"
