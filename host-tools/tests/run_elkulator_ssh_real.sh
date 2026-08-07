#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
repo_dir=$(CDPATH= cd -- "$project_dir/.." && pwd)
elkulator_source=${ELKULATOR_SOURCE:-"$repo_dir/../elkChat/emulator/elkulator"}
builder_image=${ELKULATOR_BUILDER_IMAGE:-elkchat-elkulator-builder:latest}
prefix=${WOLFSSH_PREFIX:-/tmp/wolf-install}
display_name=${DISPLAY:-:0}
authority_file=${XAUTHORITY:-}
test_root=$(mktemp -d /tmp/pi1mhz-elkulator-real.XXXXXX)
source_copy=$test_root/elkulator
trace_dir=$test_root/traces
ssh_dir=$test_root/ssh
server_pid=

cleanup() {
    if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; fi
    rm -rf -- "$test_root"
}
trap cleanup EXIT
test -f "$elkulator_source/src/mem.c"
test -f "$authority_file"
mkdir -p "$source_copy" "$trace_dir" "$ssh_dir"
chmod 0777 "$trace_dir" "$ssh_dir"
cp -a "$elkulator_source/." "$source_copy/"

ssh-keygen -q -t ed25519 -N '' -f "$ssh_dir/id_ed25519"
ssh-keygen -q -t rsa -b 2048 -N '' -f "$ssh_dir/host_rsa"
fingerprint=$(ssh-keygen -lf "$ssh_dir/host_rsa.pub" -E sha256 | awk '{print $2}')
if [[ ${PI1MHZ_SSH_DEBUG:-0} != 0 ]]; then
    echo "known host [127.0.0.1]:22022 $fingerprint" >&2
fi
awk '{print "[127.0.0.1]:22022 " $1 " " $2}' \
    "$ssh_dir/host_rsa.pub" > "$ssh_dir/known_hosts"
python3 "$project_dir/tests/paramiko_test_server.py" \
    "$ssh_dir" "$test_root/port" 22022 1 0 &
server_pid=$!
for _ in $(seq 1 100); do
    [[ -s "$test_root/port" ]] && break
    sleep 0.02
done
[[ "$(<"$test_root/port")" == 22022 ]]

PI1MHZ_WOLFSSH_PREFIX="$prefix" \
    "$repo_dir/emulator/pi1mhz-mailbox/integrations/elkulator/install.sh" \
    "$source_copy"
sed -i \
    's/^enable_elkwifi = .*/enable_elkwifi = 0/; s/^sound_internal = .*/sound_internal = 0/; s/^sound_ddnoise = .*/sound_ddnoise = 0/' \
    "$source_copy/elk.cfg"
docker run --rm -v "$source_copy:/work" -w /work "$builder_image" \
    bash -lc 'autoreconf -fi && ./configure >/tmp/configure.log && make -s -j2'

timeout 45s docker run --rm --ipc=host --network=host \
    -e DISPLAY="$display_name" -e XAUTHORITY=/tmp/xauth \
    -e PI1MHZ_MAILBOX=live -e PI1MHZ_SSH_DIR=/ssh \
    -e PI1MHZ_SSH_DEBUG="${PI1MHZ_SSH_DEBUG:-0}" \
    -e PI1MHZ_TRACE=/out/ssh-real.trace -e PI1MHZ_EXIT_ON_CLOSE=1 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "$authority_file:/tmp/xauth:ro" -v "$source_copy:/work" \
    -v "$project_dir/build:/discs:ro" -v "$trace_dir:/out" \
    -v "$ssh_dir:/ssh" -w /work "$builder_image" \
    ./elkulator -disc /discs/ssh-real-smoke.ssd -autoboot
wait "$server_pid"
server_pid=

trace=$trace_dir/ssh-real.trace
grep -q $'^SSH_OPEN\t0\tTCP://127.0.0.1:22022/' "$trace"
grep -q $'^SSH_USER\t0\ttest' "$trace"
grep -q $'^CLOSE\t0\tTCP://127.0.0.1:22022/' "$trace"
read_hex=$(awk -F '\t' '$1 == "READ" { printf "%s", $3 }' "$trace")
[[ "$read_hex" == *"5245414c20535348204f4b"* ]]
echo "Full Elkulator assembled SSD -> real wolfSSH server: OK"
