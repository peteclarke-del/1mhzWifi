#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--rom-only" ]; }; then
    echo "usage: $0 [--rom-only]" >&2
    exit 2
fi

rom=build/elkwifi_pi1mhz.rom
expected=ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict

if [ "${1:-}" = "--rom-only" ]; then
    exit 0
fi

sha256sum --check --strict SHA256SUMS
