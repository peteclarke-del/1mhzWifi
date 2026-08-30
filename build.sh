#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--rom-only" ]; }; then
    echo "usage: $0 [--rom-only]" >&2
    exit 2
fi

rom=build/pi1mhz-all/Pi1MHz/ElkWiFi.rom
expected=b26423b695fd5ba8a7e5cf90b3ae06c43534fde806b104a9c791ab50ba4c1f6b
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict

if [ "${1:-}" = "--rom-only" ]; then
    exit 0
fi

sha256sum --check --strict SHA256SUMS
