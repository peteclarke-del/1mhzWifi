#!/bin/sh -e
# Host compile check for the interactive FTP service (ftp_service.c).
#
# The 1MHzWifi integration supplies this file and links it into the kernel, so
# nothing else in this tree compiles it and an ARM toolchain is the only thing
# that would notice a type or warning regression when these headers move.
# There is no behavioural harness here: the service is almost entirely lwIP
# callbacks and FatFs, and stubbing enough of both to drive it would be a
# second implementation. What this does catch is the thing that actually
# breaks - an upstream header changing under a file upstream does not build.
# NB: set -e here too - the shebang -e is ignored under "sh script.sh".
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=${SRC_DIR:-$HERE/../..}
B=$(mktemp -d)
trap 'rm -rf "$B"' EXIT

mkdir -p "$B/rpi"
cp "$SRC"/ftp_service.c "$SRC"/ftp_service.h "$SRC"/services.h "$B/"
# The services stubs give Pi1MHz.h and ram_emulator.h; the net stubs give
# lwIP and the mock system timer. Borrowed rather than copied, so a stub that
# drifts from the real header drifts for every suite at once.
cp -r "$SRC"/tests/services/stubs/. "$B/"
cp -r "$SRC"/tests/net/stubs/lwip "$B/"
cp "$SRC"/tests/net/stubs/rpi/systimer.h "$B/rpi/"
cp "$SRC"/tests/net/stubs/wifi/wifi_lwip.h "$B/wifi/"
cat > "$B/rpi/asm-helpers.h" <<'HEADER'
#ifndef ASM_HELPERS_H
#define ASM_HELPERS_H
/* FIQ masking around the shared JIM cursor. The host tests are single
   threaded, so these are the identity. */
static inline unsigned int _disable_interrupts_cspr(void) { return 0u; }
static inline void _restore_cpsr(unsigned int cpsr) { (void)cpsr; }
#endif
HEADER

echo "== FTP service compiles warning-free against the firmware headers =="
gcc -std=gnu2x -Wall -Wextra -Wconversion -Wshadow -Werror -g \
    -I"$B" -c "$B/ftp_service.c" -o "$B/ftp_service.o"
echo "  ok: ftp_service.c builds against Pi1MHz's headers"

# The range it claims has to be the one services.h reserves for it, and the
# one the host ROM sends. A mismatch here is silent on both sides.
echo "== FTP command range agrees with services.h =="
gcc -std=gnu2x -Wall -Wextra -Werror -I"$B" -o "$B/range" -x c - <<'RANGE'
#include <stdio.h>
#include "services.h"
#include "ftp_service.h"
_Static_assert(FTP_CMD_FIRST == SERVICE_CMD_FTP_FIRST, "FTP first differs");
_Static_assert(FTP_CMD_LAST  == SERVICE_CMD_FTP_LAST,  "FTP last differs");
_Static_assert(FTP_CMD_FIRST == 114u, "the host ROM sends 114");
_Static_assert(FTP_CMD_LAST  == 119u, "the host ROM sends up to 119");
int main(void) { printf("  ok: FTP owns %u..%u\n",
                        FTP_CMD_FIRST, FTP_CMD_LAST); return 0; }
RANGE
"$B/range"

echo "FTP TESTS PASSED"
