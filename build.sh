#!/usr/bin/env bash
set -euo pipefail

rom=build/elkwifi_pi1mhz.rom
expected=feeaaaf7915e68d7bd5357fc54ffc85eda2e340be98b6a0619d5372b1ea48775
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict
sha256sum --check --strict SHA256SUMS
