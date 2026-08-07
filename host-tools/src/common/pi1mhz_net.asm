\ Direct Pi1MHz net-service client.
\
\ The caller runs on the I/O processor. The DFS catalogue marks executables
\ with &FFFFxxxx load/execute addresses so a Tube filing system keeps them on
\ the host. nIRQ remains disarmed; the applications poll cooperatively.

net_ptr = &72               \ application-owned zero-page workspace

\ Obtain the filing system's command-line tail for a *RUN/*file program.
\ command_line is the shared four-byte zero-page OSARGS control block.
.mos_get_command_tail
    LDA #1
    LDX #command_line
    LDY #0
    JMP OSARGS

.net_probe
    LDA #NET_COMMAND_LO
    STA SERVICE_ADDR_LO
    LDA #NET_COMMAND_MI
    STA SERVICE_ADDR_MI
    LDA #NET_COMMAND_HI
    STA SERVICE_ADDR_HI
    LDA SERVICE_ADDR_LO
    CMP #NET_COMMAND_LO
    BNE net_probe_missing
    LDA SERVICE_ADDR_MI
    CMP #NET_COMMAND_MI
    BNE net_probe_missing
    LDA SERVICE_ADDR_HI
    CMP #NET_COMMAND_HI
    BNE net_probe_missing
    SEC
    RTS
.net_probe_missing
    CLC
    RTS

.net_select_command
    LDA #NET_COMMAND_LO
    STA SERVICE_ADDR_LO
    LDA #NET_COMMAND_MI
    STA SERVICE_ADDR_MI
    LDA #NET_COMMAND_HI
    STA SERVICE_ADDR_HI
    RTS

.net_select_rx
    LDA #NET_RX_LO
    STA SERVICE_ADDR_LO
    LDA #NET_RX_MI
    STA SERVICE_ADDR_MI
    LDA #NET_RX_HI
    STA SERVICE_ADDR_HI
    RTS

.net_select_tx
    LDA #NET_TX_LO
    STA SERVICE_ADDR_LO
    LDA #NET_TX_MI
    STA SERVICE_ADDR_MI
    LDA #NET_TX_HI
    STA SERVICE_ADDR_HI
    RTS

\ Begin a command block. A is the command number.
.net_begin
    PHA
    JSR net_select_command
    PLA
    STA SERVICE_DATA
    RTS

\ Dispatch once. Pi-side commands are completed by the ordinary firmware poll
\ loop after the FIQ has latched them. Real hardware can therefore remain busy
\ longer than a tight 6502 spin, particularly while lwIP is active. Check once
\ immediately, then yield for at most 300 video frames. This remains bounded
\ when the service is absent or wedged and does not re-submit the command.
\ Returns the Pi result in A.
.net_dispatch
    LDA #NET_DISPATCH
    STA SERVICE_COMMAND
    LDA #&2C
    STA net_busy_lo
    LDA #1
    STA net_busy_hi
.net_dispatch_busy
    LDA SERVICE_COMMAND
    BPL net_dispatch_done
    LDA net_busy_lo
    BNE net_dispatch_dec_lo
    LDA net_busy_hi
    BEQ net_dispatch_timeout
    DEC net_busy_hi
.net_dispatch_dec_lo
    DEC net_busy_lo
    LDA #19
    JSR OSBYTE
    JMP net_dispatch_busy
.net_dispatch_timeout
    LDA #NET_LOCAL_TIMEOUT
.net_dispatch_done
    RTS

\ Re-dispatch an asynchronous command for at most about 30 seconds.
.net_dispatch_wait
    LDA #&B8
    STA net_wait_lo
    LDA #&0B
    STA net_wait_hi
.net_dispatch_wait_again
    JSR net_dispatch
    CMP #NET_PENDING
    BNE net_dispatch_wait_done
    LDA #19
    JSR OSBYTE
    LDA net_wait_lo
    BNE net_dispatch_wait_dec_lo
    LDA net_wait_hi
    BEQ net_dispatch_wait_timeout
    DEC net_wait_hi
.net_dispatch_wait_dec_lo
    DEC net_wait_lo
    JMP net_dispatch_wait_again
.net_dispatch_wait_timeout
    LDA #NET_LOCAL_TIMEOUT
.net_dispatch_wait_done
    RTS

\ X/Y point to a NUL-terminated URL. Returns result in A.
.net_url_open
    STX net_ptr
    STY net_ptr + 1
    LDA #NET_CMD_URL_OPEN
    JSR net_begin
    LDA #0                  \ read mode
    STA SERVICE_DATA
    LDY #0
.net_url_open_copy
    LDA (net_ptr),Y
    STA SERVICE_DATA
    BEQ net_url_open_go
    INY
    CPY #220
    BCC net_url_open_copy
    LDA #0
    STA SERVICE_DATA
    LDA #&23                \ NET_ERR_PARAM
    RTS
.net_url_open_go
    JMP net_dispatch_wait

\ Read up to NET_IO_MAX bytes into the fixed JIM RX buffer.
\ Returns result in A and the 16-bit byte count in net_length.
.net_url_read
    LDA #NET_CMD_URL_READ
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
    STA net_result
    JSR net_select_command
    LDA #1
    STA SERVICE_ADDR_LO
    LDA SERVICE_DATA
    STA net_length
    LDA SERVICE_DATA
    STA net_length + 1
    LDA SERVICE_DATA         \ discard high byte
    LDA net_result
    RTS

\ X/Y point to A bytes in host RAM. Returns result in A and consumed count in
\ net_length. The caller retries any unconsumed tail.
.net_url_write
    STA net_write_length
    STX net_ptr
    STY net_ptr + 1
    JSR net_select_tx
    LDY #0
.net_url_write_copy
    CPY net_write_length
    BEQ net_url_write_command
    LDA (net_ptr),Y
    STA SERVICE_DATA
    INY
    BNE net_url_write_copy
.net_url_write_command
    LDA #NET_CMD_URL_WRITE
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

.net_url_close
    LDA #NET_CMD_URL_CLOSE
    JSR net_begin
    JMP net_dispatch_wait

.net_wait_lo
    EQUB 0
.net_wait_hi
    EQUB 0
.net_busy_lo
    EQUB 0
.net_busy_hi
    EQUB 0
.net_length
    EQUW 0
.net_write_length
    EQUB 0
.net_result
    EQUB 0
