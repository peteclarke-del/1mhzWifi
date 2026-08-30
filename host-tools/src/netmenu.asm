INCLUDE "src/common/mos.inc"

ORG APP_START
GUARD APP_LIMIT

.start
    JSR application_check_workspace
    BCS netmenu_memory_safe
    JMP application_exit
.netmenu_memory_safe
    LDX #LO(menu_text)
    LDY #HI(menu_text)
    STX menu_read + 1
    STY menu_read + 2
.menu_loop
    LDY #0
.menu_read
    LDA &FFFF,Y
    BEQ menu_done
    JSR OSASCI
    INC menu_read + 1
    BNE menu_loop
    INC menu_read + 2
    JMP menu_loop
.menu_done
    JMP application_exit

.menu_text
    EQUS 12, "Pi1MHz Network Tools", 13
    EQUS "====================", 13, 13
    EQUS "*TELNET host [port]", 13
    EQUS "  Telnet with VT100 display", 13, 13
    EQUS "*SSH user@host [port]", 13
    EQUS "  SSH-2 VT100 client", 13, 13
    EQUS "*SFTP user@host [port]", 13
    EQUS "  Interactive secure file transfer", 13, 13
    EQUS "*HWDTEST", 13
    EQUS "  Compare emulator and hardware", 13, 13
    EQUS "Requires net_enable=1 in Pi1MHz.cfg", 13
    EQUS "Programs execute on the I/O processor.", 13, 0

INCLUDE "src/common/application.asm"
.end
SAVE start, end, start
