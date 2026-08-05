#!/usr/bin/env bash
set -euo pipefail

rom=build/elkwifi_pi1mhz.rom
expected=b8761bde7d651f3f7faa4386666208ee2e4c2042bed00057a46b294ecdec9480
test "$(stat -c %s "$rom")" -eq 16384
printf '%s  %s\n' "$expected" "$rom" | sha256sum --check --strict
sha256sum --check --strict SHA256SUMS
