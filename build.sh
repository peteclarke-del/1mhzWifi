#!/usr/bin/env bash
set -euo pipefail

rom=build/elkwifi_pi1mhz.rom
expected=9a38eafd644950c701edc449802798f517981e220043c5d0a7e666e2d1ed8913
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict
sha256sum --check --strict SHA256SUMS
