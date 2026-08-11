#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
output_dir=${1:-$root_dir/dist}
stage=$(mktemp -d /tmp/1mhzwifi-patch-kits.XXXXXX)

cleanup() {
    rm -rf -- "$stage"
}
trap cleanup EXIT

mkdir -p "$output_dir"
output_dir=$(CDPATH= cd -- "$output_dir" && pwd)

make_archive() {
    source_path=$1
    archive_name=$2
    top_name=$3
    destination="$stage/$top_name"

    mkdir -p "$destination"
    cp -a "$source_path/." "$destination/"
    cp -a "$root_dir/THIRD_PARTY_NOTICES.md" "$destination/"
    find "$destination" -type d \( -name .build -o -name __pycache__ \) \
        -prune -exec rm -rf -- {} +
    find "$destination" -type f \( -name '*.pyc' -o -name '*.tmp' \) \
        -delete
    (cd "$stage" && find "$top_name" -type f ! -name SHA256SUMS -print0 | sort -z | \
        xargs -0 sha256sum > "$top_name/SHA256SUMS")
    (cd "$stage" && TZ=UTC zip -Xqr "$output_dir/$archive_name" "$top_name")
    unzip -t "$output_dir/$archive_name" >/dev/null
    rm -rf -- "$destination"
}

make_archive "$root_dir/rom-side" \
    1mhzwifi-elkwifi-patch-kit.zip 1mhzwifi-elkwifi
make_archive "$root_dir/pi-side" \
    1mhzwifi-pi1mhz-patch-kit.zip 1mhzwifi-pi1mhz
make_archive "$root_dir/emulator/pi1mhz-mailbox" \
    1mhzwifi-elkulator-patch-kit.zip 1mhzwifi-elkulator

printf 'Created patch kits in %s\n' "$output_dir"
