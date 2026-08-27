INCLUDE "src/common/mos.inc"

OSFIND = &FFCE
OSBGET = &FFD7
OSBPUT = &FFD4
command_line = &70

ORG APP_START
GUARD APP_LIMIT

.start
    JSR application_check_workspace
    BCS sftp_memory_ok
    JMP application_exit
.sftp_memory_ok
    JSR mos_get_command_tail
    JSR build_sftp_target
    BCS sftp_target_ok
    LDX #LO(usage_text)
    LDY #HI(usage_text)
    JSR print_string
    JMP application_exit
.sftp_target_ok
    JSR net_probe
    BCS sftp_mailbox_ok
    LDX #LO(no_service_text)
    LDY #HI(no_service_text)
    JSR print_string
    JMP application_exit
.sftp_mailbox_ok
    JSR secure_probe
    CMP #NET_OK
    BNE sftp_error_exit
    LDA secure_features
    AND #8
    BNE sftp_supported
    LDA #NET_ERR_UNSUPPORTED
    BNE sftp_error_exit
.sftp_supported
    LDX #LO(url_buffer)
    LDY #HI(url_buffer)
    JSR secure_copy_url
    LDX #LO(username_buffer)
    LDY #HI(username_buffer)
    JSR secure_copy_user
    LDA #0
    JSR secure_sftp_open
    CMP #NET_HOSTKEY_UNKNOWN
    BNE sftp_open_result
    JSR sftp_confirm_host_key
    BCC sftp_close
    LDA #1
    JSR secure_sftp_open
.sftp_open_result
    CMP #NET_OK
    BEQ sftp_connected
    CMP #NET_AUTH_FAILED
    BNE sftp_error_exit
    JSR sftp_prompt_password
    BCC sftp_close
    LDX #LO(password_buffer)
    LDY #HI(password_buffer)
    JSR secure_ssh_password
    PHA
    JSR sftp_wipe_password
    PLA
    CMP #NET_OK
    BNE sftp_error_exit
    LDA #0
    JSR secure_sftp_open
    CMP #NET_OK
    BNE sftp_error_exit
.sftp_connected
    LDX #LO(connected_text)
    LDY #HI(connected_text)
    JSR print_string
.sftp_prompt
    LDX #LO(prompt_text)
    LDY #HI(prompt_text)
    JSR print_string
    JSR read_line
    BCC sftp_close
    JSR dispatch_line
    BCS sftp_prompt
.sftp_close
    JSR secure_sftp_transfer_close
    JSR secure_sftp_close
    JMP application_exit
.sftp_error_exit
    JSR show_error
    JMP sftp_close

\ Read an editable command line without changing the current display mode.
.read_line
    LDX #0
.read_line_next
    JSR OSRDCH
    CMP #27
    BEQ read_line_escape
    CMP #13
    BEQ read_line_done
    CMP #8
    BEQ read_line_delete
    CMP #127
    BEQ read_line_delete
    CMP #32
    BCC read_line_next
    CPX #126
    BCS read_line_next
    STA line_buffer,X
    INX
    JSR OSWRCH
    JMP read_line_next
.read_line_delete
    CPX #0
    BEQ read_line_next
    DEX
    LDA #127
    JSR OSWRCH
    JMP read_line_next
.read_line_done
    LDA #0
    STA line_buffer,X
    JSR OSNEWL
    SEC
    RTS
.read_line_escape
    JSR OSNEWL
    CLC
    RTS

.dispatch_line
    LDX #0
.dispatch_skip
    LDA line_buffer,X
    CMP #' '
    BNE dispatch_word
    INX
    BNE dispatch_skip
.dispatch_word
    STX argument_index
    JSR uppercase_command
    LDX argument_index
    LDA line_buffer,X
    BNE dispatch_nonempty
    JMP dispatch_keep
.dispatch_nonempty
    CMP #'Q'
    BNE dispatch_help
    LDA line_buffer + 1,X
    CMP #'U'
    BNE dispatch_help
    JMP dispatch_quit
