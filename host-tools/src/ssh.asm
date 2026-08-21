INCLUDE "src/common/mos.inc"

command_line = &70

ORG APP_START
GUARD APP_LIMIT

.start
    JSR application_check_workspace
    BCS ssh_memory_safe
    JMP application_exit
.ssh_memory_safe
    JSR mos_get_command_tail
    JSR build_ssh_target
    BCS ssh_have_target
    LDX #LO(usage_text)
    LDY #HI(usage_text)
    JSR print_string
    JMP application_exit
.ssh_have_target
    JSR net_probe
    BCS ssh_service_present
    LDX #LO(no_service_text)
    LDY #HI(no_service_text)
    JSR print_string
    JMP application_exit
.ssh_service_present
    JSR secure_probe
    CMP #NET_OK
    BEQ ssh_probe_secure_ok
    CMP #NET_LOCAL_TIMEOUT
    BEQ ssh_secure_timeout
    JMP ssh_secure_error
.ssh_secure_timeout
    LDX #LO(secure_timeout_text)
    LDY #HI(secure_timeout_text)
    JSR print_string
    LDA #NET_LOCAL_TIMEOUT
    JSR show_error
    JMP application_exit
.ssh_probe_secure_ok
    LDA secure_features
    AND #2
    BNE ssh_managed_available
    LDA #NET_ERR_UNSUPPORTED
    JMP ssh_secure_error
.ssh_managed_available
    LDA #0
    STA password_attempted
    LDX #LO(url_buffer)
    LDY #HI(url_buffer)
    JSR secure_copy_url
    LDX #LO(username_buffer)
    LDY #HI(username_buffer)
    JSR secure_copy_user
    LDX #LO(connecting_text)
    LDY #HI(connecting_text)
    JSR print_string
    LDA #0
    JSR secure_ssh_open
    CMP #NET_HOSTKEY_UNKNOWN
    BNE ssh_open_result
    JSR ssh_confirm_host_key
    BCC ssh_declined
    LDA #1                    \ accept and persist this host key on Pi SD
    JSR secure_ssh_open
.ssh_open_result
    CMP #NET_OK
    BEQ ssh_connected
    CMP #NET_AUTH_FAILED
    BNE ssh_failed
.ssh_try_password
    LDA password_attempted
    BNE ssh_auth_failed
    LDA secure_features
    AND #4
    BEQ ssh_auth_failed
    JSR ssh_prompt_password
    BCC ssh_auth_failed
    STA password_length
    LDX #LO(password_buffer)
    LDY #HI(password_buffer)
    JSR secure_ssh_password
    PHA
    JSR ssh_wipe_password
    PLA
    CMP #NET_OK
    BNE ssh_failed
    LDA #1
    STA password_attempted
    LDX #LO(password_auth_text)
    LDY #HI(password_auth_text)
    JSR print_string
    LDA #0
    JSR secure_ssh_open
    CMP #NET_HOSTKEY_UNKNOWN
    BNE ssh_password_open_result
    JSR ssh_confirm_host_key
    BCC ssh_declined
    LDA #1
    JSR secure_ssh_open
.ssh_password_open_result
    CMP #NET_OK
    BEQ ssh_connected
    CMP #NET_AUTH_FAILED
    BNE ssh_failed
.ssh_auth_failed
    LDX #LO(auth_failed_text)
    LDY #HI(auth_failed_text)
    JSR print_string
    JMP ssh_close
.ssh_failed
    JSR show_error
    JMP ssh_close
.ssh_declined
    LDX #LO(host_declined_text)
    LDY #HI(host_declined_text)
    JSR print_string
    JMP ssh_close

.ssh_connected
    JSR setup_keyboard
    LDA #1
    STA keyboard_active
    LDA #4
    JSR OSWRCH
    JSR vt_init
    LDX #LO(connected_text)
    LDY #HI(connected_text)
    JSR print_string

.ssh_loop
    JSR secure_ssh_read
    CMP #NET_EOF
    BNE ssh_not_eof
    JMP ssh_remote_closed
.ssh_not_eof
    CMP #NET_OK
    BEQ ssh_read_ok
    JMP ssh_network_error
.ssh_read_ok
    LDA net_length
    ORA net_length + 1
    BEQ ssh_poll_keyboard
    JSR net_copy_rx_to_host
    LDA #0
    STA ssh_rx_index
    LDA net_length
    STA ssh_rx_remaining
.ssh_render_rx
    LDX ssh_rx_index
    LDA net_rx_host,X
    INC ssh_rx_index
    JSR vt_process
    DEC ssh_rx_remaining
    BNE ssh_render_rx

.ssh_poll_keyboard
    LDA #&81
    LDX #0
    LDY #0
    JSR OSBYTE
    CPY #0
    BNE ssh_idle
    TXA
    CMP #29
    BEQ ssh_local_close
    CMP #&8B
    BEQ ssh_key_up
    CMP #&8A
    BEQ ssh_key_down
    CMP #&89
    BEQ ssh_key_right
    CMP #&88
    BEQ ssh_key_left
    CMP #13
    BEQ ssh_key_return
    STA key_buffer
    LDA #1
    BNE ssh_send_key
