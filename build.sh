#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--rom-only" ]; }; then
    echo "usage: $0 [--rom-only]" >&2
    exit 2
fi

rom=build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom
expected=1fa29e8da6d7c670fdd2c443017bc19d5d47b2a4112ae039b22f702f04e6fa2c
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict

if [ "${1:-}" = "--rom-only" ]; then
    exit 0
fi

sha256sum --check --strict SHA256SUMS