.dispatch_help
    LDA line_buffer,X
    CMP #'H'
    BNE dispatch_pwd
    LDX #LO(help_text)
    LDY #HI(help_text)
    JSR print_string
    SEC
    RTS
.dispatch_pwd
    LDA line_buffer,X
    CMP #'P'
    BNE dispatch_cd
    LDA line_buffer + 1,X
    CMP #'W'
    BEQ dispatch_pwd_run
    JMP dispatch_put
.dispatch_pwd_run
    LDA #SEC_CMD_SFTP_PWD
    JMP run_path_command
.dispatch_cd
    LDA line_buffer,X
    CMP #'C'
    BNE dispatch_ls
    LDA line_buffer + 1,X
    CMP #'D'
    BNE dispatch_unknown
    LDA #SEC_CMD_SFTP_CD
    JMP run_path_command
.dispatch_ls
    LDA line_buffer,X
    CMP #'L'
    BNE dispatch_dir
    LDA line_buffer + 1,X
    CMP #'S'
    BNE dispatch_unknown
    LDA #SEC_CMD_SFTP_LS
    JMP run_path_command
.dispatch_dir
    LDA line_buffer,X
    CMP #'D'
    BNE dispatch_get
    LDA line_buffer + 1,X
    CMP #'I'
    BNE dispatch_delete
    LDA #SEC_CMD_SFTP_LS
    JMP run_path_command
.dispatch_delete
    LDA line_buffer + 1,X
    CMP #'E'
    BNE dispatch_unknown
    LDA #SEC_CMD_SFTP_DELETE
    JMP run_path_command
.dispatch_get
    LDA line_buffer,X
    CMP #'G'
    BNE dispatch_mkdir
    LDA line_buffer + 1,X
    CMP #'E'
    BNE dispatch_unknown
    JMP sftp_get
.dispatch_mkdir
    LDA line_buffer,X
    CMP #'M'
    BNE dispatch_rmdir
    LDA line_buffer + 1,X
    CMP #'K'
    BNE dispatch_unknown
    LDA #SEC_CMD_SFTP_MKDIR
    JMP run_path_command
.dispatch_rmdir
    LDA line_buffer,X
    CMP #'R'
    BNE dispatch_put
    LDA line_buffer + 1,X
    CMP #'M'
    BNE dispatch_unknown
    LDA #SEC_CMD_SFTP_RMDIR
    JMP run_path_command
.dispatch_put
    LDA line_buffer,X
    CMP #'P'
    BNE dispatch_unknown
    LDA line_buffer + 1,X
    CMP #'U'
    BNE dispatch_unknown
    JMP sftp_put
.dispatch_unknown
    LDX #LO(unknown_text)
    LDY #HI(unknown_text)
    JSR print_string
.dispatch_keep
    SEC
    RTS
.dispatch_quit
    CLC
    RTS

\ Uppercase only the command word; remote paths remain case-sensitive.
.uppercase_command
    LDY argument_index
.uppercase_loop
    LDA line_buffer,Y
    BEQ uppercase_done
    CMP #' '
    BEQ uppercase_done
    CMP #'a'
    BCC uppercase_next
    CMP #'z' + 1
    BCS uppercase_next
    AND #&DF
    STA line_buffer,Y
.uppercase_next
    INY
    BNE uppercase_loop
.uppercase_done
    RTS

\ Copy the argument following the command into path_buffer.
.copy_path_argument
    LDY argument_index
.path_find_space
    LDA line_buffer,Y
    BEQ path_empty
    INY
    CMP #' '
    BNE path_find_space
.path_skip_space
    LDA line_buffer,Y
    CMP #' '
    BNE path_copy_start
    INY
    BNE path_skip_space
.path_copy_start
    LDX #0
.path_copy
    LDA line_buffer,Y
    BEQ path_done
    CMP #' '
    BEQ path_done
    STA path_buffer,X
    INX
    INY
    CPX #127
    BCC path_copy
