#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: $0 /path/to/Pi1MHz [all|rpi|rpi3]" >&2
    exit 2
fi

upstream=$1
preset=${2:-all}
case "$preset" in
    all|rpi|rpi3) ;;
    *) echo "preset must be all, rpi or rpi3" >&2; exit 2 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)

if [ ! -e "$upstream/.git" ] || [ ! -f "$upstream/src/Pi1MHz.c" ]; then
    echo "$upstream is not a Pi1MHz source checkout" >&2
    exit 1
fi

if ! git -C "$upstream" rev-parse --verify V1.30 >/dev/null 2>&1; then
    echo "Pi1MHz tag V1.30 is required" >&2
    exit 1
fi
if ! git -C "$upstream" merge-base --is-ancestor V1.30 HEAD; then
    echo "the checkout does not contain Pi1MHz V1.30" >&2
    exit 1
fi
expected_upstream=83bca4922955e28e2f95122d71d631cce813d467
actual_upstream=$(git -C "$upstream" rev-parse HEAD)
if [ "$actual_upstream" != "$expected_upstream" ]; then
    echo "Pi1MHz commit $expected_upstream is required" >&2
    echo "checkout is at $actual_upstream" >&2
    exit 1
fi

arm_gcc=${ARM_GCC:-arm-none-eabi-gcc}
if ! command -v "$arm_gcc" >/dev/null 2>&1; then
    echo "$arm_gcc is required (set ARM_GCC to its full path)" >&2
    exit 1
fi
arm_gcc_path=$(command -v "$arm_gcc")
PATH=$(dirname -- "$arm_gcc_path"):$PATH
export PATH

if [ ! -f "$upstream/src/net_service.c" ]; then
    echo "Pi1MHz must include the post-V1.30 net service (src/net_service.c)" >&2
    echo "Update the checkout to current Pi1MHz master before installing." >&2
    exit 1
fi

"$root_dir/build.sh"
install -m 0644 "$script_dir/pi1mhz-v1.30/src/elkwifi_service.c" "$upstream/src/elkwifi_service.c"
install -m 0644 "$script_dir/pi1mhz-v1.30/src/elkwifi_service.h" "$upstream/src/elkwifi_service.h"

for patch_name in integration.patch wifi-security.patch wifi-radio.patch wifi-mac-fallback.patch wifi-radio-setup.patch wifi-join-diagnostics.patch wifi-join-reference.patch wifi-leave.patch wifi-network-tools.patch http-status.patch tcp-diagnostics.patch wifi-off-state.patch; do
    patch_file="$script_dir/pi1mhz-current/$patch_name"
    patch_present=false
    case "$patch_name" in
        integration.patch)
            grep -q 'elkwifi_service.c' "$upstream/src/CMakeLists.txt" &&
            grep -q 'SERVICE_CMD_ELKWIFI_FIRST' "$upstream/src/services.h" &&
            grep -q '#define SERVICES_MAX 8u' "$upstream/src/services_emulator.c" &&
            patch_present=true
            ;;
        wifi-security.patch)
            grep -q 'WIFI_SDIO_TX_PROBE_COMMAND_WEP_KEY' "$upstream/src/wifi/wifi.h" &&
            grep -q 'WSEC_KEY_PAYLOAD_LENGTH 164u' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-radio.patch)
            grep -q 'bool wifi_enable_radio(void)' "$upstream/src/wifi/wifi.c" &&
            grep -q 'bool wifi_enable_radio(void);' "$upstream/src/wifi/wifi.h" &&
            patch_present=true
            ;;
        wifi-mac-fallback.patch)
            grep -q 'g_runtime_step_deadline_us = now + 250000u' "$upstream/src/wifi/sdio.c" &&
            grep -q 'if (g_runtime_desired_mac_valid)' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-radio-setup.patch)
            grep -q 'Radio-only startup still needs the complete CLM/country' "$upstream/src/wifi/sdio.c" &&
            grep -q "config->ssid\[0\] != '\\\\0'" "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-join-diagnostics.patch)
            grep -q 'last_event_reason' "$upstream/src/wifi/sdio.h" &&
            grep -q 'status.join_busy = sdio_runtime_rejoin_busy' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-join-reference.patch)
            grep -q 'always send the canonical 36 bytes' "$upstream/src/wifi/sdio.c" &&
            grep -q 'commands\[count++\] = WIFI_SDIO_TX_PROBE_COMMAND_MFP' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-leave.patch)
            grep -q 'WIFI_SDIO_TX_PROBE_COMMAND_DISASSOC' "$upstream/src/wifi/wifi.h" &&
            grep -q 'auto-rejoin paused' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-network-tools.patch)
            grep -q '#define LWIP_RAW[[:space:]]*1' "$upstream/src/wifi/lwipopts.h" &&
            grep -q 'src/core/raw.c' "$upstream/src/CMakeLists.txt" &&
            patch_present=true
            ;;
        http-status.patch)
            grep -q 'A completed TCP request is not a successful WGET' "$upstream/src/net_service.c" &&
            grep -q 'h->http_code >= 300u' "$upstream/src/net_service.c" &&
            grep -q 'http_content_length' "$upstream/src/net_service.c" &&
            grep -q 'http_body_read >= h->http_content_length' "$upstream/src/net_service.c" &&
            patch_present=true
            ;;
        tcp-diagnostics.patch)
            grep -q 'static uint8_t net_tcp_result' "$upstream/src/net_service.c" &&
            grep -q 'NET_ERR_HTTP_STATUS' "$upstream/src/net_service.h" &&
            patch_present=true
            ;;
        wifi-off-state.patch)
            grep -q 'bool wifi_disable_radio(void)' "$upstream/src/wifi/wifi.c" &&
            grep -q 'association and address state cleared' "$upstream/src/wifi/wifi_lwip.c" &&
            grep -q 'WLC_DOWN: radio disabled by ElkWiFi host' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
    esac
    if "$patch_present"; then
        echo "Pi1MHz $patch_name is already applied"
    elif [ "$patch_name" = http-status.patch ]; then
        # This pinned patch deliberately uses a zero-context insertion to keep
        # the patch file itself free of whitespace-only context lines.
        git -C "$upstream" apply --unidiff-zero --check "$patch_file"
        git -C "$upstream" apply --unidiff-zero "$patch_file"
    else
        git -C "$upstream" apply --check "$patch_file"
        git -C "$upstream" apply "$patch_file"
    fi
