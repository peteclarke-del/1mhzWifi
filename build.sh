#!/usr/bin/env bash
set -euo pipefail

rom=build/elkwifi_pi1mhz.rom
expected=923c607123674115c009fd5665b3aea27cd00638054e2a9e937a2903d9a438fe
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict
sha256sum --check --strict SHA256SUMS
