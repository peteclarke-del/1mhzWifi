#!/usr/bin/env bash
# Apply the 1MHzWifi integration to the pinned Pi1MHz and run the host test
# suites that live in that tree.
#
# This is the gate that would have caught what this package spent most of its
# life not catching: upstream owns the WiFi, UEF, secure and net services now,
# this package only patches them, and a patch that still applies can still be
# wrong. Upstream's own suites exercise the patched files - including the FILEV
# stamp repair and the private scratch-to-public JIM copy, whose tests this
# package adds to them - so running them against the integrated tree is worth
# more than any check on the patch text.
#
# No ARM toolchain is needed: every suite here builds for the host with gcc.
# Set PI1MHZ_SOURCE to reuse a checkout; without one, upstream is fetched.
set -euo pipefail

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
# shellcheck source=../upstream.env
. "$root_dir/pi-side/upstream.env"

work=$(mktemp -d /tmp/1mhzwifi-pi-host.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
checkout="$work/Pi1MHz"

if [ -n "${PI1MHZ_SOURCE:-}" ] && [ -d "$PI1MHZ_SOURCE/.git" ]; then
    git clone -q --shared "$PI1MHZ_SOURCE" "$checkout"
    git -C "$checkout" remote set-url origin "$PI1MHZ_UPSTREAM_URL"
else
    git clone -q --filter=blob:none "$PI1MHZ_UPSTREAM_URL" "$checkout"
fi
git -C "$checkout" checkout -q "$PI1MHZ_UPSTREAM_COMMIT"

# The live upstream check is off by default here. This gate answers "does the
# integration still work against the commit we pinned", and upstream advancing
# is not a failure of the change under test; check_upstream.sh is the release
# gate that says the pin has gone stale. Set PI1MHZ_VERIFY_REMOTE=1 to have
# both at once.
PI1MHZ_SKIP_THIRD_PARTY=1 PI1MHZ_VERIFY_REMOTE=${PI1MHZ_VERIFY_REMOTE:-0} \
    "$root_dir/pi-side/install_bundle.sh" "$checkout" apply

# Every host suite in the tree that covers a file this integration touches or
# supplies. uef and net carry the two tests this package adds to them.
status=0
for suite in services net uef ftp secure config; do
    runner="$checkout/src/tests/$suite/run_tests.sh"
    [ -f "$runner" ] || runner="$checkout/src/tests/$suite/run.sh"
    if [ ! -f "$runner" ]; then
        echo "Pi1MHz has no host suite for $suite" >&2
        status=1
        continue
    fi
    echo
    echo "======== Pi1MHz host tests: $suite ========"
    if UEF_CORPUS=${UEF_CORPUS:-} sh "$runner"; then
        echo "$suite: OK"
    else
        echo "$suite: FAILED" >&2
        status=1
    fi
done

# The host ROM against the headers it talks to. The ROM is this repository's
# and the headers are upstream's, so this is the one check that can only run
# with both trees present.
echo
echo "======== 1MHz-WiFi ROM against the service headers ========"
if python3 "$checkout/src/tests/wifirom/check_rom_interface.py" \
        "$root_dir/rom-side/1mhz-wifi/src/service_driver.asm"; then
    echo "rom interface: OK"
else
    echo "rom interface: FAILED" >&2
    status=1
fi

echo
if [ "$status" -eq 0 ]; then
    echo "Pi1MHz host tests against the integrated tree: OK"
else
    echo "Pi1MHz host tests against the integrated tree: FAILED" >&2
fi
exit "$status"