.path_done
    LDA #0
    STA path_buffer,X
    STY second_index
    CPX #0
    BEQ path_empty
    SEC
    RTS
.path_empty
    LDA #0
    STA path_buffer
    CLC
    RTS

.run_path_command
    STA saved_command
    JSR copy_path_argument
    LDA saved_command
    CMP #SEC_CMD_SFTP_PWD
    BEQ path_argument_ok
    BCC path_usage
    LDA path_buffer
    BNE path_argument_ok
.path_usage
    LDX #LO(argument_text)
    LDY #HI(argument_text)
    JSR print_string
    SEC
    RTS
.path_argument_ok
    LDX #LO(path_buffer)
    LDY #HI(path_buffer)
    JSR secure_copy_path
    LDA saved_command
    JSR secure_sftp_path
    CMP #NET_OK
    BNE path_error
    LDA net_length
    ORA net_length + 1
    BEQ path_ok
    JSR net_copy_rx_to_host
    LDX #0
.path_print
    CPX net_length
    BEQ path_ok
    LDA net_rx_host,X
    STX saved_index
    JSR OSASCI
    LDX saved_index
    INX
    BNE path_print
.path_ok
    SEC
    RTS
.path_error
    JSR show_error
    SEC
    RTS

.sftp_get
    JSR copy_path_argument
    BCC path_usage
    JSR choose_local_name
    LDX #LO(path_buffer)
    LDY #HI(path_buffer)
    JSR secure_copy_path
    LDA #SEC_CMD_SFTP_GET_OPEN
    JSR secure_sftp_transfer_open
    CMP #NET_OK
    BNE get_remote_error
    LDA #&80
    LDX #LO(local_name)
    LDY #HI(local_name)
    JSR OSFIND
    BNE get_file_open
    JSR secure_sftp_transfer_close
    JMP local_file_error
.get_file_open
    STA file_handle
.get_loop
    JSR secure_sftp_get_read
    CMP #NET_OK
    BEQ get_read_ok
    JMP transfer_error_close_remote
.get_read_ok
    LDA net_length
    ORA net_length + 1
    BEQ transfer_done
    JSR net_copy_rx_to_host
    LDX #0
.get_write
    CPX net_length
    BEQ get_loop
    LDA net_rx_host,X
    STX saved_index
    LDY file_handle
    JSR OSBPUT
    LDX saved_index
    INX
    BNE get_write
    JMP get_loop
.get_remote_error
    JSR show_error
    SEC
    RTS

.sftp_put
    JSR copy_path_argument
    BCS put_have_path
    JMP path_usage
.put_have_path
    JSR copy_local_from_path
    JSR choose_remote_name
    LDA #&40
    LDX #LO(local_name)
    LDY #HI(local_name)
    JSR OSFIND
    BNE put_file_open
    JMP local_file_error
.put_file_open
    STA file_handle
    LDX #LO(path_buffer)
    LDY #HI(path_buffer)
    JSR secure_copy_path
    LDA #SEC_CMD_SFTP_PUT_OPEN
    JSR secure_sftp_transfer_open
    CMP #NET_OK
    BEQ put_loop
    JMP transfer_error_close
.put_loop
    LDX #0
.put_read
    LDY file_handle
    JSR OSBGET
    BCS put_chunk
    STA transfer_buffer,X
    INX
    CPX #NET_IO_MAX
    BCC put_read
.put_chunk
    TXA
    BEQ transfer_done
    LDX #LO(transfer_buffer)
    LDY #HI(transfer_buffer)
    JSR secure_sftp_put_write
    CMP #NET_OK
    BEQ put_loop
    JMP transfer_error_close_remote

.transfer_done
    JSR secure_sftp_transfer_close
    PHA
    LDA #0
    LDY file_handle
    JSR OSFIND
    PLA
    CMP #NET_OK
    BEQ transfer_success
    JSR show_error
    SEC
    RTS
