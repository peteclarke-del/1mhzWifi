\ Acorn MOS entry points and shared constants.

OSRDCH = &FFE0
OSASCI = &FFE3
OSNEWL = &FFE7
OSWRCH = &FFEE
OSARGS = &FFDA
OSWORD = &FFF1
OSBYTE = &FFF4
OSCLI  = &FFF7

SERVICE_ADDR_LO = &FCA6
SERVICE_ADDR_MI = &FCA7
SERVICE_ADDR_HI = &FCA8
SERVICE_DATA    = &FCA9
SERVICE_COMMAND = &FCAA

NET_HANDLE       = 0
NET_DISPATCH     = &F0 + NET_HANDLE
NET_COMMAND_LO   = &00
NET_COMMAND_MI   = &F0
NET_COMMAND_HI   = &FF
NET_RX_LO        = &00
NET_RX_MI        = &00
NET_RX_HI        = &02
NET_TX_LO        = &00
NET_TX_MI        = &01
NET_TX_HI        = &02
NET_IO_MAX       = 240

NET_CMD_URL_OPEN  = 60
NET_CMD_URL_READ  = 61
NET_CMD_URL_WRITE = 62
NET_CMD_URL_CLOSE = 63

NET_CMD_OPEN      = 45
NET_CMD_DNS       = 46
NET_CMD_CLOSE     = 53
NET_TYPE_TCP      = 0

ELKWIFI_CMD_PING   = 88
ELKWIFI_CMD_CANCEL = 90

NET_OK      = &00
NET_PENDING = &01
NET_EOF     = &20
NET_ERR_UNSUPPORTED = &27
NET_BUSY    = &80

NET_LOCAL_NO_SERVICE = &29
NET_LOCAL_TIMEOUT    = &2A
NET_LOCAL_PROTOCOL   = &2B
NET_HOSTKEY_UNKNOWN  = &2C
NET_AUTH_FAILED      = &2D

\ The public loader occupies &2000-&21FF, so main images start beyond it. The
\ loader selects MODE 4 before MOS reads these images from the filing system.
APP_START = &2200
APP_LIMIT = &5800

\ Diagnostic handoff below the main image. The public loader writes the
\ pre-MODE memory envelope and commits the two-byte signature last.
LOADER_COOKIE = &21F0