done

install -m 0644 "$root_dir/build/elkwifi_pi1mhz.rom" "$upstream/firmware/Pi1MHz/ElkWiFi.rom"

# The raw socket/URL service is deliberately opt-in upstream.  This adapter
# depends on it for OSWORD &65 TCP and *WGET, so enable it in the shipped
# firmware configuration unless the integrator already made an explicit
# choice.
config_file="$upstream/firmware/Pi1MHz/Pi1MHz.cfg"

# Keep an existing active value.  Otherwise turn the upstream commented
# example into an active default; append only when that release has no such
# example.  This makes rebuilt SD bundles retain explicit local choices while
# ensuring BeebSCSI is usable out of the box on the Electron/AP5 test setup.
ensure_config_default() {
    key="$1"
    value="$2"
    if grep -Eq "^[[:space:]]*$key[[:space:]]*=" "$config_file"; then
        return
    fi
    if grep -Eq "^[[:space:]]*#[[:space:]]*$key[[:space:]]*=" "$config_file"; then
        sed -i -E "0,/^[[:space:]]*#[[:space:]]*$key[[:space:]]*=/{s//${key}=/}" "$config_file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$config_file"
    fi
}

ensure_config_default SCSIJUKE 0
ensure_config_default SCSIID 0
ensure_config_default VFSJUKE 0
if ! grep -Eq '^[[:space:]]*Services_addr[[:space:]]*=' "$config_file"; then
    printf '\n# ElkWiFi host transport: AP5 forwards the FCA0-FCAF block\nServices_addr=0xA6\n' >> "$config_file"
fi
if ! grep -Eq '^[[:space:]]*ElkWiFi_addr[[:space:]]*=' "$config_file"; then
    printf 'ElkWiFi_addr=0x00\n' >> "$config_file"
fi
if ! grep -Eq '^[[:space:]]*net_enable[[:space:]]*=' "$config_file"; then
    printf '\n# Required by the ElkWiFi ROM transport\nnet_enable=1\n' >> "$config_file"
fi
if ! grep -Eq '^[[:space:]]*#?[[:space:]]*elkwifi_menu_url[[:space:]]*=' "$config_file"; then
    printf '\n# Initial ElkWiFi menu source; an explicit *MENUSRC setting overrides it\n# elkwifi_menu_url=http://acornelectron.nl/uefarchive/MENU\n' >> "$config_file"
fi
if ! grep -Eq '^[[:space:]]*#?[[:space:]]*elkwifi_utc_offset_minutes[[:space:]]*=' "$config_file"; then
    printf '# elkwifi_utc_offset_minutes=0  # DATE/TIME offset east of UTC; e.g. 60 for BST\n' >> "$config_file"
fi
if ! grep -Eq '^[[:space:]]*#?[[:space:]]*wifi_security[[:space:]]*=' "$config_file"; then
    printf '# wifi_security=auto      # auto|open|wep|wpa|wpa2\n' >> "$config_file"
fi
case "$preset" in
    all)
        bash "$upstream/src/scripts/build.sh" rpi
        bash "$upstream/src/scripts/build.sh" rpi3
        echo "Built $upstream/firmware/kernel.img and $upstream/firmware/kernel7.img"
        ;;
    rpi)
        bash "$upstream/src/scripts/build.sh" rpi
        echo "Built $upstream/firmware/kernel.img"
        ;;
    rpi3)
        bash "$upstream/src/scripts/build.sh" rpi3
        echo "Built $upstream/firmware/kernel7.img"
        ;;
esac
bundle="$root_dir/build/pi1mhz-$preset"
mkdir -p "$bundle"
cp -a "$upstream/firmware/." "$bundle/"
archive="$root_dir/build/pi1mhz-$preset-hardware-test.zip"
archive_tmp_dir=$(mktemp -d "$root_dir/build/.pi1mhz-bundle.XXXXXX")
(cd "$root_dir/build" && zip -qr "$archive_tmp_dir/bundle.zip" "pi1mhz-$preset")
mv "$archive_tmp_dir/bundle.zip" "$archive"
rmdir "$archive_tmp_dir"
echo "Hardware-test SD-card bundle: $bundle"
echo "Hardware-test ZIP archive: $archive"
echo "Copy the contents of that directory to a FAT SD-card boot partition."
echo "Fit/load $upstream/firmware/Pi1MHz/ElkWiFi.rom as the host sideways ROM."
