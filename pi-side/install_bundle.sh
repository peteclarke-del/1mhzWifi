#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: $0 /path/to/Pi1MHz [all|rpi|rpi3|apply]" >&2
    exit 2
fi

upstream=$1
preset=${2:-all}
case "$preset" in
    all|rpi|rpi3|apply) ;;
    *) echo "preset must be all, rpi, rpi3 or apply" >&2; exit 2 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
package_dir="$script_dir/pi1mhz-516a267"
patch_dir="$package_dir/patches"
overlay_dir="$package_dir/overlay"
output_dir=${PI1MHZ_OUTPUT_DIR:-$root_dir/build}
# shellcheck source=upstream.env
. "$script_dir/upstream.env"

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
expected_upstream=$PI1MHZ_UPSTREAM_COMMIT
actual_upstream=$(git -C "$upstream" rev-parse HEAD)
if [ "$actual_upstream" != "$expected_upstream" ]; then
    echo "Pi1MHz commit $expected_upstream is required" >&2
    echo "checkout is at $actual_upstream" >&2
    exit 1
fi

if [ "${PI1MHZ_VERIFY_REMOTE:-1}" = 1 ]; then
    "$script_dir/check_upstream.sh" "$upstream"
else
    echo "warning: live Pi1MHz upstream check disabled; exact reviewed commit is still enforced" >&2
fi

if [ "$preset" != apply ]; then
    arm_gcc=${ARM_GCC:-arm-none-eabi-gcc}
    if ! command -v "$arm_gcc" >/dev/null 2>&1; then
        echo "$arm_gcc is required (set ARM_GCC to its full path)" >&2
        exit 1
    fi
    arm_gcc_path=$(command -v "$arm_gcc")
    PATH=$(dirname -- "$arm_gcc_path"):$PATH
    export PATH
    if [ ! -f "$upstream/src/usb/tinyusb/src/tusb.c" ] \
       || [ ! -f "$upstream/src/wifi/lwip/src/core/def.c" ]; then
        echo "Pi1MHz TinyUSB and lwIP submodules are required for a firmware build" >&2
        echo "Run: git -C '$upstream' submodule update --init --recursive" >&2
        exit 1
    fi
fi

if [ ! -f "$upstream/src/net_service.c" ]; then
    echo "Pi1MHz must include the post-V1.30 net service (src/net_service.c)" >&2
    echo "Update the checkout to reviewed Pi1MHz $PI1MHZ_UPSTREAM_BRANCH before installing." >&2
    exit 1
fi

wolfssl_commit=65836b40693f8ea8d04daac0b1019d8e2e9394dd
wolfssh_commit=c2d169872e410251a6967fc47d4fc0c6f318b79c
third_party_dir="$upstream/src/third_party"
mkdir -p "$third_party_dir"

install_dependency() {
    name=$1
    url=$2
    commit=$3
    supplied=$4
    destination=$5
    if [ -d "$destination/.git" ]; then
        actual=$(git -C "$destination" rev-parse HEAD)
        if [ "$actual" != "$commit" ]; then
            echo "$name checkout must be at $commit, found $actual" >&2
            exit 1
        fi
        return
    fi
    if [ -n "$supplied" ]; then
        actual=$(git -C "$supplied" rev-parse HEAD)
        if [ "$actual" != "$commit" ]; then
            echo "$name source must be at $commit, found $actual" >&2
            exit 1
        fi
        cp -a "$supplied" "$destination"
    else
        git clone -q "$url" "$destination"
        git -C "$destination" checkout -q "$commit"
    fi
}

install_dependency wolfSSL https://github.com/wolfSSL/wolfssl.git \
    "$wolfssl_commit" "${WOLFSSL_SOURCE:-}" "$third_party_dir/wolfssl"
install_dependency wolfSSH https://github.com/wolfSSL/wolfssh.git \
    "$wolfssh_commit" "${WOLFSSH_SOURCE:-}" "$third_party_dir/wolfssh"
if ! grep -q 'BBC/Electron display' \
        "$third_party_dir/wolfssh/wolfssh/internal.h"; then
    patch -d "$third_party_dir/wolfssh" -p1 \
        < "$patch_dir/wolfssh-pi1mhz.patch"
fi

