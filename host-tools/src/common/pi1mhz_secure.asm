\ NetTools secure-service foundation. Commands 94-113 are reserved.

SEC_CMD_CAPS = 94
SEC_CMD_RANDOM = 95
SEC_CMD_SSH_OPEN = 96
SEC_CMD_SSH_READ = 97
SEC_CMD_SSH_WRITE = 98
SEC_CMD_SSH_CLOSE = 99
SEC_CMD_SSH_PASSWORD = 100
SEC_CMD_SFTP_OPEN = 101
SEC_CMD_SFTP_PWD = 102
SEC_CMD_SFTP_CD = 103
SEC_CMD_SFTP_LS = 104
SEC_CMD_SFTP_DELETE = 105
SEC_CMD_SFTP_MKDIR = 106
SEC_CMD_SFTP_RMDIR = 107
SEC_CMD_SFTP_GET_OPEN = 108
SEC_CMD_SFTP_GET_READ = 109
SEC_CMD_SFTP_PUT_OPEN = 110
SEC_CMD_SFTP_PUT_WRITE = 111
SEC_CMD_SFTP_TRANSFER_CLOSE = 112
SEC_CMD_SFTP_CLOSE = 113
SEC_ABI_MAJOR = 1
SEC_RANDOM_JIM_LO = &00
SEC_RANDOM_JIM_MI = &02
SEC_RANDOM_JIM_HI = &02
SEC_URL_JIM_LO = &00
SEC_URL_JIM_MI = &03
SEC_URL_JIM_HI = &02
SEC_USER_JIM_LO = &00
SEC_USER_JIM_MI = &04
SEC_USER_JIM_HI = &02
SEC_PASSWORD_JIM_LO = &00
SEC_PASSWORD_JIM_MI = &06
SEC_PASSWORD_JIM_HI = &02
SEC_PATH_JIM_LO = &00
SEC_PATH_JIM_MI = &07
SEC_PATH_JIM_HI = &02

.secure_probe
    LDA #SEC_CMD_CAPS
    JSR net_begin
    JSR net_dispatch
    CMP #NET_OK
    BNE secure_probe_done
    PHP
    SEI
    JSR net_select_command
    LDA #1
    JSR net_set_cursor_low
    JSR net_data_read
    CMP #SEC_ABI_MAJOR
    BNE secure_probe_bad
    JSR net_data_read       \ minor
    JSR net_data_read       \ features
    STA secure_features
    AND #1
    BEQ secure_probe_bad
    LDA #8
    JSR net_set_cursor_low
    JSR net_data_read
    CMP #'N'
    BNE secure_probe_bad
    JSR net_data_read
    CMP #'T'
    BNE secure_probe_bad
    JSR net_data_read
    CMP #'S'
    BNE secure_probe_bad
    PLP
    LDA #NET_OK
.secure_probe_done
    RTS
.secure_probe_bad
    PLP
    LDA #NET_ERR_UNSUPPORTED
    RTS

\ Fill 16 bytes at JIM &020200. Returns the service result in A.
.secure_random16
    LDA #SEC_CMD_RANDOM
    JSR net_begin
    LDA #16
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #SEC_RANDOM_JIM_LO
    JSR net_data_write
    LDA #SEC_RANDOM_JIM_MI
    JSR net_data_write
    LDA #SEC_RANDOM_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JMP net_dispatch

.secure_select_random
    LDA #SEC_RANDOM_JIM_LO
    LDX #SEC_RANDOM_JIM_MI
    LDY #SEC_RANDOM_JIM_HI
    JMP net_select_address

\ Copy the NUL-terminated string at X/Y to JIM address A/&03/&02.
\ The caller supplies the low address in A (URL=&00, user=&00 with MI=&04),
\ so the two public wrappers below keep the command ABI explicit.
.secure_copy_url
    PHP
    SEI
    STX net_ptr
    STY net_ptr + 1
    LDA #SEC_URL_JIM_LO
    LDX #SEC_URL_JIM_MI
    LDY #SEC_URL_JIM_HI
    JSR net_select_address
    JMP secure_copy_string
