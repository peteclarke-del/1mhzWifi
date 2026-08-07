INCLUDE "src/common/mos.inc"

command_line = &70          \ application-owned zero-page workspace

ORG APP_START
GUARD APP_LIMIT

.start
    JSR mos_get_command_tail
    JSR build_telnet_url
    BCS term_have_url
    LDX #LO(term_usage)
    LDY #HI(term_usage)
    JSR print_string
    RTS
.term_have_url
    JSR net_probe
    BCS term_service_present
    LDX #LO(no_service_text)
    LDY #HI(no_service_text)
    JSR print_string
    RTS
.term_service_present
    JSR setup_keyboard
    LDA #4
    JSR OSWRCH
    JSR vt_init
    LDX #LO(connecting_text)
    LDY #HI(connecting_text)
    JSR print_string
    LDX #LO(url_buffer)
    LDY #HI(url_buffer)
    JSR net_url_open
    CMP #NET_OK
    BEQ term_connected
    JSR show_net_error
    JMP term_exit
.term_connected
    LDX #LO(connected_text)
    LDY #HI(connected_text)
    JSR print_string

.term_loop
    JSR net_url_read
    CMP #NET_EOF
    BNE term_check_read_ok
    JMP term_remote_closed
.term_check_read_ok
    CMP #NET_OK
    BEQ term_read_ok
    JMP term_network_error
.term_read_ok
    LDA net_length
    ORA net_length + 1
    BEQ term_poll_keyboard
    JSR net_select_rx
    LDA net_length
    STA term_rx_remaining
.term_render_rx
    LDA SERVICE_DATA
    JSR vt_process
    DEC term_rx_remaining
    BNE term_render_rx

.term_poll_keyboard
    LDA #&81
    LDX #0
    LDY #0
    JSR OSBYTE
    CPY #0
    BNE term_idle
    TXA
    CMP #29                  \ Ctrl-] is the local command prefix
    BEQ term_local_close
    CMP #&8B
    BEQ term_key_up
    CMP #&8A
    BEQ term_key_down
    CMP #&89
    BEQ term_key_right
    CMP #&88
    BEQ term_key_left
    CMP #13
    BEQ term_key_return
    STA key_buffer
    LDA #1
    BNE term_send_key
.term_key_up
    LDA #'A'
    BNE term_key_cursor
.term_key_down
    LDA #'B'
    BNE term_key_cursor
.term_key_right
    LDA #'C'
    BNE term_key_cursor
.term_key_left
    LDA #'D'
.term_key_cursor
    STA key_buffer + 2
    LDA #27
    STA key_buffer
    LDA #'['
    STA key_buffer + 1
    LDA #3
    BNE term_send_key
.term_key_return
    LDA #13
    STA key_buffer
    LDA #10
    STA key_buffer + 1
    LDA #2
.term_send_key
    LDX #LO(key_buffer)
    LDY #HI(key_buffer)
    JSR send_all
    CMP #NET_OK
    BNE term_network_error
    JMP term_loop
.term_idle
    LDA #19
    JSR OSBYTE
    JMP term_loop

.term_remote_closed
    LDX #LO(remote_closed_text)
    LDY #HI(remote_closed_text)
    JSR print_string
    JMP term_exit
.term_local_close
    LDX #LO(local_closed_text)
    LDY #HI(local_closed_text)
    JSR print_string
    JMP term_exit
.term_network_error
    JSR show_net_error
.term_exit
    JSR net_url_close
    JSR restore_keyboard
    RTS

\ Send A bytes from X/Y, retrying bounded zero/partial sends.
.send_all
    STA send_remaining
    STX send_pointer
    STY send_pointer + 1
    LDA #100
    STA send_retries
.send_all_loop
    LDA send_remaining
    BEQ send_all_ok
    LDX send_pointer
    LDY send_pointer + 1
    JSR net_url_write
    CMP #NET_OK
    BNE send_all_done
    LDA net_length
    BEQ send_all_wait
    CLC
    ADC send_pointer
    STA send_pointer
    BCC send_all_no_carry
    INC send_pointer + 1
.send_all_no_carry
    LDA send_remaining
    SEC
    SBC net_length
    STA send_remaining
    JMP send_all_loop
.send_all_wait
    LDA #19
    JSR OSBYTE
    DEC send_retries
    BNE send_all_loop
    LDA #NET_LOCAL_TIMEOUT
    RTS
.send_all_ok
    LDA #NET_OK
.send_all_done
    RTS

