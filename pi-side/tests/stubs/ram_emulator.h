#ifndef STUB_RAM_EMULATOR_H
#define STUB_RAM_EMULATOR_H

/* The services mailbox scratch lives at DISC_RAM_BASE in JIM. Only the
 * relative arithmetic matters to the transport, so the harness fixes a value
 * and uses it consistently on both sides of the call. */
#define DISC_RAM_BASE 0x10000u
#define DISC_RAM_SIZE 0x10000u

#endif
