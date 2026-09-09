#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--rom-only" ]; }; then
    echo "usage: $0 [--rom-only]" >&2
    exit 2
fi

rom=build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom
expected=ad37814c31a17afdc9009679ad4ac0fb3dfecc1e9ac7dd2b092fd0be88d1fde5
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict

if [ "${1:-}" = "--rom-only" ]; then
    exit 0
fi

sha256sum --check --strict SHA256SUMS
