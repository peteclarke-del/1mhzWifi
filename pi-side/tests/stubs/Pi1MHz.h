#ifndef STUB_PI1MHZ_H
#define STUB_PI1MHZ_H

/* Build-host stubs mirroring the parts of the Pi1MHz kernel headers that the
 * media service transport uses. They exist so media_service.c can be compiled
 * and driven off-target; the real declarations come from the upstream tree
 * when the kernel is built, and this harness is not a substitute for that. */

#include <stdint.h>

#define PI1MHZ_JIM_RAM_SIZE (1u << 20)

typedef struct {
    uint8_t JIM_ram[PI1MHZ_JIM_RAM_SIZE];
} pi1mhz_stub_t;

extern pi1mhz_stub_t *Pi1MHz;

void Pi1MHz_MemoryWrite(uint32_t address, uint8_t value);

#endif
