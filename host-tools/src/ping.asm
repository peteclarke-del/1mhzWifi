INCLUDE "src/common/mos.inc"

command_line = &70

ORG APP_START
GUARD APP_LIMIT

.start
    JSR mos_get_command_tail
    JSR tool_read_argument
    BCS ping_have_host
    LDX #LO(ping_usage)
    LDY #HI(ping_usage)
    JSR tool_print_string
    RTS
.ping_have_host
    JSR net_probe
    BCS ping_service_present
    LDX #LO(ping_no_service)
    LDY #HI(ping_no_service)
    JSR tool_print_string
    RTS
.ping_service_present
    LDA #4
    STA ping_remaining
.ping_next
    LDA #ELKWIFI_CMD_PING
    JSR net_begin
    LDX #0
.ping_copy_host
    LDA tool_argument,X
    STA SERVICE_DATA
    BEQ ping_dispatch
    INX
    BNE ping_copy_host
.ping_dispatch
    LDA #NET_DISPATCH
    STA SERVICE_COMMAND
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
    JSR net_select_command
    LDA #1
    STA SERVICE_ADDR_LO
    LDX #LO(ping_reply)
    LDY #HI(ping_reply)
    JSR tool_print_string
.ping_print_response
    LDA SERVICE_DATA
    BEQ ping_response_done
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
    LDA #NET_DISPATCH
    STA SERVICE_COMMAND
    LDX #LO(ping_cancelled)
    LDY #HI(ping_cancelled)
    JSR tool_print_string
.ping_done
    RTS

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
.ping_timeout_lo
    EQUB 0
.ping_timeout_hi
    EQUB 0
.ping_pause_count
    EQUB 0

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/common/tool_common.asm"

.end
SAVE start, end, start
