#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--rom-only" ]; }; then
    echo "usage: $0 [--rom-only]" >&2
    exit 2
fi

rom=build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom
expected=1434c236e11249162461ea46a4a0d741189054844e39534c4f43cc90fbb6a40e
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict

if [ "${1:-}" = "--rom-only" ]; then
    exit 0
fi

sha256sum --check --strict SHA256SUMS
