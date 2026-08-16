#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/b-em-source" >&2
    exit 2
fi

integration_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
component_dir=$(CDPATH= cd -- "$integration_dir/../.." && pwd)
target=$1

test -f "$target/src/6502.c"
test -f "$target/src/Makefile.am"

cp "$component_dir/include/pi1mhz_mailbox.h" "$target/src/"
cp "$component_dir/include/pi1mhz_net_backend.h" "$target/src/"
cp "$component_dir/src/pi1mhz_mailbox.c" "$target/src/"
cp "$component_dir/src/pi1mhz_net_backend.c" "$target/src/"
cp "$component_dir/include/pi1mhz_wolfssh.h" "$target/src/"
cp "$component_dir/src/pi1mhz_wolfssh.c" "$target/src/"
cp "$integration_dir/pi1mhz_bem.h" "$target/src/"
cp "$integration_dir/pi1mhz_bem.c" "$target/src/"

# b-em snapshots may mix CRLF and LF. Normalise the patch targets so the
# versioned patch remains deterministic on Linux and macOS.
for source in "$target/src/6502.c" "$target/src/Makefile.am"; do
    if grep -q "$(printf '\r')" "$source"; then
        tr -d '\r' < "$source" > "$source.pi1mhz-tmp"
        mv "$source.pi1mhz-tmp" "$source"
    fi
done

apply_combined_section() {
    source_path=$1
    section_patch="$target/.pi1mhz-$(basename "$source_path").patch"
    awk -v header="--- a/$source_path" '
        $0 == header { emit = 1 }
        emit && /^--- a\// && $0 != header { exit }
        emit { print }
    ' "$integration_dir/bem-mailbox.patch" > "$section_patch"
    test -s "$section_patch"
    patch --batch -d "$target" -p1 < "$section_patch"
    rm -f "$section_patch"
}

if ! grep -q 'pi1mhz_bem.h' "$target/src/6502.c"; then
    apply_combined_section src/6502.c
fi

# Append through Automake's supported += form instead of rewriting the
# emulator's source list. This composes with other independently installed
# devices and stays valid even if the upstream b_em_SOURCES list changes.
if ! grep -q 'pi1mhz_bem.c' "$target/src/Makefile.am"; then
    printf '\nb_em_SOURCES += pi1mhz_bem.c pi1mhz_mailbox.c pi1mhz_net_backend.c\n' \
        >> "$target/src/Makefile.am"
fi

cat <<EOF
Pi1MHz mailbox installed into b-em.

Regenerate the build system before compiling, e.g.:
    (cd "$target" && ./autogen.sh && ./configure && make)

Enable the device at run time with, for example:
    PI1MHZ_MAILBOX=fixture ./b-em
EOF
