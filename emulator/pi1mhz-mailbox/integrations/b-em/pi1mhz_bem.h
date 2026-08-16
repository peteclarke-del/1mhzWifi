#ifndef PI1MHZ_BEM_H
#define PI1MHZ_BEM_H

#include <stdint.h>

int pi1mhz_bem_enabled(void);
int pi1mhz_bem_handles_read(uint16_t address);
int pi1mhz_bem_handles_write(uint16_t address);
void pi1mhz_bem_snoop_read(uint16_t address);
void pi1mhz_bem_snoop_write(uint16_t address, uint8_t value);
uint8_t pi1mhz_bem_read(uint16_t address);
void pi1mhz_bem_write(uint16_t address, uint8_t value);
void pi1mhz_bem_run_host_cycles(int host_cycles);

#endif
