#ifndef PI1MHZ_ELKULATOR_H
#define PI1MHZ_ELKULATOR_H

#include <stdint.h>

int pi1mhz_elkulator_enabled(void);
int pi1mhz_elkulator_handles(uint16_t address);
uint8_t pi1mhz_elkulator_read(uint16_t address);
void pi1mhz_elkulator_write(uint16_t address, uint8_t value);

#endif
