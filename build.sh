#!/usr/bin/env bash
set -euo pipefail

rom=build/elkwifi_pi1mhz.rom
expected=c13d2d469867ee482d9b409cfa4344c3d12a030387adf667f0c81be6ca176ab3
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict
sha256sum --check --strict SHA256SUMS
