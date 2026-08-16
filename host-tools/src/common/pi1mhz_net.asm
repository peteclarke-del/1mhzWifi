\ Direct Pi1MHz net-service client.
\
\ The caller runs on the I/O processor. The DFS catalogue marks executables
\ with &FFFFxxxx load/execute addresses so a Tube filing system keeps them on
\ the host. nIRQ remains disarmed; the applications poll cooperatively.

net_ptr = &72               \ application-owned zero-page workspace

IF NET_DEBUG
\ Real hardware has no serial trace channel, so a debug build reports the
\ shared FCA6-FCA9 command/result sequence on screen: ">" before a command is
\ dispatched, "<" after each poll returns a non-busy result. This is the same
\ sequence documented in host-tools/docs/secure_service_abi.md and
\ pi-side/docs commands, so hex bytes are enough to diagnose a stall against
\ that reference rather than needing decoded text here.
.net_debug_command
    PHA
    LDA #'>'
    JSR OSWRCH
    PLA
    JSR net_debug_hex
    JMP OSNEWL
.net_debug_result
    PHA
    LDA #'<'
    JSR OSWRCH
    PLA
    JSR net_debug_hex
    JMP OSNEWL
.net_debug_hex
    PHA
    LSR A
    LSR A
    LSR A
    LSR A
    JSR net_debug_nibble
    PLA
    AND #15
.net_debug_nibble
    CMP #10
    BCC net_debug_digit
    ADC #'A' - 11
    JMP OSWRCH
.net_debug_digit
    ADC #'0'
    JMP OSWRCH

\ Read the Pi-side net_service_poll stage marker (net_debug_mark) after a
\ local timeout, so a stall can be located without a serial trace channel.
\ Lives at the fixed NET_COMMAND page, offset &FF - beyond NET_IO_MAX (&F0),
\ so no command payload written directly into the command page can reach it.
.net_debug_stage
    LDA #'S'
    JSR OSWRCH
    PHP
    SEI
    LDA #NET_COMMAND_LO + &FF
    STA SERVICE_ADDR_LO
    LDA #NET_COMMAND_MI
    STA SERVICE_ADDR_MI
    LDA #NET_COMMAND_HI
    STA SERVICE_ADDR_HI
    LDA SERVICE_DATA
    STA net_debug_value
    PLP
    LDA net_debug_value
    JSR net_debug_hex
    JMP OSNEWL
ENDIF

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
    JSR net_bus_settle
    LDA #NET_COMMAND_MI
    STA SERVICE_ADDR_MI
    JSR net_bus_settle
    LDA #NET_COMMAND_HI
    STA SERVICE_ADDR_HI
    JSR net_bus_settle
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
    STA net_cursor_lo
    LDA #NET_COMMAND_MI
    STA net_cursor_mi
    LDA #NET_COMMAND_HI
    STA net_cursor_hi
    JMP net_apply_cursor

.net_select_rx
    LDA #NET_RX_LO
    STA net_cursor_lo
    LDA #NET_RX_MI
    STA net_cursor_mi
    LDA #NET_RX_HI
    STA net_cursor_hi
    JMP net_apply_cursor

.net_select_tx
    LDA #NET_TX_LO
    STA net_cursor_lo
    LDA #NET_TX_MI
    STA net_cursor_mi
    LDA #NET_TX_HI
    STA net_cursor_hi
    JMP net_apply_cursor

\ Select an arbitrary services-port byte address. A/X/Y are low/mid/high.
.net_select_address
    STA net_cursor_lo
    STX net_cursor_mi
    STY net_cursor_hi
    JMP net_apply_cursor

\ The physical Pi1MHz services port updates its auto-increment cursor from an
\ asynchronous FIQ callback. An immediate following 6502 access can therefore
\ precede the read-back update. Select the complete software-shadowed address
\ for every byte, matching the proven ROM transport, instead of depending on
\ the callback having completed between consecutive FCA9 accesses.
.net_apply_cursor
    LDA net_cursor_lo
    STA SERVICE_ADDR_LO
    JSR net_bus_settle
    LDA net_cursor_mi
    STA SERVICE_ADDR_MI
    JSR net_bus_settle
    LDA net_cursor_hi
    STA SERVICE_ADDR_HI
    JSR net_bus_settle
    RTS

.net_set_cursor_low
    STA net_cursor_lo
    STA SERVICE_ADDR_LO
    JSR net_bus_settle
    RTS

.net_data_write
    PHA
    JSR net_apply_cursor
    PLA
    STA SERVICE_DATA
    PHA
    JSR net_increment_cursor
    JSR net_wait_cursor
    PLA
    RTS

.net_data_read
    JSR net_apply_cursor
    LDA SERVICE_DATA
    PHA
    JSR net_increment_cursor
    JSR net_wait_cursor
    PLA
    RTS

.net_increment_cursor
    INC net_cursor_lo
    BNE net_cursor_done
    INC net_cursor_mi
    BNE net_cursor_done
    INC net_cursor_hi
.net_cursor_done
    RTS

\ FCA9 auto-increment is completed by the Pi's asynchronous FIQ callback.
\ Do not begin another selector transaction until its published address is
\ visible. Otherwise a late callback can overwrite the next FCA6-FCA8 values.
\ The wait is bounded and preserves every caller-visible register.
.net_wait_cursor
    JSR net_bus_settle
    PHA
    TXA
    PHA
    TYA
    PHA
    LDY #0
