#ifndef STUB_SERVICES_H
#define STUB_SERVICES_H

#include <stdbool.h>
#include <stdint.h>

typedef void (*service_handler_t)(uint32_t command_pointer, uint32_t address,
                                  uint8_t data);

bool services_register(uint8_t first, uint8_t last, service_handler_t handler);

#endif