.transfer_success
    LDX #LO(transfer_ok_text)
    LDY #HI(transfer_ok_text)
    JSR print_string
    SEC
    RTS
.transfer_error_close_remote
    PHA
    JSR secure_sftp_transfer_close
    PLA
.transfer_error_close
    PHA
    LDA #0
    LDY file_handle
    JSR OSFIND
    PLA
    JSR show_error
    SEC
    RTS
.local_file_error
    LDX #LO(file_error_text)
    LDY #HI(file_error_text)
    JSR print_string
    SEC
    RTS

\ GET defaults the local name to the final remote path component.
.choose_local_name
    LDY second_index
.local_skip
    LDA line_buffer,Y
    CMP #' '
    BNE local_optional
    INY
    BNE local_skip
.local_optional
    BEQ local_basename
    LDX #0
.local_copy
    LDA line_buffer,Y
    BEQ local_terminate
    CMP #' '
    BEQ local_terminate
    STA local_name,X
    INX
    INY
    CPX #120
    BCC local_copy
    BCS local_terminate
.local_basename
    LDX #0
    LDY #0
.basename_scan
    LDA path_buffer,Y
    BEQ basename_copy
    CMP #'/'
    BNE basename_next
    TYA
    CLC
    ADC #1
    TAX
.basename_next
    INY
    BNE basename_scan
.basename_copy
    LDY #0
.basename_loop
    LDA path_buffer,X
    BEQ basename_terminate
    STA local_name,Y
    INX
    INY
    BNE basename_loop
.basename_terminate
    TYA
    TAX
.local_terminate
    LDA #13
    STA local_name,X
    RTS

.copy_local_from_path
    LDX #0
.copy_local_loop
    LDA path_buffer,X
    BEQ copy_local_done
    STA local_name,X
    INX
    BNE copy_local_loop
.copy_local_done
    LDA #13
    STA local_name,X
    RTS

\ PUT defaults remote to local. An optional second word replaces it.
.choose_remote_name
    LDY second_index
.remote_skip
    LDA line_buffer,Y
    CMP #' '
    BNE remote_optional
    INY
    BNE remote_skip
.remote_optional
    BEQ remote_keep
    LDX #0
.remote_copy
    LDA line_buffer,Y
    BEQ remote_done
    CMP #' '
    BEQ remote_done
    STA path_buffer,X
    INX
    INY
    CPX #127
    BCC remote_copy
.remote_done
    LDA #0
    STA path_buffer,X
.remote_keep
    RTS

\ Parse user@host [port] into the same fixed URL contract used by SSH.
.build_sftp_target
    LDY #0
.target_skip
    LDA (command_line),Y
    CMP #' '
    BNE target_user
    INY
    BNE target_skip
.target_user
    LDX #0
.target_user_loop
    CMP #'@'
    BEQ target_user_done
    CMP #13
    BEQ target_bad
    CMP #' '
    BEQ target_bad
    STA username_buffer,X
    INX
    CPX #63
    BCS target_bad
    INY
    LDA (command_line),Y
    JMP target_user_loop
.target_user_done
    LDA #0
    STA username_buffer,X
    INY
    LDX #0
.target_prefix
    LDA tcp_prefix,X
    BEQ target_host
    STA url_buffer,X
    INX
    BNE target_prefix
.target_host
    LDA (command_line),Y
    CMP #' '
    BEQ target_port
    CMP #13
    BEQ target_default_port
    STA url_buffer,X
    INX
    INY
    CPX #180
    BCC target_host
    BCS target_bad
.target_port
    LDA #':'
    STA url_buffer,X
    INX
.target_port_skip
    INY
    LDA (command_line),Y
    CMP #' '
    BEQ target_port_skip
.target_port_copy
    CMP #13
    BEQ target_finish
    CMP #' '
    BEQ target_finish
    STA url_buffer,X
    INX
    INY
    LDA (command_line),Y
    JMP target_port_copy
