#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/elkulator-source" >&2
    exit 2
fi

integration_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
component_dir=$(CDPATH= cd -- "$integration_dir/../.." && pwd)
target=$1

test -f "$target/src/mem.c"
test -f "$target/src/Makefile.am"

cp "$component_dir/include/pi1mhz_mailbox.h" "$target/src/"
cp "$component_dir/include/pi1mhz_net_backend.h" "$target/src/"
cp "$component_dir/include/pi1mhz_ftp.h" "$target/src/"
cp "$component_dir/src/pi1mhz_mailbox.c" "$target/src/"
cp "$component_dir/src/pi1mhz_net_backend.c" "$target/src/"
cp "$component_dir/src/pi1mhz_ftp.c" "$target/src/"
cp "$component_dir/include/pi1mhz_wolfssh.h" "$target/src/"
cp "$component_dir/src/pi1mhz_wolfssh.c" "$target/src/"
cp "$integration_dir/pi1mhz_elkulator.h" "$target/src/"
cp "$integration_dir/pi1mhz_elkulator.c" "$target/src/"
cp "$integration_dir/beebscsi_elkulator.h" "$target/src/"
cp "$integration_dir/beebscsi_elkulator.c" "$target/src/"
cp "$integration_dir/tube/ap5_tube.h" "$target/src/"
cp "$integration_dir/tube/ap5_tube.c" "$target/src/"
cp "$integration_dir/tube/vrEmu6502.h" "$target/src/"
cp "$integration_dir/tube/vrEmu6502.c" "$target/src/"
cp "$integration_dir/tube/LICENSE.vrEmu6502" "$target/src/"

# Elkulator snapshots may mix CRLF and LF. Normalise the patch targets so the
# versioned patches remain deterministic on Linux and macOS.
for source in "$target/src/mem.c" "$target/src/main.c" \
              "$target/src/elk.h" "$target/src/Makefile.am" \
              "$target/src/6502.c" "$target/src/ula.c"; do
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
    ' "$integration_dir/elkulator.patch" > "$section_patch"
    test -s "$section_patch"
    patch --batch --no-backup-if-mismatch -d "$target" -p1 < "$section_patch"
    rm -f "$section_patch"
}

if ! grep -q 'pi1mhz_elkulator.h' "$target/src/mem.c"; then
    apply_combined_section src/mem.c
elif grep -q 'pi1mhz_elkulator_handles(addr)' "$target/src/mem.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-snoop-upgrade.patch"
fi
if ! grep -q '^int rambanks\[16\];' "$target/src/main.c"; then
    if grep -q 'elkwifiname' "$target/src/main.c"; then
        patch --batch --no-backup-if-mismatch -d "$target" -p1 \
            < "$integration_dir/elkulator-elkwifi-main.patch"
    else
        apply_combined_section src/main.c
    fi
fi
if ! grep -q 'void enable_ram_n(int bank);' "$target/src/elk.h"; then
    apply_combined_section src/elk.h
fi

if grep -q 'static int scripted_keys\[64\];' "$target/src/main.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 < "$integration_dir/elkulator-autokeys-upgrade.patch"
elif ! grep -q 'parse_scripted_keys' "$target/src/main.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 < "$integration_dir/elkulator-autokeys.patch"
fi

# Append through Automake's supported += form instead of rewriting the
# emulator's source list. This composes with other independently installed
# devices and with Elkulator variants that have different final source files.
if ! grep -q 'pi1mhz_mailbox.c' "$target/src/Makefile.am"; then
    printf '\nelkulator_SOURCES += pi1mhz_mailbox.c pi1mhz_net_backend.c pi1mhz_ftp.c pi1mhz_elkulator.c\n' \
        >> "$target/src/Makefile.am"
fi
if ! grep -q 'pi1mhz_ftp.c' "$target/src/Makefile.am"; then
    sed -i 's/pi1mhz_net_backend.c/pi1mhz_net_backend.c pi1mhz_ftp.c/' \
        "$target/src/Makefile.am"
fi
if ! grep -q '^elkulator_LDADD += -lz$' "$target/src/Makefile.am"; then
    printf '%s\n' 'elkulator_LDADD += -lz' >> "$target/src/Makefile.am"
fi

apply_tube_section() {
    source_path=$1
    section_patch="$target/.pi1mhz-tube-$(basename "$source_path").patch"
    awk -v header="--- a/$source_path" '
        $0 == header { emit = 1 }
        emit && /^--- a\// && $0 != header { exit }
        emit { print }
    ' "$integration_dir/elkulator-ap5-tube.patch" > "$section_patch"
    test -s "$section_patch"
    patch --batch --no-backup-if-mismatch -d "$target" -p1 < "$section_patch"
    rm -f "$section_patch"
}

if ! grep -q 'ap5_tube_sync_host_clock' "$target/src/6502.c"; then
    apply_tube_section src/6502.c