# The host ROM is an input to a complete SD-card build, but not to the
# source-only `apply` preset used to prepare an upstream review patch. A full
# repository checkout uses build/elkwifi_pi1mhz.rom. A standalone patch kit
# may supply ELKWIFI_ROM or place ElkWiFi.rom under pi-side/firmware.
rom_source=${ELKWIFI_ROM:-}
if [ -z "$rom_source" ] && [ -f "$root_dir/build/elkwifi_pi1mhz.rom" ]; then
    rom_source="$root_dir/build/elkwifi_pi1mhz.rom"
    if [ -x "$root_dir/build.sh" ]; then
        "$root_dir/build.sh" --rom-only
    fi
elif [ -z "$rom_source" ] && [ -f "$script_dir/firmware/ElkWiFi.rom" ]; then
    rom_source="$script_dir/firmware/ElkWiFi.rom"
fi
if [ "$preset" != apply ] && [ -z "$rom_source" ]; then
    echo "a built 16 KiB host ROM is required; set ELKWIFI_ROM" >&2
    exit 1
fi
if [ -n "$rom_source" ] && [ "$(wc -c < "$rom_source")" -ne 16384 ]; then
    echo "$rom_source is not a 16 KiB ElkWiFi host ROM" >&2
    exit 1
fi

install_if_changed() {
    source_file=$1
    destination_file=$2
    if [ ! -f "$destination_file" ] || ! cmp -s "$source_file" "$destination_file"; then
        install -m 0644 "$source_file" "$destination_file"
    fi
}

install_if_changed "$overlay_dir/src/elkwifi_service.c" "$upstream/src/elkwifi_service.c"
install_if_changed "$overlay_dir/src/elkwifi_service.h" "$upstream/src/elkwifi_service.h"
install_if_changed "$overlay_dir/src/uef_normalize.c" "$upstream/src/uef_normalize.c"
install_if_changed "$overlay_dir/src/uef_normalize.h" "$upstream/src/uef_normalize.h"
install_if_changed "$overlay_dir/src/puff.c" "$upstream/src/puff.c"
install_if_changed "$overlay_dir/src/puff.h" "$upstream/src/puff.h"
install_if_changed "$overlay_dir/src/secure_service.c" "$upstream/src/secure_service.c"
install_if_changed "$overlay_dir/src/secure_service.h" "$upstream/src/secure_service.h"
install_if_changed "$overlay_dir/src/secure_service_core.c" "$upstream/src/secure_service_core.c"
install_if_changed "$overlay_dir/src/secure_service_core.h" "$upstream/src/secure_service_core.h"
install_if_changed "$overlay_dir/src/secure_service_wolfssh.c" "$upstream/src/secure_service_wolfssh.c"
install_if_changed "$overlay_dir/src/secure_service_wolfssh.h" "$upstream/src/secure_service_wolfssh.h"
install_if_changed "$overlay_dir/src/user_settings.h" "$upstream/src/user_settings.h"