.target_default_port
    LDA #':'
    STA url_buffer,X
    INX
    LDA #'2'
    STA url_buffer,X
    INX
    STA url_buffer,X
    INX
.target_finish
    LDA #'/'
    STA url_buffer,X
    INX
    LDA #0
    STA url_buffer,X
    SEC
    RTS
.target_bad
    CLC
    RTS

.sftp_confirm_host_key
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
.fingerprint_loop
    LDA net_rx_host,X
    BEQ fingerprint_done
    STX saved_index
    JSR OSASCI
    LDX saved_index
    INX
    BNE fingerprint_loop
.fingerprint_done
    LDX #LO(accept_text)
    LDY #HI(accept_text)
    JSR print_string
    JSR OSRDCH
    PHA
    JSR OSNEWL
    PLA
    AND #&DF
    CMP #'Y'
    BEQ host_accepted
    CLC
    RTS
.host_accepted
    SEC
    RTS

.sftp_prompt_password
    LDX #LO(password_text)
    LDY #HI(password_text)
    JSR print_string
    LDX #0
.password_read
    JSR OSRDCH
    CMP #13
    BEQ password_enter
    CMP #27
    BEQ password_cancel
    CMP #8
    BEQ password_delete
    CMP #127
    BEQ password_delete
    CMP #32
    BCC password_read
    CPX #63
    BCS password_read
    STA password_buffer,X
    INX
    BNE password_read
.password_delete
    CPX #0
    BEQ password_read
    DEX
    JMP password_read
.password_enter
    STX password_length
    JSR OSNEWL
    TXA
    BEQ password_cancel_no_line
    SEC
    RTS
.password_cancel
    JSR OSNEWL
.password_cancel_no_line
    JSR sftp_wipe_password
    CLC
    RTS
.sftp_wipe_password
    LDX #0
    LDA #0
.wipe_loop
    STA password_buffer,X
    INX
    CPX #64
    BCC wipe_loop
    STA password_length
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
    BCC print_digit
    ADC #'A' - 11
    JMP OSWRCH
.print_digit
    ADC #'0'
    JMP OSWRCH
.print_string
    STX print_read + 1
    STY print_read + 2
    LDY #0
.print_read
    LDA &FFFF,Y
    BEQ print_done
    JSR OSASCI
    INY
    BNE print_read
.print_done
    RTS

.usage_text EQUS "Usage: *SFTP user@host [port]",13,0
.no_service_text EQUS "Pi1MHz services mailbox not found.",13,0
.connected_text EQUS "SFTP connected. HELP lists commands.",13,0
.prompt_text EQUS "sftp> ",0
.help_text EQUS "PWD  CD path  DIR [path]  LS [path]",13
    EQUS "GET remote [local]  PUT local [remote]",13
    EQUS "DELETE file  MKDIR path  RMDIR path  QUIT",13,0
.unknown_text EQUS "Unknown SFTP command. Type HELP.",13,0
.argument_text EQUS "Remote path required.",13,0
.transfer_ok_text EQUS "Transfer complete.",13,0
.file_error_text EQUS "Local file error.",13,0
.unknown_host_text EQUS "Unknown host key: ",0
.accept_text EQUS 13,"Trust and store on Pi SD card (y/N)? ",0
.password_text EQUS "Password: ",0
.error_text EQUS "SFTP network error &",0
.tcp_prefix EQUS "TCP://",0

.url_buffer SKIP 192
.username_buffer SKIP 64
.password_buffer SKIP 64
.path_buffer SKIP 128
.local_name SKIP 128
.line_buffer SKIP 128
.transfer_buffer SKIP NET_IO_MAX
.password_length EQUB 0
.file_handle EQUB 0
.argument_index EQUB 0
.second_index EQUB 0
.saved_command EQUB 0
.saved_index EQUB 0

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/common/pi1mhz_secure.asm"
INCLUDE "src/common/application.asm"
.end
SAVE start, end, start
