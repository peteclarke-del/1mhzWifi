#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
prefix=${WOLFSSH_PREFIX:-/tmp/wolf-install}
test_root=$(mktemp -d /tmp/pi1mhz-wolfssh.XXXXXX)
server_pid=
cleanup() {
    if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; fi
    rm -rf -- "$test_root"
}
trap cleanup EXIT

start_server() {
    local directory=$1 requested_port=${2:-0} expect_session=${3:-1}
    : > "$test_root/port"
    python3 "$project_dir/tests/paramiko_test_server.py" \
        "$directory" "$test_root/port" "$requested_port" 1 0 \
        "$expect_session" &
    server_pid=$!
    for _ in $(seq 1 100); do
        [[ -s "$test_root/port" ]] && break
        sleep 0.02
    done
    [[ -s "$test_root/port" ]]
}

ssh-keygen -q -t ed25519 -N '' -f "$test_root/id_ed25519"
ssh-keygen -q -t rsa -b 2048 -N '' -f "$test_root/host_rsa"
if [[ ${PI1MHZ_SSH_DEBUG:-0} != 0 ]]; then
    ssh-keygen -lf "$test_root/host_rsa.pub" -E sha256 >&2
fi
python3 "$project_dir/tests/paramiko_test_server.py" \
    "$test_root" "$test_root/port" 0 2 1 1 &
server_pid=$!
for _ in $(seq 1 100); do [[ -s "$test_root/port" ]] && break; sleep 0.02; done
port=$(<"$test_root/port")
"$project_dir/build/wolfssh-probe" "$port" "$test_root"
wait "$server_pid"
server_pid=

password_client=$test_root/password-client
mkdir "$password_client"
cp "$test_root/id_ed25519" "$test_root/id_ed25519.pub" \
    "$test_root/host_rsa" "$password_client/"
: > "$test_root/port"
python3 "$project_dir/tests/paramiko_test_server.py" \
    "$password_client" "$test_root/port" 0 2 1 1 password secret &
server_pid=$!
for _ in $(seq 1 100); do [[ -s "$test_root/port" ]] && break; sleep 0.02; done
password_port=$(<"$test_root/port")
"$project_dir/build/wolfssh-probe" \
    "$password_port" "$password_client" password
wait "$server_pid"
server_pid=

: > "$test_root/port"
python3 "$project_dir/tests/paramiko_test_server.py" \
    "$password_client" "$test_root/port" 0 2 1 1 mixed secret &
server_pid=$!
for _ in $(seq 1 100); do [[ -s "$test_root/port" ]] && break; sleep 0.02; done
mixed_port=$(<"$test_root/port")
"$project_dir/build/wolfssh-probe" \
    "$mixed_port" "$password_client" password
wait "$server_pid"
server_pid=
ssh-keygen -F "[127.0.0.1]:$port" -f "$test_root/known_hosts" >/dev/null
trusted_hash=$(sha256sum "$test_root/known_hosts" | awk '{print $1}')

changed=$test_root/changed
mkdir "$changed"
ssh-keygen -q -t ed25519 -N '' -f "$changed/id_ed25519"
ssh-keygen -q -t rsa -b 2048 -N '' -f "$changed/host_rsa"
start_server "$changed" "$port" 0
"$project_dir/build/wolfssh-probe" "$port" "$test_root" changed-host
wait "$server_pid"
server_pid=
[[ "$(sha256sum "$test_root/known_hosts" | awk '{print $1}')" == \
    "$trusted_hash" ]]

bad_client=$test_root/bad-client
mkdir "$bad_client"
ssh-keygen -q -t ed25519 -N '' -f "$bad_client/id_ed25519"
cp "$test_root/known_hosts" "$bad_client/known_hosts"
start_server "$test_root" "$port" 0
"$project_dir/build/wolfssh-probe" "$port" "$bad_client" auth-fail
wait "$server_pid"
server_pid=