.secure_copy_user
    PHP
    SEI
    STX net_ptr
    STY net_ptr + 1
    LDA #SEC_USER_JIM_LO
    LDX #SEC_USER_JIM_MI
    LDY #SEC_USER_JIM_HI
    JSR net_select_address
.secure_copy_string
    LDY #0
.secure_copy_string_loop
    LDA (net_ptr),Y
    JSR net_data_write
    BEQ secure_copy_string_ok
    INY
    CPY #192
    BCC secure_copy_string_loop
    LDA #NET_LOCAL_PROTOCOL
    PLP
    RTS
.secure_copy_string_ok
    TYA
    CLC
    ADC #1
    PLP
    RTS

\ Start/poll a managed SSH connection. A contains flags; bit 0 accepts and
\ persists an unknown host key. URL and username must already be in the fixed
\ JIM string buffers. The Pi owns key exchange, crypto and private-key use.
.secure_ssh_open
    STA secure_open_flags
    LDA #SEC_CMD_SSH_OPEN
    JSR net_begin
    LDA secure_open_flags
    JSR net_data_write
    LDA #SEC_URL_JIM_LO
    JSR net_data_write
    LDA #SEC_URL_JIM_MI
    JSR net_data_write
    LDA #SEC_URL_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    LDA #SEC_USER_JIM_LO
    JSR net_data_write
    LDA #SEC_USER_JIM_MI
    JSR net_data_write
    LDA #SEC_USER_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JMP net_dispatch_wait

.secure_ssh_read
    LDA #SEC_CMD_SSH_READ
    JSR net_begin
    LDA #NET_IO_MAX
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #NET_RX_LO
    JSR net_data_write
    LDA #NET_RX_MI
    JSR net_data_write
    LDA #NET_RX_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_dispatch
    JMP secure_ssh_result_length

.secure_ssh_write
    STA net_write_length
    STX net_ptr
    STY net_ptr + 1
    PHP
    SEI
    JSR net_select_tx
    LDY #0
.secure_ssh_write_copy
    CPY net_write_length
    BEQ secure_ssh_write_command
    LDA (net_ptr),Y
    JSR net_data_write
    INY
    BNE secure_ssh_write_copy
.secure_ssh_write_command
    PLP
    LDA #SEC_CMD_SSH_WRITE
    JSR net_begin
    LDA net_write_length
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #NET_TX_LO
    JSR net_data_write
    LDA #NET_TX_MI
    JSR net_data_write
    LDA #NET_TX_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_dispatch
.secure_ssh_result_length
    STA net_result
    PHP
    SEI
    JSR net_select_command
    LDA #1
    JSR net_set_cursor_low
    JSR net_data_read
    STA net_length
    JSR net_data_read
    STA net_length + 1
    JSR net_data_read
    PLP
    LDA net_result
    RTS

.secure_ssh_close
    LDA #SEC_CMD_SSH_CLOSE
    JSR net_begin
    JMP net_dispatch_wait

\ Supply an ephemeral password for the next SSH open. A is the length and
\ X/Y point at the bytes. Both the mailbox copy and caller buffer are wiped;
\ this routine owns the JIM-side wipe, while the caller owns its RAM buffer.
.secure_ssh_password
    STA secure_password_length
    STX net_ptr
    STY net_ptr + 1
    PHP
    SEI
    LDA #SEC_PASSWORD_JIM_LO
    LDX #SEC_PASSWORD_JIM_MI
    LDY #SEC_PASSWORD_JIM_HI
    JSR net_select_address
    LDY #0
.secure_password_copy
    CPY secure_password_length
    BEQ secure_password_command
    LDA (net_ptr),Y
    JSR net_data_write
    INY
    BNE secure_password_copy
.secure_password_command
    PLP
    LDA #SEC_CMD_SSH_PASSWORD
    JSR net_begin
    LDA secure_password_length
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #SEC_PASSWORD_JIM_LO
    JSR net_data_write
    LDA #SEC_PASSWORD_JIM_MI
    JSR net_data_write
    LDA #SEC_PASSWORD_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_dispatch_wait
    STA secure_password_result
    PHP
    SEI
    LDA #SEC_PASSWORD_JIM_LO
    LDX #SEC_PASSWORD_JIM_MI
    LDY #SEC_PASSWORD_JIM_HI
    JSR net_select_address
    LDY #0
    LDA #0
