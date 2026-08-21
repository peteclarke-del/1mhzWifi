#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: $0 /path/to/clean/Pi1MHz output.patch" >&2
    exit 2
fi

source_tree=$1
output=$2
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
# shellcheck source=upstream.env
. "$script_dir/upstream.env"
expected=$PI1MHZ_UPSTREAM_COMMIT
test_root=$(mktemp -d /tmp/1mhzwifi-pi-patch.XXXXXX)
checkout="$test_root/Pi1MHz"

cleanup() {
    rm -rf -- "$test_root"
}
trap cleanup EXIT

if [ "$(git -C "$source_tree" rev-parse HEAD)" != "$expected" ]; then
    echo "Pi1MHz source must be at $expected" >&2
    exit 1
fi

git clone --quiet --no-checkout "$source_tree" "$checkout"
git -C "$checkout" checkout --quiet "$expected"

ELKWIFI_ROM=${ELKWIFI_ROM:-$root_dir/build/pi1mhz-all/Pi1MHz/ElkWiFi.rom} \
WOLFSSL_SOURCE=${WOLFSSL_SOURCE:-} \
WOLFSSH_SOURCE=${WOLFSSH_SOURCE:-} \
    "$script_dir/install_bundle.sh" "$checkout" apply

# Dependency commits are recorded separately and are not vendored into the
# maintainer patch. The generated diff contains all first-party Pi1MHz source,
# configuration, firmware-calibration changes, the matched host ROM, and the
# BCM43455 compatibility firmware pin.
rm -rf -- "$checkout/src/third_party"
git -C "$checkout" add -A src firmware/Pi1MHz/Pi1MHz.cfg \
    firmware/Pi1MHz/ElkWiFi.rom \
    firmware/Pi1MHz/wifi/brcmfmac43430-sdio.txt \
    firmware/Pi1MHz/wifi/brcmfmac43455-sdio.bin
git -C "$checkout" diff --cached --binary HEAD > "$output"

if [ ! -s "$output" ]; then
    echo "generated patch is empty" >&2
    exit 1
fi

printf 'Pi1MHz base: %s\n' "$expected"
printf 'wolfSSL: %s\n' 65836b40693f8ea8d04daac0b1019d8e2e9394dd
printf 'wolfSSH: %s\n' c2d169872e410251a6967fc47d4fc0c6f318b79c
printf 'Patch: %s\n' "$output"