elif ! grep -q 'ap5_tube_rebase_host_clock' "$target/src/6502.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-clock-rebase-upgrade.patch"
fi
if ! grep -q 'ap5_tube.c' "$target/src/Makefile.am"; then
    printf '%s\n' 'elkulator_SOURCES += ap5_tube.c vrEmu6502.c' \
        >> "$target/src/Makefile.am"
fi
if ! grep -q 'void updateulaints(void);' "$target/src/elk.h"; then
    apply_tube_section src/elk.h
fi
if ! grep -q 'ap5_tube_handles' "$target/src/mem.c"; then
    apply_tube_section src/mem.c
fi
if ! grep -q 'ap5_tube_host_irq' "$target/src/ula.c"; then
    apply_tube_section src/ula.c
fi
if ! grep -q 'ap5_tube_init' "$target/src/main.c"; then
    if grep -q 'elkwifiname' "$target/src/main.c"; then
        patch --batch --no-backup-if-mismatch -d "$target" -p1 \
            < "$integration_dir/elkulator-ap5-tube-elkwifi.patch"
    else
        apply_tube_section src/main.c
    fi
fi

if ! grep -q 'beebscsi_elkulator.c' "$target/src/Makefile.am"; then
    printf '\nelkulator_SOURCES += beebscsi_elkulator.c\n' \
        >> "$target/src/Makefile.am"
fi

apply_beebscsi_section() {
    source_path=$1
    section_patch="$target/.pi1mhz-beebscsi-$(basename "$source_path").patch"
    awk -v header="--- a/$source_path" '
        $0 == header { emit = 1 }
        emit && /^--- a\// && $0 != header { exit }
        emit { print }
    ' "$integration_dir/elkulator-beebscsi.patch" > "$section_patch"
    test -s "$section_patch"
    patch --batch --no-backup-if-mismatch -d "$target" -p1 < "$section_patch"
    rm -f "$section_patch"
}

if ! grep -q 'beebscsi_elkulator.h' "$target/src/mem.c"; then
    apply_beebscsi_section src/mem.c
fi
if ! grep -q 'beebscsi_elkulator.h' "$target/src/ula.c"; then
    apply_beebscsi_section src/ula.c
fi

if ! grep -q 'PI1MHZ_RAM_DUMP' "$target/src/main.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-ram-dump.patch"
fi

if ! grep -q 'PI1MHZ_CPU_DUMP' "$target/src/main.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-cpu-dump.patch"
fi

if ! grep -q 'PI1MHZ_VECTOR_TRACE' "$target/src/6502.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-vector-trace.patch"
fi

if ! grep -q 'PI1MHZ_PC_DUMP_ADDRESS' "$target/src/6502.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-pc-dump.patch"
fi

if ! grep -q 'PI1MHZ_PC_HISTORY_TRIGGER' "$target/src/6502.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-pc-history.patch"
fi

if ! grep -q 'PI1MHZ_TUPLE_TRACE' "$target/src/6502.c"; then
    patch --batch --no-backup-if-mismatch -d "$target" -p1 \
        < "$integration_dir/elkulator-tuple-trace.patch"
fi

if [ -n "${PI1MHZ_WOLFSSH_PREFIX:-}" ]; then
    test -f "$PI1MHZ_WOLFSSH_PREFIX/lib/libwolfssh.a"
    test -f "$PI1MHZ_WOLFSSH_PREFIX/lib/libwolfssl.a"
    mkdir -p "$target/src/pi1mhz-wolfssh/include" \
             "$target/src/pi1mhz-wolfssh/lib"
    wolf_target="$target/src/pi1mhz-wolfssh"
    for include_dir in wolfssh wolfssl; do
        source_path=$(CDPATH= cd -- \
            "$PI1MHZ_WOLFSSH_PREFIX/include/$include_dir" && pwd)
        target_path="$wolf_target/include/$include_dir"
        if [ ! -d "$target_path" ] ||
           [ "$source_path" != "$(CDPATH= cd -- "$target_path" && pwd)" ]; then
            cp -a "$source_path" "$wolf_target/include/"
        fi
    done
    for library in libwolfssh.a libwolfssl.a; do
        source_path="$PI1MHZ_WOLFSSH_PREFIX/lib/$library"
        target_path="$wolf_target/lib/$library"
        if [ "$source_path" != "$target_path" ]; then
            cp "$source_path" "$target_path"
        fi
    done
    if ! grep -q 'PI1MHZ_WOLFSSH' "$target/src/Makefile.am"; then
        printf '%s\n' \
          'elkulator_CPPFLAGS = -D_POSIX_C_SOURCE=200809L -DPI1MHZ_WOLFSSH -I$(srcdir)/pi1mhz-wolfssh/include' \
          'elkulator_SOURCES += pi1mhz_wolfssh.c' \
          'elkulator_LDADD += pi1mhz-wolfssh/lib/libwolfssh.a pi1mhz-wolfssh/lib/libwolfssl.a -lpthread -lm -lutil' \
          >> "$target/src/Makefile.am"
    fi
fi

echo "Installed Pi1MHz mailbox, BeebSCSI and AP5 Tube devices into $target"
