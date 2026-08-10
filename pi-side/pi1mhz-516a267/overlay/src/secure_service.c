/* Pi1MHz services-port wrapper for the NetTools secure ABI.
 *
 * FIQ only latches a command and publishes BUSY. All RNG, FatFs, lwIP and
 * wolfSSH work runs from the ordinary Pi1MHz poll loop.
 */
#include "Pi1MHz.h"
#include "services.h"
#include "secure_service.h"
#include "secure_service_core.h"
#include "secure_service_wolfssh.h"

#include <stdbool.h>
#include <stdint.h>

#define SEC_BUSY 0x80u

static volatile bool pending;
static volatile uint32_t pending_cp;
static volatile uint32_t pending_addr;
static bool reset_pending;
static nts_secure_service service;

_Static_assert(NTS_SEC_CAPS == SERVICE_CMD_SECURE_FIRST,
               "secure service first command mismatch");
_Static_assert(NTS_SEC_SSH_PASSWORD <= SERVICE_CMD_SECURE_LAST,
               "secure service command exceeds reserved range");

static void secure_command(uint32_t command_pointer, uint32_t addr,
                           uint8_t data)
{
    (void)data;
    pending_cp = command_pointer;
    pending_addr = addr;
    pending = true;
    Pi1MHz_MemoryWrite(addr, SEC_BUSY);
}

static void secure_poll(void)
{
    if (reset_pending) {
        nts_pi_wolfssh_reset();
        service.port = nts_pi_wolfssh_port();
        service.opaque = nts_pi_wolfssh_context();
        service.managed_ssh = nts_pi_wolfssh_ready();
        reset_pending = false;
    }

    nts_pi_wolfssh_poll();
    if (pending) {
        uint32_t cp = pending_cp;
        uint32_t addr = pending_addr;
        uint8_t result;
        pending = false;
        if (cp < DISC_RAM_BASE) {
            result = NTS_ERR_PARAM;
        } else {
            result = nts_secure_dispatch(
                &service, &Pi1MHz->JIM_ram[cp],
                &Pi1MHz->JIM_ram[DISC_RAM_BASE], DISC_RAM_SIZE);
        }
        Pi1MHz_MemoryWrite(addr, result);
    }
}

void secure_service_init(uint8_t instance, uint8_t address)
{
    (void)instance;
    (void)address;
    reset_pending = true;
    (void)services_register(SERVICE_CMD_SECURE_FIRST,
                            SERVICE_CMD_SECURE_LAST, secure_command);
    Pi1MHz_Register_Poll(secure_poll);
}
