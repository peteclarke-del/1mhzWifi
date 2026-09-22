#!/usr/bin/env bash
set -euo pipefail

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
source_tree=${PI1MHZ_SOURCE:?Set PI1MHZ_SOURCE to the pinned Pi1MHz checkout}
test_root=$(mktemp -d /tmp/1mhzwifi-pi-firmware.XXXXXX)
checkout="$test_root/Pi1MHz"

cleanup() {
    rm -rf -- "$test_root"
}
trap cleanup EXIT

test -f "$source_tree/src/Pi1MHz.c"
cp -a "$source_tree" "$checkout"
rm -rf -- "$checkout/src/build"

ARM_GCC=${ARM_GCC:-arm-none-eabi-gcc} \
WOLFSSL_SOURCE=${WOLFSSL_SOURCE:-} \
WOLFSSH_SOURCE=${WOLFSSH_SOURCE:-} \
PI1MHZ_OUTPUT_DIR="$test_root/output" \
    "$root_dir/pi-side/install_bundle.sh" "$checkout" all

test -s "$checkout/firmware/kernel.img"
test -s "$checkout/firmware/kernel7.img"
echo "Combined Pi1MHz Pi 1/Zero and Pi 2/3 firmware builds: OK"