for patch_name in integration.patch service-range-online.patch uef-normalize.patch services-capacity-test.patch deterministic-service-dispatch.patch gitversion-untracked-content.patch gitversion-third-party.patch secure-service.patch wifi-security.patch wifi-radio.patch wifi-mac-fallback.patch wifi-radio-setup.patch wifi-join-diagnostics.patch wifi-join-reference.patch wifi-leave.patch wifi-network-tools.patch wifi-pi3b.patch http-status.patch tcp-diagnostics.patch http-truncated-body.patch http-user-agent.patch wifi-off-state.patch wifi-scan-cancel.patch wifi-profile-validation.patch; do
    patch_file="$patch_dir/$patch_name"
    patch_present=false
    case "$patch_name" in
        integration.patch)
            grep -q 'elkwifi_service.c' "$upstream/src/CMakeLists.txt" &&
            grep -q 'SERVICE_CMD_ELKWIFI_FIRST' "$upstream/src/services.h" &&
            grep -q '#define SERVICES_MAX 8u' "$upstream/src/services_emulator.c" &&
            patch_present=true
            ;;
        service-range-online.patch)
            grep -Eq 'SERVICE_CMD_ELKWIFI_LAST  *(92|93)u' "$upstream/src/services.h" &&
            patch_present=true
            ;;
        uef-normalize.patch)
            grep -q 'SERVICE_CMD_ELKWIFI_LAST  *93u' "$upstream/src/services.h" &&
            grep -q '^    uef_normalize.c' "$upstream/src/CMakeLists.txt" &&
            grep -q '^    puff.c' "$upstream/src/CMakeLists.txt" &&
            patch_present=true
            ;;
        services-capacity-test.patch)
            grep -q 'eighth range registers' "$upstream/src/tests/services/test_services.c" &&
            grep -q 'identical reset-time claim renews' "$upstream/src/tests/services/test_services.c" &&
            patch_present=true
            ;;
        deterministic-service-dispatch.patch)
            grep -q 'Built-in service ranges have fixed ABI allocations' \
                "$upstream/src/services_emulator.c" &&
            grep -q 'Private service headers are deliberately not' "$upstream/src/services_emulator.c" &&
            grep -q 'net_service_command(command_pointer' "$upstream/src/services_emulator.c" &&
            grep -q 'elkwifi_service_command(command_pointer' "$upstream/src/services_emulator.c" &&
            grep -q 'secure_service_command(command_pointer' "$upstream/src/services_emulator.c" &&
            grep -q 'void net_service_command' "$upstream/src/net_service.c" &&
            grep -q 'void elkwifi_service_command' "$upstream/src/elkwifi_service.c" &&
            grep -q 'void secure_service_command' "$upstream/src/secure_service.c" &&
            grep -q 'command 94 routed directly to secure service' \
                "$upstream/src/tests/services/test_services.c" &&
            grep -q 'fixed_services_child' "$upstream/src/Pi1MHz.c" &&
            grep -q 'fixed Services command range' "$upstream/src/Pi1MHz.c" &&
            patch_present=true
            ;;
        gitversion-untracked-content.patch)
            grep -q 'GIT_UNTRACKED_CONTENT' "$upstream/src/scripts/gitversion.cmake" &&
            grep -q 'file(SHA256.*UNTRACKED_FILE' "$upstream/src/scripts/gitversion.cmake" &&
            patch_present=true
            ;;
        gitversion-third-party.patch)
            grep -q ':(exclude)third_party/\*\*' "$upstream/src/scripts/gitversion.cmake" &&
            patch_present=true
            ;;
        secure-service.patch)
            grep -q 'SERVICE_CMD_SECURE_FIRST  *94u' "$upstream/src/services.h" &&
            grep -q 'secure_service.c' "$upstream/src/CMakeLists.txt" &&
            grep -q 'nettools_wolfssh' "$upstream/src/CMakeLists.txt" &&
            grep -q 'secure_service_init' "$upstream/src/Pi1MHz.c" &&
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
        wifi-pi3b.patch)
            grep -q 'original Pi 3B is ARMv8' "$upstream/src/wifi/cyw43.c" &&
            grep -q 'need_legacy = socramrev < 23u' "$upstream/src/wifi/cyw43.c" &&
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
        http-truncated-body.patch)
            grep -q 'declared HTTP body ended early' "$upstream/src/net_service.c" &&
            grep -q 'truncated HTTP body -> TCP_CLOSED' "$upstream/src/tests/net/test_net.c" &&
            patch_present=true
            ;;
        http-user-agent.patch)
            grep -q 'User-Agent: ElkWiFi/0.23' "$upstream/src/net_service.c" &&
            patch_present=true
            ;;
        wifi-off-state.patch)
            grep -q 'bool wifi_disable_radio(void)' "$upstream/src/wifi/wifi.c" &&
            grep -q 'association and address state cleared' "$upstream/src/wifi/wifi_lwip.c" &&
            grep -q 'WLC_DOWN: radio disabled by ElkWiFi host' "$upstream/src/wifi/sdio.c" &&
            patch_present=true
            ;;
        wifi-scan-cancel.patch)
            grep -q 'void sdio_runtime_scan_cancel(void)' "$upstream/src/wifi/sdio.c" &&
            grep -q 'void sdio_runtime_scan_cancel(void);' "$upstream/src/wifi/sdio.h" &&
            patch_present=true
            ;;
        wifi-profile-validation.patch)
            grep -q 'bool wifi_profile_is_valid' "$upstream/src/wifi/wifi.c" &&
            grep -q 'g_wifi_state == WIFI_STATE_DISABLED' "$upstream/src/wifi/wifi.c" &&
            patch_present=true
            ;;
    esac
    if "$patch_present"; then
        echo "Pi1MHz $patch_name is already applied"
    elif [ "$patch_name" = http-status.patch ] || [ "$patch_name" = service-range-online.patch ] || [ "$patch_name" = uef-normalize.patch ]; then
        # These small migration patches use zero-context hunks so they can
        # update an already-integrated checkout as well as a clean one.
        git -C "$upstream" apply --unidiff-zero --check "$patch_file"
        git -C "$upstream" apply --unidiff-zero "$patch_file"
    else
        git -C "$upstream" apply --check "$patch_file"
        git -C "$upstream" apply "$patch_file"
    fi