.setup_keyboard
    LDA #&C8
    LDX #1
    LDY #0
    JSR OSBYTE
    STX saved_escape_break
    LDA #4
    LDX #1
    LDY #0
    JSR OSBYTE
    STX saved_cursor_keys
    LDA #&E5
    LDX #0
    LDY #&FF
    JSR OSBYTE
    STX saved_escape_ascii
    LDA #&E5
    LDX #1
    LDY #0
    JSR OSBYTE
    LDA #&CA                  \ save and disable Caps Lock for terminal input
    LDX #0
    LDY #&FF
    JSR OSBYTE
    STX saved_keyboard_status
    LDA #&CA
    LDX #&10
    LDY #&EF
    JMP OSBYTE

.restore_keyboard
    LDA #&C8
    LDX saved_escape_break
    LDY #0
    JSR OSBYTE
    LDA #4
    LDX saved_cursor_keys
    LDY #0
    JSR OSBYTE
    LDA #&E5
    LDX saved_escape_ascii
    LDY #0
    JSR OSBYTE
    LDA saved_keyboard_status
    AND #&10
    TAX
    LDA #&CA
    LDY #&EF
    JMP OSBYTE

.build_telnet_url
    LDX #0
.build_telnet_prefix
    LDA telnet_prefix,X
    BEQ build_telnet_prefix_done
    STA url_buffer,X
    INX
    BNE build_telnet_prefix
.build_telnet_prefix_done
    LDY #0
.build_telnet_skip_space
    LDA (command_line),Y
    CMP #' '
    BNE build_telnet_host
    INY
    BNE build_telnet_skip_space
.build_telnet_host
    CMP #13
    BEQ build_telnet_missing
    CMP #0
    BEQ build_telnet_missing
.build_telnet_copy_host
    CMP #' '
    BEQ build_telnet_port
    CMP #13
    BEQ build_telnet_done
    CMP #0
    BEQ build_telnet_done
    STA url_buffer,X
    INX
    CPX #190
    BCS build_telnet_missing
    INY
    LDA (command_line),Y
    JMP build_telnet_copy_host
.build_telnet_port
    LDA #':'
    STA url_buffer,X
    INX
.build_telnet_skip_port_space
    INY
    LDA (command_line),Y
    CMP #' '
    BEQ build_telnet_skip_port_space
.build_telnet_copy_port
    CMP #13
    BEQ build_telnet_done
    CMP #0
    BEQ build_telnet_done
    CMP #' '
    BEQ build_telnet_done
    STA url_buffer,X
    INX
    INY
    LDA (command_line),Y
    JMP build_telnet_copy_port
.build_telnet_done
    LDA #'/'
    STA url_buffer,X
    INX
    LDA #0
    STA url_buffer,X
    SEC
    RTS
.build_telnet_missing
    CLC
    RTS

.show_net_error
    PHA
    LDX #LO(net_error_text)
    LDY #HI(net_error_text)
    JSR print_string
    PLA
    JSR print_hex
    JMP OSNEWL
.print_hex
    PHA
    LSR A
    LSR A
    LSR A
    LSR A
    JSR print_nibble
    PLA
    AND #15
.print_nibble
    CMP #10
    BCC print_nibble_digit
    ADC #'A' - 11
    JMP OSWRCH
.print_nibble_digit
    ADC #'0'
    JMP OSWRCH
.print_string
    STX print_string_read + 1
    STY print_string_read + 2
    LDY #0
.print_string_read
    LDA &FFFF,Y
    BEQ print_string_done
    JSR OSASCI
    INY
    BNE print_string_read
.print_string_done
    RTS

.term_usage
    EQUS "Usage: *TERM host [port]", 13, 0
.no_service_text
    EQUS "Pi1MHz net service not found.", 13
    EQUS "Set net_enable=1 in Pi1MHz.cfg.", 13, 0
.connecting_text
    EQUS "Connecting...", 13, 0
.connected_text
    EQUS "Connected. Ctrl-] disconnects.", 13, 0
.remote_closed_text
    EQUS 13, "Remote host closed the connection.", 13, 0
.local_closed_text
    EQUS 13, "Disconnected.", 13, 0
.net_error_text
    EQUS 13, "Network error &", 0
.telnet_prefix
    EQUS "TELNET://", 0
.url_buffer
    SKIP 192
.key_buffer
    SKIP 3
.send_pointer
    EQUW 0
.send_remaining
    EQUB 0
.send_retries
    EQUB 0
.saved_escape_break
    EQUB 0
.saved_cursor_keys
    EQUB 0
.saved_escape_ascii
    EQUB 0
.saved_keyboard_status
    EQUB 0
.term_rx_remaining
    EQUB 0

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/vt100.asm"

.end
SAVE start, end, start