.secure_password_wipe
    CPY secure_password_length
    BEQ secure_password_done
    JSR net_data_write
    INY
    BNE secure_password_wipe
.secure_password_done
    PLP
    LDA secure_password_result
    RTS

\ Copy a NUL-terminated remote path at X/Y into the fixed SFTP path buffer.
.secure_copy_path
    PHP
    SEI
    STX net_ptr
    STY net_ptr + 1
    LDA #SEC_PATH_JIM_LO
    LDX #SEC_PATH_JIM_MI
    LDY #SEC_PATH_JIM_HI
    JSR net_select_address
    JMP secure_copy_string

.secure_sftp_open
    STA secure_open_flags
    LDA #SEC_CMD_SFTP_OPEN
    JSR net_begin
    LDA secure_open_flags
    JSR net_data_write
    LDA #SEC_URL_JIM_LO
    JSR net_data_write
    LDA #SEC_URL_JIM_MI
    JSR net_data_write
    LDA #SEC_URL_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    LDA #SEC_USER_JIM_LO
    JSR net_data_write
    LDA #SEC_USER_JIM_MI
    JSR net_data_write
    LDA #SEC_USER_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JMP net_dispatch_wait

\ A contains the path-operation command. The fixed path buffer is input and
\ the normal receive buffer is output. Returns length in net_length.
.secure_sftp_path
    JSR net_begin
    LDA #NET_IO_MAX
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #SEC_PATH_JIM_LO
    JSR net_data_write
    LDA #SEC_PATH_JIM_MI
    JSR net_data_write
    LDA #SEC_PATH_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    LDA #NET_RX_LO
    JSR net_data_write
    LDA #NET_RX_MI
    JSR net_data_write
    LDA #NET_RX_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_dispatch_wait
    JMP secure_ssh_result_length

\ A is GET_OPEN or PUT_OPEN; the fixed path buffer is input.
.secure_sftp_transfer_open
    JSR net_begin
    LDA #0
    JSR net_data_write
    JSR net_data_write
    JSR net_data_write
    LDA #SEC_PATH_JIM_LO
    JSR net_data_write
    LDA #SEC_PATH_JIM_MI
    JSR net_data_write
    LDA #SEC_PATH_JIM_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JMP net_dispatch_wait

.secure_sftp_get_read
    LDA #SEC_CMD_SFTP_GET_READ
    JSR net_begin
    LDA #NET_IO_MAX
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #NET_RX_LO
    JSR net_data_write
    LDA #NET_RX_MI
    JSR net_data_write
    LDA #NET_RX_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_dispatch_wait
    JMP secure_ssh_result_length

\ A is length and X/Y point to data.
.secure_sftp_put_write
    STA net_write_length
    STX net_ptr
    STY net_ptr + 1
    PHP
    SEI
    JSR net_select_tx
    LDY #0
.secure_sftp_put_copy
    CPY net_write_length
    BEQ secure_sftp_put_command
    LDA (net_ptr),Y
    JSR net_data_write
    INY
    BNE secure_sftp_put_copy
.secure_sftp_put_command
    PLP
    LDA #SEC_CMD_SFTP_PUT_WRITE
    JSR net_begin
    LDA net_write_length
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_data_write
    LDA #NET_TX_LO
    JSR net_data_write
    LDA #NET_TX_MI
    JSR net_data_write
    LDA #NET_TX_HI
    JSR net_data_write
    LDA #0
    JSR net_data_write
    JSR net_dispatch_wait
    JMP secure_ssh_result_length

.secure_sftp_transfer_close
    LDA #SEC_CMD_SFTP_TRANSFER_CLOSE
    JSR net_begin
    JMP net_dispatch_wait

.secure_sftp_close
    LDA #SEC_CMD_SFTP_CLOSE
    JSR net_begin
    JMP net_dispatch_wait

.secure_features
    EQUB 0
.secure_open_flags
    EQUB 0
.secure_password_length
    EQUB 0
.secure_password_result
    EQUB 0
