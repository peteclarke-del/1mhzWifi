/* Media service transport for the Pi1MHz services mailbox.
 *
 * `*UEF CAT`, `*SSD CAT` and the extraction commands are answered by
 * media_service_core.c, which owns every container and session decision and
 * performs no Pi1MHz register access. This file is the binding the core's
 * header names: it moves a command block and a reply between JIM and the core.
 *
 * Unlike ftp_service.c this is synchronous. The session works on an image
 * already resident in Pi memory, so there is nothing to wait for and no
 * pending or cancel state to carry.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "Pi1MHz.h"
#include "elkwifi_service.h"
#include "media_service.h"
#include "media_service_core.h"
#include "ram_emulator.h"
#include "services.h"

static media_service media;

/* The command block is the command byte followed by up to three arguments,
 * matching every other service on this mailbox. */
#define MEDIA_COMMAND_BYTES 4u

void media_service_command(uint32_t command_pointer, uint32_t address,
                           uint8_t data)
{
   uint32_t cp = command_pointer - 0xff0000u + DISC_RAM_BASE;
   uint8_t command[MEDIA_COMMAND_BYTES];
   uint8_t reply[MEDIA_SVC_REPLY_MAX];
   size_t reply_length = 0u;
   uint8_t status;
   (void)data;

   memcpy(command, &Pi1MHz->JIM_ram[cp], sizeof command);

   /* An open binds whatever the host last uploaded through the incremental
    * window protocol. The core deliberately separates binding from dispatch,
    * so a bare MEDIA_OPEN reports what the bound image holds rather than
    * carrying the container in the command. */
   if (command[0] == MEDIA_CMD_OPEN) {
      size_t length = 0u;
      const uint8_t *image = elkwifi_uef_stream_image(&length);
      if (image == NULL) {
         Pi1MHz_MemoryWrite(address, MEDIA_SVC_ERR_PARAM);
         return;
      }
      status = media_service_open(&media, image, length);
      if (status != MEDIA_SVC_OK) {
         Pi1MHz_MemoryWrite(address, status);
         return;
      }
   }

   status = media_service_dispatch(&media, command, reply, sizeof reply,
                                   &reply_length);
   if (reply_length > MEDIA_SVC_REPLY_MAX)
      reply_length = MEDIA_SVC_REPLY_MAX;
   if (reply_length != 0u)
      memcpy(&Pi1MHz->JIM_ram[cp + 1u], reply, reply_length);
   /* Catalogue lines are read as text, so terminate what was written. A read
    * window is length-prefixed and the host ignores anything past it. */
   Pi1MHz->JIM_ram[cp + 1u + reply_length] = 0u;
   Pi1MHz_MemoryWrite(address, status);
}

void media_service_init(void)
{
   media_service_reset(&media);
   (void)services_register(MEDIA_SVC_CMD_FIRST, MEDIA_SVC_CMD_LAST,
                           media_service_command);
}
