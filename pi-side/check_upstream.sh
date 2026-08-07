#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ]; then
    echo "usage: $0 [/path/to/Pi1MHz]" >&2
    exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=upstream.env
. "$script_dir/upstream.env"

remote=$(git ls-remote --symref "$PI1MHZ_UPSTREAM_URL" HEAD \
    "refs/heads/$PI1MHZ_UPSTREAM_BRANCH")
default_ref=$(printf '%s\n' "$remote" | awk '$1 == "ref:" && $3 == "HEAD" {print $2}')
remote_commit=$(printf '%s\n' "$remote" | awk -v ref="refs/heads/$PI1MHZ_UPSTREAM_BRANCH" \
    '$1 != "ref:" && $2 == ref {print $1}')

if [ "$default_ref" != "refs/heads/$PI1MHZ_UPSTREAM_BRANCH" ]; then
    echo "Pi1MHz default branch changed: expected $PI1MHZ_UPSTREAM_BRANCH, found ${default_ref:-unknown}" >&2
    exit 1
fi
if [ -z "$remote_commit" ]; then
    echo "could not resolve Pi1MHz $PI1MHZ_UPSTREAM_BRANCH" >&2
    exit 1
fi
if [ "$remote_commit" != "$PI1MHZ_UPSTREAM_COMMIT" ]; then
    echo "Pi1MHz has advanced since $PI1MHZ_UPSTREAM_VERIFIED" >&2
    echo "reviewed integration: $PI1MHZ_UPSTREAM_COMMIT" >&2
    echo "current upstream:    $remote_commit" >&2
    echo "review and rebase the patch set before producing another release" >&2
    exit 1
fi

if [ "$#" -eq 1 ]; then
    checkout_commit=$(git -C "$1" rev-parse HEAD)
    if [ "$checkout_commit" != "$PI1MHZ_UPSTREAM_COMMIT" ]; then
        echo "checkout is at $checkout_commit, expected $PI1MHZ_UPSTREAM_COMMIT" >&2
        exit 1
    fi
fi

printf 'Pi1MHz %s is current at %s (verified %s)\n' \
    "$PI1MHZ_UPSTREAM_BRANCH" "$PI1MHZ_UPSTREAM_COMMIT" "$PI1MHZ_UPSTREAM_VERIFIED"
