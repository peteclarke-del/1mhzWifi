#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
repo_dir=$(CDPATH= cd -- "$project_dir/.." && pwd)
elkulator_source=${ELKULATOR_SOURCE:-"$repo_dir/../elkChat/emulator/elkulator"}
builder_image=${ELKULATOR_BUILDER_IMAGE:-elkchat-elkulator-builder:latest}
display_name=${DISPLAY:-:0}
authority_file=${XAUTHORITY:-}
test_root=$(mktemp -d /tmp/pi1mhz-elkulator-smoke.XXXXXX)
source_copy=$test_root/elkulator
trace_dir=$test_root/traces
elk_roms_dir=${ELK_ROMS_DIR:-"$repo_dir/../elk_roms"}
tube_archive=$elk_roms_dir/electron_tube.zip

cleanup() {
    rm -rf -- "$test_root"
}
trap cleanup EXIT

if [[ ! -f "$elkulator_source/src/mem.c" ]]; then
    echo "Elkulator source not found: $elkulator_source" >&2
    exit 2
fi
if [[ -z "$authority_file" || ! -f "$authority_file" ]]; then
    echo "XAUTHORITY must name a readable X11 authority file" >&2
    exit 2
fi
if [[ ! -f "$tube_archive" ]]; then
    echo "Electron Tube ROM archive not found: $tube_archive" >&2
    echo "Set ELK_ROMS_DIR to the directory containing electron_tube.zip" >&2
    exit 2
fi

mkdir -p "$source_copy" "$trace_dir"
chmod 0777 "$trace_dir"
cp -a "$elkulator_source/." "$source_copy/"
mkdir -p "$source_copy/roms"
unzip -p "$tube_archive" 6502tube_120.rom \
    >"$source_copy/roms/6502tube_120.rom"
"$repo_dir/emulator/pi1mhz-mailbox/integrations/elkulator/install.sh" \
    "$source_copy"

# The smoke device supersedes these Elkulator peripherals during this run.
sed -i \
    's/^enable_elkwifi = .*/enable_elkwifi = 0/; s/^sound_internal = .*/sound_internal = 0/; s/^sound_ddnoise = .*/sound_ddnoise = 0/' \
    "$source_copy/elk.cfg"

docker run --rm -v "$source_copy:/work" -w /work "$builder_image" \
    bash -lc 'autoreconf -fi && ./configure >/tmp/configure.log && make -s -j2'

run_client() {
    local name=$1
    local disc=$2
    local tube=$3
    local log=$trace_dir/$name.elkulator.log
    local tube_args=()
    if [[ "$tube" == 1 ]]; then
        tube_args=(-tube6502 /work/roms/6502tube_120.rom)
    fi
    timeout 30s docker run --rm --ipc=host \
        -e DISPLAY="$display_name" -e XAUTHORITY=/tmp/xauth \
        -e PI1MHZ_MAILBOX=fixture \
        -e PI1MHZ_TRACE="/out/$name.trace" \
        -e PI1MHZ_EXIT_ON_CLOSE=1 \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v "$authority_file:/tmp/xauth:ro" \
        -v "$source_copy:/work" \
        -v "$project_dir/build:/discs:ro" \
        -v "$trace_dir:/out" \
        -w /work "$builder_image" \
        ./elkulator -disc "/discs/$disc" -autoboot "${tube_args[@]}" >"$log" 2>&1 || {
            cat "$log" >&2
            if [[ -f "$trace_dir/$name.trace" ]]; then
                echo "--- $name mailbox trace ---" >&2
                cat "$trace_dir/$name.trace" >&2
            fi
            return 1
        }
}

run_client telnet-off telnet-smoke.ssd 0
run_client telnet-on telnet-smoke.ssd 1
run_client ssh-off ssh-smoke.ssd 0
run_client ssh-on ssh-smoke.ssd 1

for state in off on; do
    telnet_trace=$trace_dir/telnet-$state.trace
    ssh_trace=$trace_dir/ssh-$state.trace
    grep -q $'^OPEN\t0\tTELNET://fixture/' "$telnet_trace"
    grep -q $'^CLOSE\t0\tTELNET://fixture/' "$telnet_trace"
    grep -q $'^SSH_OPEN\t0\tTCP://fixture:22/' "$ssh_trace"
    grep -q $'^SSH_USER\t0\ttest' "$ssh_trace"
    grep -q $'^CLOSE\t0\tTCP://fixture:22/' "$ssh_trace"

    telnet_read=$(awk -F '\t' '$1 == "READ" { printf "%s", $3 }' "$telnet_trace")
    ssh_read=$(awk -F '\t' '$1 == "READ" { printf "%s", $3 }' "$ssh_trace")

    [[ "$telnet_read" == *"5069314d487a206d61696c626f78204f4b"* ]]
    [[ "$ssh_read" == *"5069314d487a20535348207368656c6c204f4b"* ]]
done

echo "Full Elkulator TELNET/SSH Pi1MHz mailbox smoke tests, Tube off/on: OK"
