\ NetTools secure-service foundation. Commands 94-113 are reserved.

SEC_CMD_CAPS = 94
SEC_CMD_RANDOM = 95
SEC_CMD_SSH_OPEN = 96
SEC_CMD_SSH_READ = 97
SEC_CMD_SSH_WRITE = 98
SEC_CMD_SSH_CLOSE = 99
SEC_CMD_SSH_PASSWORD = 100
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

.secure_probe
    LDA #SEC_CMD_CAPS
    JSR net_begin
    JSR net_dispatch
    CMP #NET_OK
    BNE secure_probe_done
    JSR net_select_command
    LDA #1
    STA SERVICE_ADDR_LO
    LDA SERVICE_DATA
    CMP #SEC_ABI_MAJOR
    BNE secure_probe_bad
    LDA SERVICE_DATA       \ minor
    LDA SERVICE_DATA       \ features
    STA secure_features
    AND #1
    BEQ secure_probe_bad
    LDA #8
    STA SERVICE_ADDR_LO
    LDA SERVICE_DATA
    CMP #'N'
    BNE secure_probe_bad
    LDA SERVICE_DATA
    CMP #'T'
    BNE secure_probe_bad
    LDA SERVICE_DATA
    CMP #'S'
    BNE secure_probe_bad
    LDA #NET_OK
.secure_probe_done
    RTS
.secure_probe_bad
    LDA #NET_ERR_UNSUPPORTED
    RTS

\ Fill 16 bytes at JIM &020200. Returns the service result in A.
.secure_random16
    LDA #SEC_CMD_RANDOM
    JSR net_begin
    LDA #16
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    STA SERVICE_DATA
    LDA #SEC_RANDOM_JIM_LO
    STA SERVICE_DATA
    LDA #SEC_RANDOM_JIM_MI
    STA SERVICE_DATA
    LDA #SEC_RANDOM_JIM_HI
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    JMP net_dispatch

.secure_select_random
    LDA #SEC_RANDOM_JIM_LO
    STA SERVICE_ADDR_LO
    LDA #SEC_RANDOM_JIM_MI
    STA SERVICE_ADDR_MI
    LDA #SEC_RANDOM_JIM_HI
    STA SERVICE_ADDR_HI
    RTS

\ Copy the NUL-terminated string at X/Y to JIM address A/&03/&02.
\ The caller supplies the low address in A (URL=&00, user=&00 with MI=&04),
\ so the two public wrappers below keep the command ABI explicit.
.secure_copy_url
    STX net_ptr
    STY net_ptr + 1
    LDA #SEC_URL_JIM_LO
    STA SERVICE_ADDR_LO
    LDA #SEC_URL_JIM_MI
    STA SERVICE_ADDR_MI
    LDA #SEC_URL_JIM_HI
    STA SERVICE_ADDR_HI
    JMP secure_copy_string
.secure_copy_user
    STX net_ptr
    STY net_ptr + 1
    LDA #SEC_USER_JIM_LO
    STA SERVICE_ADDR_LO
    LDA #SEC_USER_JIM_MI
    STA SERVICE_ADDR_MI
    LDA #SEC_USER_JIM_HI
    STA SERVICE_ADDR_HI
.secure_copy_string
    LDY #0
.secure_copy_string_loop
    LDA (net_ptr),Y
    STA SERVICE_DATA
    BEQ secure_copy_string_ok
    INY
    CPY #192
    BCC secure_copy_string_loop
    LDA #NET_LOCAL_PROTOCOL
    RTS
.secure_copy_string_ok
    TYA
    CLC
    ADC #1
    RTS

\ Start/poll a managed SSH connection. A contains flags; bit 0 accepts and
\ persists an unknown host key. URL and username must already be in the fixed
\ JIM string buffers. The Pi owns key exchange, crypto and private-key use.
.secure_ssh_open
    STA secure_open_flags
    LDA #SEC_CMD_SSH_OPEN
    JSR net_begin
    LDA secure_open_flags
    STA SERVICE_DATA
    LDA #SEC_URL_JIM_LO
    STA SERVICE_DATA
    LDA #SEC_URL_JIM_MI
    STA SERVICE_DATA
    LDA #SEC_URL_JIM_HI
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    LDA #SEC_USER_JIM_LO
    STA SERVICE_DATA
    LDA #SEC_USER_JIM_MI
    STA SERVICE_DATA
    LDA #SEC_USER_JIM_HI
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    JMP net_dispatch_wait

.secure_ssh_read
    LDA #SEC_CMD_SSH_READ
    JSR net_begin
    LDA #NET_IO_MAX
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    STA SERVICE_DATA
    LDA #NET_RX_LO
    STA SERVICE_DATA
    LDA #NET_RX_MI
    STA SERVICE_DATA
    LDA #NET_RX_HI
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    JSR net_dispatch
    JMP secure_ssh_result_length

.secure_ssh_write
    STA net_write_length
    STX net_ptr
    STY net_ptr + 1
    JSR net_select_tx
    LDY #0
.secure_ssh_write_copy
    CPY net_write_length
    BEQ secure_ssh_write_command
    LDA (net_ptr),Y
    STA SERVICE_DATA
    INY
    BNE secure_ssh_write_copy
.secure_ssh_write_command
    LDA #SEC_CMD_SSH_WRITE
    JSR net_begin
    LDA net_write_length
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    STA SERVICE_DATA
    LDA #NET_TX_LO
    STA SERVICE_DATA
    LDA #NET_TX_MI
    STA SERVICE_DATA
    LDA #NET_TX_HI
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    JSR net_dispatch
.secure_ssh_result_length
    STA net_result
    JSR net_select_command
    LDA #1
    STA SERVICE_ADDR_LO
    LDA SERVICE_DATA
    STA net_length
    LDA SERVICE_DATA
    STA net_length + 1
    LDA SERVICE_DATA
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
    LDA #SEC_PASSWORD_JIM_LO
    STA SERVICE_ADDR_LO
    LDA #SEC_PASSWORD_JIM_MI
    STA SERVICE_ADDR_MI
    LDA #SEC_PASSWORD_JIM_HI
    STA SERVICE_ADDR_HI
    LDY #0
.secure_password_copy
    CPY secure_password_length
    BEQ secure_password_command
    LDA (net_ptr),Y
    STA SERVICE_DATA
    INY
    BNE secure_password_copy
.secure_password_command
    LDA #SEC_CMD_SSH_PASSWORD
    JSR net_begin
    LDA secure_password_length
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    STA SERVICE_DATA
    LDA #SEC_PASSWORD_JIM_LO
    STA SERVICE_DATA
    LDA #SEC_PASSWORD_JIM_MI
    STA SERVICE_DATA
    LDA #SEC_PASSWORD_JIM_HI
    STA SERVICE_DATA
    LDA #0
    STA SERVICE_DATA
    JSR net_dispatch_wait
    STA secure_password_result
    LDA #SEC_PASSWORD_JIM_LO
    STA SERVICE_ADDR_LO
    LDA #SEC_PASSWORD_JIM_MI
    STA SERVICE_ADDR_MI
    LDA #SEC_PASSWORD_JIM_HI
    STA SERVICE_ADDR_HI
    LDY #0
    LDA #0
.secure_password_wipe
    CPY secure_password_length
    BEQ secure_password_done
    STA SERVICE_DATA
    INY
    BNE secure_password_wipe
.secure_password_done
    LDA secure_password_result
    RTS

.secure_features
    EQUB 0
.secure_open_flags
    EQUB 0
.secure_password_length
    EQUB 0
.secure_password_result
    EQUB 0