done

# Raspberry Pi OS uses this calibrated NVRAM for both the original Pi 3B and
# Zero W. The generic upstream file contains placeholder calibration values.
install_if_changed "$script_dir/firmware/brcmfmac43430-sdio.txt" \
                   "$upstream/firmware/Pi1MHz/wifi/brcmfmac43430-sdio.txt"

# Pi1MHz 92ccf96 replaced BCM43455 firmware 7.45.241 with 7.45.265. The
# replacement associates on the Pi 3A+ validation hardware but does not pass
# DHCP traffic. Keep current Pi1MHz source while installing the last proven
# BCM43455 image from the pinned upstream history.
bcm43455_path=firmware/Pi1MHz/wifi/brcmfmac43455-sdio.bin
bcm43455_tmp=$(mktemp)
trap 'rm -f "$bcm43455_tmp"' EXIT
git -C "$upstream" show \
    "$PI1MHZ_BCM43455_FIRMWARE_COMMIT:$bcm43455_path" > "$bcm43455_tmp"
printf '%s  %s\n' "$PI1MHZ_BCM43455_FIRMWARE_SHA256" "$bcm43455_tmp" \
    | sha256sum --check --strict
install_if_changed "$bcm43455_tmp" "$upstream/$bcm43455_path"

if [ -n "$rom_source" ]; then
    install_if_changed "$rom_source" "$upstream/firmware/Pi1MHz/ElkWiFi.rom"
fi
install_if_changed "$script_dir/firmware/EMMFS.rom" "$upstream/firmware/Pi1MHz/EMMFS.rom"

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
ensure_config_default Rampage_addr 0xFD
if ! grep -Eqi '^[[:space:]]*Rampage_addr[[:space:]]*=[[:space:]]*0x0*FD([[:space:]]*(#.*)?)?$' "$config_file"; then
    echo "Pi1MHz.cfg must set Rampage_addr=0xFD for the 1MHzWifi JIM transport" >&2
    exit 1
fi
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
    apply)
        echo "Applied the complete 1MHzWifi integration to $upstream"
        exit 0
        ;;
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
bundle="$output_dir/pi1mhz-$preset"
mkdir -p "$bundle"
cp -a "$upstream/firmware/." "$bundle/"

# Keep the host programs paired with the firmware which implements their
# mailbox ABI.  This is distribution material rather than Pi boot firmware,
# but putting it in the same release tree prevents an SD-card update from
# silently leaving an older SSH/TERM binary in use.
host_tools_ssd=${HOST_TOOLS_SSD:-}
if [ -d "$root_dir/host-tools" ]; then
    make -C "$root_dir/host-tools" all
    host_tools_ssd="$root_dir/host-tools/build/nettools.ssd"
fi
if [ -n "$host_tools_ssd" ]; then
    mkdir -p "$bundle/host-tools"
    install -m 0644 "$host_tools_ssd" "$bundle/host-tools/nettools.ssd"
else
    echo "note: standalone Pi1MHz kit has no NetTools SSD; set HOST_TOOLS_SSD to include one" >&2
fi
# Preserve the actual kernel build times in a normal hardware-test bundle so
# an SD-card operator can distinguish a newly linked image from a stale copy.
# Reproducible release jobs may still request normalized timestamps explicitly.
if [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
    find "$bundle" -exec touch -d "@$SOURCE_DATE_EPOCH" -- {} +
fi
archive="$output_dir/pi1mhz-$preset-hardware-test.zip"
archive_tmp_dir=$(mktemp -d "$output_dir/.pi1mhz-bundle.XXXXXX")
(cd "$output_dir" && TZ=UTC zip -Xqr "$archive_tmp_dir/bundle.zip" "pi1mhz-$preset")
mv "$archive_tmp_dir/bundle.zip" "$archive"
rmdir "$archive_tmp_dir"
echo "Hardware-test SD-card bundle: $bundle"
echo "Hardware-test ZIP archive: $archive"
echo "Copy the contents of that directory to a FAT SD-card boot partition."
echo "Preserve /BeebSCSI*/scsi*.dat when updating an existing card."
echo "This bundle does not include BeebSCSI hard-disc images."
echo "Fit/load $upstream/firmware/Pi1MHz/ElkWiFi.rom as the host sideways ROM."
echo "Install host-tools/nettools.ssd in the Electron's DFS/MMFS workflow."
echo "For a 32K Electron without sideways RAM, fit Pi1MHz/EMMFS.rom as the MMFS ROM."
