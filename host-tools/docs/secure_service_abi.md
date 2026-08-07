# Pi1MHz NetTools secure-service ABI

The secure service reserves commands 94-113 after the 1MHzWifi service range.
Pi1MHz services range. It uses the normal page-aligned command block selected
by `&FCAA`; handle zero is at JIM `&FFF000`. All JIM addresses are offsets from
the start of the services RAM.

## Implemented foundation

### 94: `SEC_CAPS`

No input. On success the command block contains:

| Offset | Size | Meaning |
| --- | ---: | --- |
| 0 | 1 | command, 94 |
| 1 | 1 | ABI major, currently 1 |
| 2 | 1 | ABI minor, currently 1 |
| 3 | 1 | feature bits (`bit 0`: secure random, `bit 1`: managed SSH, `bit 2`: password fallback) |
| 4 | 2 | maximum SSH packet size, little endian |
| 6 | 1 | available secure contexts |
| 7 | 1 | algorithm feature bits |
| 8 | 3 | signature `NTS` |

The assembly client checks the major version and signature. A missing or old
firmware therefore fails before sending SSH negotiation packets.

### 95: `SEC_RANDOM`

| Offset | Size | Meaning |
| --- | ---: | --- |
| 0 | 1 | command, 95 |
| 1 | 2 | requested length, 1-64, little endian |
| 3 | 1 | reserved, zero |
| 4 | 4 | destination JIM address, little endian; high byte zero |

Random output is committed before success is published. The emulator reads
the operating system CSPRNG. The Pi provider reads the BCM hardware RNG,
performs startup and continuous-word checks, and withholds the capability if
either check fails; it never substitutes a timer or deterministic PRNG.

## Managed SSH commands

The Pi runs the wolfSSH/wolfCrypt transport engine. The 6502 remains
responsible for the user interface, trust decision, byte-stream lifecycle and
VT100 terminal. This keeps private keys, exchange secrets, packet MAC keys and
large packet buffers out of BBC/Electron memory.

### 96: `SEC_SSH_OPEN`

Starts or polls one non-blocking SSH connection and opens a 40x24 `vt100`
shell channel. Re-dispatch the unchanged command while result `1` is returned.

| Offset | Size | Meaning |
| --- | ---: | --- |
| 0 | 1 | command, 96 |
| 1 | 1 | flags; bit 0 accepts and persists the presented unknown host key |
| 2 | 4 | NUL-terminated `TCP://host:port/` URL address in JIM |
| 6 | 4 | NUL-terminated SSH username address in JIM |
| 10 | 6 | reserved, zero |

Result `&2C` means an unknown host. The service writes its OpenSSH-style
`SHA256:<base64>` fingerprint to JIM `&020500`. If bit 0 is subsequently set,
the exact key is appended in standard OpenSSH three-field format to
`Pi1MHz/ssh/known_hosts` and the connection is retried. The Pi provider syncs
a temporary file and renames it with rollback; the emulator uses `fsync` plus
rename. A changed key fails closed and is never overridden by bit 0. Result
`&2D` is authentication failure.

Authentication uses `Pi1MHz/ssh/id_ed25519` and
`Pi1MHz/ssh/id_ed25519.pub`. Key file bytes, decrypted key material and
signatures never cross the services mailbox.

The client tries the SD-card identity first and prompts for a password only
after public-key authentication fails.

### 97: `SEC_SSH_READ`

Same length/destination layout as net command 61. It returns decrypted stdout
from the shell channel, zero bytes while it would block, and `&20` at EOF.

### 98: `SEC_SSH_WRITE`

Same length/source layout and partial-write contract as net command 62. Input
is encrypted and authenticated by the Pi before transmission.

### 99: `SEC_SSH_CLOSE`

Closes the channel, wipes the secure context and releases its TCP connection.
It is idempotent.

### 100: `SEC_SSH_PASSWORD`

Supplies a 1-127 byte password for the next `SEC_SSH_OPEN` retry. Offset 1 is
the byte length and offset 4 is the four-byte little-endian JIM address. The
service copies the credential into its secure context and wipes the JIM source
before returning. The provider wipes its copy after authentication, failure,
close or reset. Passwords are never persisted or included in traces.

Commands 101-113 remain reserved for later keyboard-interactive auth, key
management, SFTP and HTTPS primitives. They must not be advertised until
their known-answer and end-to-end tests pass.