.ssh_key_up
    LDA #'A'
    BNE ssh_key_cursor
.ssh_key_down
    LDA #'B'
    BNE ssh_key_cursor
.ssh_key_right
    LDA #'C'
    BNE ssh_key_cursor
.ssh_key_left
    LDA #'D'
.ssh_key_cursor
    STA key_buffer + 2
    LDA #27
    STA key_buffer
    LDA #'['
    STA key_buffer + 1
    LDA #3
    BNE ssh_send_key
.ssh_key_return
    LDA #13
    STA key_buffer
    LDA #1
.ssh_send_key
    LDX #LO(key_buffer)
    LDY #HI(key_buffer)
    JSR ssh_send_all
    CMP #NET_OK
    BNE ssh_network_error
    JMP ssh_loop
.ssh_idle
    LDA #19
    JSR OSBYTE
    JMP ssh_loop

.ssh_remote_closed
    LDX #LO(remote_closed_text)
    LDY #HI(remote_closed_text)
    JSR print_string
    JMP ssh_close
.ssh_local_close
    LDX #LO(local_closed_text)
    LDY #HI(local_closed_text)
    JSR print_string
    JMP ssh_close
.ssh_network_error
    JSR show_error
.ssh_close
    JSR secure_ssh_close
    LDA keyboard_active
    BEQ ssh_close_done
    JSR restore_keyboard
.ssh_close_done
    JMP application_exit
.ssh_secure_error
    PHA
    LDX #LO(secure_required_text)
    LDY #HI(secure_required_text)
    JSR print_string
    PLA
    JSR show_error
    JMP application_exit

\ The secure service leaves `SHA256:<base64>` at JIM &020500 when an
\ unknown key is encountered. It has already cryptographically verified the
\ exchange; this prompt controls TOFU persistence in Pi1MHz/ssh/known_hosts.
.ssh_confirm_host_key
    LDX #LO(unknown_host_text)
    LDY #HI(unknown_host_text)
    JSR print_string
    PHP
    SEI
    LDA #0
    LDX #5
    LDY #2
    JSR net_select_address
    JSR net_copy_selected_string
    PLP
    LDX #0
.ssh_print_fingerprint
    LDA net_rx_host,X
    BEQ ssh_fingerprint_done
    INX
    STX ssh_fingerprint_index
    JSR OSASCI
    LDX ssh_fingerprint_index
    JMP ssh_print_fingerprint
.ssh_fingerprint_done
    LDX #LO(accept_text)
    LDY #HI(accept_text)
    JSR print_string
    JSR OSRDCH
    PHA
    JSR OSNEWL
    PLA
    AND #&DF
    CMP #'Y'
    BEQ ssh_host_accepted
    CLC
    RTS
.ssh_host_accepted
    SEC
    RTS

\ Read a password without echo. Return C set and A=length on Return; Escape or
\ an empty password cancels. Delete/backspace edits the hidden buffer.
.ssh_prompt_password
    LDX #LO(password_text)
    LDY #HI(password_text)
    JSR print_string
    LDX #0
.ssh_password_read
    JSR OSRDCH
    CMP #13
    BEQ ssh_password_enter
    CMP #27
    BEQ ssh_password_cancel
    CMP #8
    BEQ ssh_password_delete
    CMP #127
    BEQ ssh_password_delete
    CMP #32
    BCC ssh_password_read
    CPX #63
    BCS ssh_password_read
    STA password_buffer,X
    INX
    BNE ssh_password_read
.ssh_password_delete
    CPX #0
    BEQ ssh_password_read
    DEX
    LDA #0
    STA password_buffer,X
    JMP ssh_password_read
.ssh_password_enter
    STX password_length
    JSR OSNEWL
    LDX password_length
    CPX #0
    BEQ ssh_password_cancel_no_newline
    TXA
    SEC
    RTS
.ssh_password_cancel
    JSR OSNEWL
.ssh_password_cancel_no_newline
    JSR ssh_wipe_password
    CLC
    RTS

.ssh_wipe_password
    LDX #0
    LDA #0
.ssh_wipe_password_loop
    STA password_buffer,X
    INX
    CPX #64
    BCC ssh_wipe_password_loop
    STA password_length
    RTS

.ssh_send_all
    STA send_remaining
    STX send_pointer
    STY send_pointer + 1
    LDA #100
    STA send_retries
.ssh_send_loop
    LDX send_pointer
    LDY send_pointer + 1
    LDA send_remaining
    JSR secure_ssh_write
    CMP #NET_OK
    BNE ssh_send_done
    LDA net_length
    BEQ ssh_send_wait
    CLC
    ADC send_pointer
    STA send_pointer
    BCC ssh_send_no_carry
    INC send_pointer + 1
