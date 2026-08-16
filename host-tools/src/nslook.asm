INCLUDE "src/common/mos.inc"

command_line = &70

ORG APP_START
GUARD APP_LIMIT

.start
    JSR application_check_workspace
    BCS nslook_memory_safe
    JMP application_exit
.nslook_memory_safe
    JSR mos_get_command_tail
    JSR tool_read_argument
    BCS nslook_have_host
    LDX #LO(nslook_usage)
    LDY #HI(nslook_usage)
    JSR tool_print_string
    JMP application_exit
.nslook_have_host
    JSR net_probe
    BCS nslook_service_present
    LDX #LO(nslook_no_service)
    LDY #HI(nslook_no_service)
    JSR tool_print_string
    JMP application_exit
.nslook_service_present
    LDA #NET_CMD_OPEN
    JSR net_begin
    LDA #NET_TYPE_TCP
    JSR net_data_write
    JSR net_dispatch
    CMP #NET_OK
    BNE nslook_error
    LDA #NET_CMD_DNS
    JSR net_begin
    LDX #0
.nslook_copy_host
    LDA tool_argument,X
    JSR net_data_write
    BEQ nslook_resolve
    INX
    BNE nslook_copy_host
.nslook_resolve
    JSR net_dispatch_wait
    CMP #NET_OK
    BNE nslook_error_close
    PHP
    SEI
    JSR net_select_command
    LDA #4
    JSR net_set_cursor_low
    LDX #0
.nslook_copy_ip
    JSR net_data_read
    STA nslook_address,X
    INX
    CPX #4
    BNE nslook_copy_ip
    PLP
    LDX #LO(nslook_prefix)
    LDY #HI(nslook_prefix)
    JSR tool_print_string
    LDX #0
.nslook_print_ip
    STX nslook_octet
    LDA nslook_address,X
    JSR tool_print_u8
    LDX nslook_octet
    INX
    CPX #4
    BEQ nslook_newline
    LDA #'.'
    JSR OSWRCH
    JMP nslook_print_ip
.nslook_newline
    JSR OSNEWL
    LDA #NET_CMD_CLOSE
    JSR net_begin
    JSR net_dispatch_wait
    JMP application_exit
.nslook_error_close
    PHA
    LDA #NET_CMD_CLOSE
    JSR net_begin
    JSR net_dispatch_wait
    PLA
.nslook_error
    JSR tool_show_error
    JMP application_exit

.nslook_usage
    EQUS "Usage: *NSLOOK host", 13, 0
.nslook_no_service
    EQUS "Pi1MHz network service not found.", 13, 0
.nslook_prefix
    EQUS "Address: ", 0
.nslook_octet
    EQUB 0
.nslook_address
    SKIP 4

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/common/tool_common.asm"
INCLUDE "src/common/application.asm"

.end
SAVE start, end, start
