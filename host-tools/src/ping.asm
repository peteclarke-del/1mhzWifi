INCLUDE "src/common/mos.inc"

command_line = &70

ORG APP_START
GUARD APP_LIMIT

.start
    JSR application_check_workspace
    BCS ping_memory_safe
    JMP application_exit
.ping_memory_safe
    JSR mos_get_command_tail
    JSR tool_read_argument
    BCS ping_have_host
    LDX #LO(ping_usage)
    LDY #HI(ping_usage)
    JSR tool_print_string
    JMP application_exit
.ping_have_host
    JSR net_probe
    BCS ping_service_present
    LDX #LO(ping_no_service)
    LDY #HI(ping_no_service)
    JSR tool_print_string
    JMP application_exit
.ping_service_present
    LDA #4
    STA ping_remaining
.ping_next
    LDA #ELKWIFI_CMD_PING
    JSR net_begin
    LDX #0
.ping_copy_host
    LDA tool_argument,X
    JSR net_data_write
    BEQ ping_dispatch
    INX
    BNE ping_copy_host
.ping_dispatch
    JSR net_dispatch_start
    LDA #0
    STA ping_timeout_lo
    LDA #8
    STA ping_timeout_hi
.ping_wait
    LDA SERVICE_COMMAND
    BPL ping_result
    LDA #&7E
    JSR OSBYTE
    CPX #&FF
    BEQ ping_cancel
    LDA #19
    JSR OSBYTE
    DEC ping_timeout_lo
    BNE ping_wait
    DEC ping_timeout_hi
    BNE ping_wait
    LDA #NET_LOCAL_TIMEOUT
    BNE ping_error
.ping_result
    CMP #NET_OK
    BNE ping_error
    PHP
    SEI
    JSR net_select_command
    LDA #1
    JSR net_set_cursor_low
    JSR net_copy_selected_string
    PLP
    LDX #LO(ping_reply)
    LDY #HI(ping_reply)
    JSR tool_print_string
.ping_print_response
    LDX ping_response_index
    LDA net_rx_host,X
    BEQ ping_response_done
    INC ping_response_index
    CMP #'+'
    BEQ ping_print_response
    CMP #13
    BEQ ping_print_ms
    JSR OSWRCH
    JMP ping_print_response
.ping_print_ms
    LDX #LO(ping_ms)
    LDY #HI(ping_ms)
    JSR tool_print_string
    JMP ping_response_done
.ping_error
    JSR tool_show_error
.ping_response_done
    LDA #0
    STA ping_response_index
    DEC ping_remaining
    BEQ ping_done
    LDA #25
    STA ping_pause_count
.ping_pause
    LDA #19
    JSR OSBYTE
    DEC ping_pause_count
    BNE ping_pause
    JMP ping_next
.ping_cancel
    LDA #ELKWIFI_CMD_CANCEL
    JSR net_begin
    JSR net_dispatch_start
    LDX #LO(ping_cancelled)
    LDY #HI(ping_cancelled)
    JSR tool_print_string
.ping_done
    JMP application_exit

.ping_usage
    EQUS "Usage: *PING host", 13, 0
.ping_no_service
    EQUS "Pi1MHz network service not found.", 13, 0
.ping_reply
    EQUS "Reply from ", 0
.ping_ms
    EQUS " ms", 13, 0
.ping_cancelled
    EQUS "Ping cancelled.", 13, 0
.ping_remaining
    EQUB 0
.ping_response_index
    EQUB 0
.ping_timeout_lo
    EQUB 0
.ping_timeout_hi
    EQUB 0
.ping_pause_count
    EQUB 0

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/common/tool_common.asm"
INCLUDE "src/common/application.asm"

.end
SAVE start, end, start
