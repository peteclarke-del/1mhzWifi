#ifndef PI1MHZ_MEDIA_SERVICE_H
#define PI1MHZ_MEDIA_SERVICE_H

#include <stdint.h>

/* Binds media_service_core to the Pi1MHz services mailbox.
 *
 * The core owns every container and session decision and touches no Pi1MHz
 * register, so it unit tests on the build host. This file is only the
 * transport: it reads a command block out of JIM, calls the core, and writes
 * the reply and status back. */

#define MEDIA_SVC_CMD_FIRST 120u
#define MEDIA_SVC_CMD_LAST  124u

void media_service_init(void);
void media_service_command(uint32_t command_pointer, uint32_t address,
                           uint8_t data);

#endif