.ssh_send_no_carry
    LDA send_remaining
    SEC
    SBC net_length
    STA send_remaining
    BNE ssh_send_loop
    LDA #NET_OK
.ssh_send_done
    RTS
.ssh_send_wait
    LDA #19
    JSR OSBYTE
    DEC send_retries
    BNE ssh_send_loop
    LDA #NET_LOCAL_TIMEOUT
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

\ Parse user@host [port]. Requiring an explicit user avoids surprising Pi-SD
\ key selection and keeps credentials out of BBC RAM.
.build_ssh_target
    LDY #0
.build_skip_space
    LDA (command_line),Y
    CMP #' '
    BNE build_username
    INY
    BNE build_skip_space
.build_username
    LDX #0
.build_username_loop
    CMP #'@'
    BEQ build_username_done
    CMP #13
    BEQ build_early_missing
    CMP #0
    BEQ build_early_missing
    CMP #' '
    BEQ build_early_missing
    STA username_buffer,X
    INX
    CPX #63
    BCS build_early_missing
    INY
    LDA (command_line),Y
    JMP build_username_loop
.build_early_missing
    JMP build_target_missing
.build_username_done
    LDA #0
    STA username_buffer,X
    INY
    LDX #0
.build_prefix
    LDA tcp_prefix,X
    BEQ build_prefix_done
    STA url_buffer,X
    INX
    BNE build_prefix
.build_prefix_done
    LDA (command_line),Y
.build_host_loop
    CMP #' '
    BEQ build_port
    CMP #13
    BEQ build_default_port
    CMP #0
    BEQ build_default_port
    STA url_buffer,X
    INX
    CPX #180
    BCS build_target_missing
    INY
    LDA (command_line),Y
    JMP build_host_loop
.build_port
    LDA #':'
    STA url_buffer,X
    INX
.build_skip_port_space
    INY
    LDA (command_line),Y
    CMP #' '
    BEQ build_skip_port_space
.build_port_loop
    CMP #13
    BEQ build_target_done
    CMP #0
    BEQ build_target_done
    CMP #' '
    BEQ build_target_done
    STA url_buffer,X
    INX
    INY
    LDA (command_line),Y
    JMP build_port_loop
.build_default_port
    LDA #':'
    STA url_buffer,X
    INX
    LDA #'2'
    STA url_buffer,X
    INX
    STA url_buffer,X
    INX
.build_target_done
    LDA #'/'
    STA url_buffer,X
    INX
    LDA #0
    STA url_buffer,X
    SEC
    RTS
.build_target_missing
    CLC
    RTS

.show_error
    PHA
    LDX #LO(error_text)
    LDY #HI(error_text)
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

.usage_text
    EQUS "Usage: *SSH user@host [port]", 13, 0
.no_service_text
    EQUS "Pi1MHz services mailbox not found.", 13, 0
.secure_required_text
    EQUS "Pi1MHz managed SSH service ABI 1 required.", 13, 0
.secure_timeout_text
    EQUS "Pi1MHz secure service did not answer.", 13, 0
.connecting_text
    EQUS "SSH: connecting and verifying host...", 13, 0
.connected_text
    EQUS "SSH connected. Ctrl-] disconnects.", 13, 0
.unknown_host_text
    EQUS "Unknown host key: ", 0
.accept_text
    EQUS 13, "Trust and store on Pi SD card (y/N)? ", 0
.host_declined_text
    EQUS "Host key not accepted.", 13, 0
.auth_failed_text
    EQUS "SSH authentication failed.", 13, 0
.password_text
    EQUS "Password: ", 0
.password_auth_text
    EQUS "Authenticating with password...", 13, 0
.remote_closed_text
    EQUS 13, "Remote host closed the SSH channel.", 13, 0
.local_closed_text
    EQUS 13, "Disconnected.", 13, 0
.error_text
    EQUS 13, "SSH 0.1.57 error &", 0
.tcp_prefix
    EQUS "TCP://", 0
.url_buffer
    SKIP 192
.username_buffer
    SKIP 64
.password_buffer
    SKIP 64
.password_length
    EQUB 0
.password_attempted
    EQUB 0
.key_buffer
    SKIP 3
.send_pointer
    EQUW 0
.send_remaining
    EQUB 0
.send_retries
    EQUB 0
.ssh_rx_remaining
    EQUB 0
.ssh_rx_index
    EQUB 0
.ssh_fingerprint_index
    EQUB 0
.keyboard_active
    EQUB 0
.saved_escape_break
    EQUB 0
.saved_cursor_keys
    EQUB 0
.saved_escape_ascii
    EQUB 0
.saved_keyboard_status
    EQUB 0

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/common/pi1mhz_secure.asm"
INCLUDE "src/vt100.asm"
INCLUDE "src/common/application.asm"

.end
SAVE start, end, start