.net_wait_cursor_loop
    LDA SERVICE_ADDR_LO
    CMP net_cursor_lo
    BNE net_wait_cursor_again
    LDA SERVICE_ADDR_MI
    CMP net_cursor_mi
    BNE net_wait_cursor_again
    LDA SERVICE_ADDR_HI
    CMP net_cursor_hi
    BEQ net_wait_cursor_done
.net_wait_cursor_again
    DEY
    BNE net_wait_cursor_loop
    LDA #1
    STA net_cursor_timeout
.net_wait_cursor_done
    PLA
    TAY
    PLA
    TAX
    PLA
    RTS

\ Pi1MHz handles FRED writes in a 1 MHz-bus FIQ callback. Tight assembled
\ clients can reach the next selector or FCA9 access before that callback has
\ published the selected data byte or incremented cursor. BASIC clients hide
\ this latency in interpreter overhead. A CPU-local counted delay provides the
\ bounded ordering margin without issuing another FRED/JIM transaction, which
\ would replace the still-pending one-slot FIQ event.
.net_bus_settle
    PHA
    TXA
    PHA
    LDX #64
.net_bus_settle_loop
    NOP
    DEX
    BNE net_bus_settle_loop
    PLA
    TAX
    PLA
    RTS

\ Copy the fixed RX window into application RAM before the caller invokes
\ MOS or another ROM. The Pi1MHz byte-address cursor is shared global state
\ and must never be retained across those calls. NET_IO_MAX is below 256.
.net_copy_rx_to_host
    PHP
    SEI
    JSR net_select_rx
    LDX #0
.net_copy_rx_loop
    CPX net_length
    BEQ net_copy_rx_done
    JSR net_data_read
    STA net_rx_host,X
    INX
    BNE net_copy_rx_loop
.net_copy_rx_done
    PLP
    RTS

\ Copy a NUL-terminated string from the currently selected JIM address.
\ The result is always terminated, even if the remote data is malformed.
.net_copy_selected_string
    PHP
    SEI
    LDX #0
.net_copy_selected_loop
    JSR net_data_read
    STA net_rx_host,X
    BEQ net_copy_selected_done
    INX
    CPX #NET_IO_MAX
    BCC net_copy_selected_loop
    LDA #0
    STA net_rx_host,X
.net_copy_selected_done
    PLP
    RTS

\ Begin a command block. A is the command number.
.net_begin
    PHA
    PHP
    PLA
    STA net_saved_p
IF NET_DEBUG
    \ Diagnostics must run before selecting the shared JIM cursor. OSWRCH and
    \ OSNEWL can enter other ROMs, and those ROMs are entitled to use the same
    \ FCA6-FCA9 services aperture. Printing after net_select_command therefore
    \ redirected the following command-byte write on real AP5 hardware.
    PLA
    PHA
    JSR net_debug_command
ENDIF
    SEI
    JSR net_select_command
    PLA
    JSR net_data_write
    RTS

\ Dispatch once. Pi-side commands are completed by the ordinary firmware poll
\ loop after the FIQ has latched them. Real hardware can therefore remain busy
\ longer than a tight 6502 spin, particularly while lwIP is active. Check once
\ immediately, then yield for at most 300 video frames. This remains bounded
\ when the service is absent or wedged and does not re-submit the command.
\ Returns the Pi result in A.
.net_dispatch
    JSR net_dispatch_start
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
IF NET_DEBUG
    PHA
    JSR net_debug_stage
    PLA
ENDIF
.net_dispatch_done
IF NET_DEBUG
    PHA
    JSR net_debug_result
    PLA
ENDIF
    RTS

\ Publish a prepared command and restore the caller's interrupt state. Custom
\ wait loops such as PING use this entry so Escape remains responsive without
\ retaining the IRQ mask used to construct the shared JIM command block.
.net_dispatch_start
    LDA #NET_DISPATCH
    STA SERVICE_COMMAND
    LDA net_saved_p
    PHA
    PLP
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
    JSR net_data_write
    LDY #0
.net_url_open_copy
    LDA (net_ptr),Y
    JSR net_data_write
    BEQ net_url_open_go
    INY
    CPY #220
    BCC net_url_open_copy
    LDA #0
    JSR net_data_write
    LDA #&23                \ NET_ERR_PARAM
    PHA
    LDA net_saved_p
    PHA
    PLP
    PLA
    RTS
.net_url_open_go
    JMP net_dispatch_wait

\ Read up to NET_IO_MAX bytes into the fixed JIM RX buffer.
\ Returns result in A and the 16-bit byte count in net_length.
.net_url_read
    LDA #NET_CMD_URL_READ
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
    JSR net_data_read        \ discard high byte
    PLP
    LDA net_result
    RTS

\ X/Y point to A bytes in host RAM. Returns result in A and consumed count in
\ net_length. The caller retries any unconsumed tail.
.net_url_write
    STA net_write_length
    STX net_ptr
    STY net_ptr + 1
    PHP
    SEI
    JSR net_select_tx
    LDY #0
.net_url_write_copy
    CPY net_write_length
    BEQ net_url_write_command
    LDA (net_ptr),Y
    JSR net_data_write
    INY
    BNE net_url_write_copy
.net_url_write_command
    PLP
    LDA #NET_CMD_URL_WRITE
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
.net_saved_p
    EQUB 0
.net_cursor_lo
    EQUB 0
.net_cursor_mi
    EQUB 0
.net_cursor_hi
    EQUB 0
.net_cursor_timeout
    EQUB 0
IF NET_DEBUG
.net_debug_value
    EQUB 0
ENDIF
.net_rx_host
    SKIP NET_IO_MAX + 1
