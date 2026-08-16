\ Pi1MHz real-hardware versus emulator diagnostic.
\ Host-resident, read-only with respect to filing systems and Tube hardware.

INCLUDE "src/common/mos.inc"

command_line = &70

ORG APP_START
GUARD APP_LIMIT

.start
    JSR application_check_workspace
    BCS hwdtest_memory_safe
    JMP application_exit
.hwdtest_memory_safe
    LDA #0
    STA diag_final_fail
    LDX #LO(title_text)
    LDY #HI(title_text)
    JSR tool_print_string

    LDA LOADER_COOKIE
    CMP #'N'
    BNE loader_cookie_missing
    LDA LOADER_COOKIE + 1
    CMP #'T'
    BNE loader_cookie_missing
    LDX #LO(loader_envelope_text)
    LDY #HI(loader_envelope_text)
    JSR tool_print_string
    LDA LOADER_COOKIE + 3
    JSR tool_print_hex
    LDA LOADER_COOKIE + 2
    JSR tool_print_hex
    LDX #LO(loader_himem_text)
    LDY #HI(loader_himem_text)
    JSR tool_print_string
    LDA LOADER_COOKIE + 5
    JSR tool_print_hex
    LDA LOADER_COOKIE + 4
    JSR tool_print_hex
    JSR OSNEWL
    JMP loader_cookie_done
.loader_cookie_missing
    LDX #LO(loader_missing_text)
    LDY #HI(loader_missing_text)
    JSR tool_print_string
.loader_cookie_done

    \ Record where MOS actually entered the image and whether OSBYTE reports
    \ host or parasite memory. These markers deliberately bracket the call:
    \ a Tube deadlock leaves an unambiguous last completed operation.
    LDX #LO(entry_text)
    LDY #HI(entry_text)
    JSR tool_print_string
    LDA #HI(start)
    JSR tool_print_hex
    LDA #LO(start)
    JSR tool_print_hex
    LDA #' '
    JSR OSWRCH
    LDA start
    JSR tool_print_hex
    JSR OSNEWL

    LDX #LO(before_82_text)
    LDY #HI(before_82_text)
    JSR tool_print_string
    LDA #&82                 \ high word of the current processor address
    LDX #0
    LDY #0
    JSR OSBYTE
    STX diag_host_hi
    STY diag_host_hi + 1
    LDX #LO(after_82_text)
    LDY #HI(after_82_text)
    JSR tool_print_string
    LDA diag_host_hi + 1
    JSR tool_print_hex
    LDA diag_host_hi
    JSR tool_print_hex
    JSR OSNEWL

    LDX #LO(before_81_text)
    LDY #HI(before_81_text)
    JSR tool_print_string
    LDA #&81                 \ legacy INKEY(-256) machine byte; diagnostic only
    LDX #0
    LDY #&FF
    JSR OSBYTE
    STX diag_machine
    LDX #LO(after_81_text)
    LDY #HI(after_81_text)
    JSR tool_print_string
    LDA diag_machine
    JSR tool_print_hex
    JSR OSNEWL

    LDA #&EA                 \ Tube presence/status query, no Tube transfer
    LDX #0
    LDY #&FF
    JSR OSBYTE
    STX diag_tube
    LDX #LO(tube_text)
    LDY #HI(tube_text)
    JSR tool_print_string
    LDA diag_tube
    JSR tool_print_hex
    JSR OSNEWL

    LDA #&83                 \ lowest user address, returned in YX
    JSR OSBYTE
    STX diag_word
    STY diag_word + 1
    LDX #LO(oshwm_text)
    LDY #HI(oshwm_text)
    JSR tool_print_string
    JSR print_diag_word

    LDA #&84                 \ highest user address, returned in YX
    JSR OSBYTE
    STX diag_word
    STY diag_word + 1
    LDX #LO(himem_text)
    LDY #HI(himem_text)
    JSR tool_print_string
    JSR print_diag_word

    LDX #LO(vectors_text)
    LDY #HI(vectors_text)
    JSR tool_print_string
    LDA &0213                \ FILEV high then low for normal hex notation
    JSR tool_print_hex
    LDA &0212
    JSR tool_print_hex
    LDA #' '
    JSR OSWRCH
    LDA &021F                \ FSCV
    JSR tool_print_hex
    LDA &021E
    JSR tool_print_hex
    LDA #' '
    JSR OSWRCH
    LDA &020D                \ WORDV
    JSR tool_print_hex
    LDA &020C
    JSR tool_print_hex
    JSR OSNEWL

    \ Reproduce the live adjacent-register case without dispatching a command.
    LDX #LO(selector_request_text)
    LDY #HI(selector_request_text)
    JSR tool_print_string
    PHP
    SEI
    LDA #0
    STA net_cursor_timeout
    LDA #0
    STA SERVICE_ADDR_LO
    LDA #&F0
    STA SERVICE_ADDR_MI
    LDA #&FF
    STA SERVICE_ADDR_HI
    LDA #&5E
    STA SERVICE_DATA
    LDA SERVICE_ADDR_LO
    STA diag_regs
    LDA SERVICE_ADDR_MI
    STA diag_regs + 1
    LDA SERVICE_ADDR_HI
    STA diag_regs + 2
    LDA #0
    STA SERVICE_ADDR_LO
    LDA SERVICE_DATA
    STA diag_regs + 3
    PLP

    LDX #LO(adjacent_text)
    LDY #HI(adjacent_text)
    JSR tool_print_string
    LDX #0
.print_regs
    LDA diag_regs,X
    JSR tool_print_hex
    INX
    CPX #4
    BEQ adjacent_result
    LDA #' '
    JSR OSWRCH
    JMP print_regs
.adjacent_result
    LDA diag_regs
    CMP #1
    BNE adjacent_fail
    LDA diag_regs + 1
    CMP #&F0
    BNE adjacent_fail
    LDA diag_regs + 2
    CMP #&FF
    BNE adjacent_fail
    LDA diag_regs + 3
    CMP #&5E
    BNE adjacent_fail
    LDX #LO(pass_text)
    LDY #HI(pass_text)
    BNE adjacent_print_result
.adjacent_fail
    INC diag_final_fail
    LDX #LO(fail_text)
    LDY #HI(fail_text)
.adjacent_print_result
    JSR tool_print_string

    \ Round-trip sixteen bytes through a non-command Services JIM page using
    \ the explicitly addressed pattern used by the working ROM transport.
    \ This remains correct when the FIQ auto-increment read-back is not visible
    \ before the Electron begins its next bus access.
    PHP
    SEI
    LDA #0
    LDX #&EF
    LDY #&FF
    JSR net_select_address
    LDX #0
.block_write
    LDA block_pattern,X
    JSR net_data_write
    INX
    CPX #16
    BNE block_write
    LDX #0
    STX diag_block_bad
    LDA #0
    LDX #&EF
    LDY #&FF
    JSR net_select_address
    LDX #0
.block_read
    JSR net_data_read
    CMP block_pattern,X
    BEQ block_next
    INC diag_block_bad
.block_next
    INX
    CPX #16
    BNE block_read
    PLP
    LDX #LO(block_text)
    LDY #HI(block_text)
    JSR tool_print_string
    LDA diag_block_bad
    BEQ block_pass
    INC diag_final_fail
    LDX #LO(fail_text)
    LDY #HI(fail_text)
    BNE block_print
.block_pass
    LDX #LO(pass_text)
    LDY #HI(pass_text)
.block_print
    JSR tool_print_string
    LDX #LO(ack_text)
    LDY #HI(ack_text)
    JSR tool_print_string
    LDA net_cursor_timeout
    BEQ ack_pass
    INC diag_final_fail
    LDX #LO(fail_text)
    LDY #HI(fail_text)
    BNE ack_print
.ack_pass
    LDX #LO(pass_text)
    LDY #HI(pass_text)
.ack_print
    JSR tool_print_string

    \ Issue secure capability command 94 and report the raw bounded result.
    \ Read the command byte back before dispatch, as the ROM does, so the
    \ asynchronous data-port callback has completed before FCAA consumes it.
    PHP
    SEI
    LDA #0
    LDX #&F0
    LDY #&FF
    JSR net_select_address
    LDA #94
    JSR net_data_write
    LDA #0
    LDX #&F0
    LDY #&FF
    JSR net_select_address
    JSR net_data_read
    CMP #94
    BNE caps_protocol
    LDA #&F0
    STA SERVICE_COMMAND
    PLP
    LDA #&2C
    STA diag_wait_lo
    LDA #1
    STA diag_wait_hi
.caps_wait
    LDA SERVICE_COMMAND
    BPL caps_done
    LDA diag_wait_lo
    BNE caps_dec
    LDA diag_wait_hi
    BEQ caps_timeout
    DEC diag_wait_hi
.caps_dec
    DEC diag_wait_lo
    LDA #19
    JSR OSBYTE
    JMP caps_wait
.caps_timeout
    LDA #NET_LOCAL_TIMEOUT
    BNE caps_done
.caps_protocol
    LDA #NET_LOCAL_PROTOCOL
.caps_done
    STA diag_caps_result
    LDX #LO(caps_text)
    LDY #HI(caps_text)
    JSR tool_print_string
    LDA diag_caps_result
    JSR tool_print_hex
    JSR OSNEWL
    LDA diag_caps_result
    BEQ caps_result_recorded
    INC diag_final_fail
.caps_result_recorded

    \ Capture the capability structure even on a protocol error. This
    \ distinguishes an absent command from a stale or partly published reply.
    PHP
    SEI
    LDA #1
    LDX #&F0
    LDY #&FF
    JSR net_select_address
    LDX #0
.caps_capture
    JSR net_data_read
    STA diag_caps_bytes,X
    INX
    CPX #10
    BNE caps_capture
    PLP
    LDX #LO(caps_1_text)
    LDY #HI(caps_1_text)
    JSR tool_print_string
    LDX #0
    JSR print_five_bytes
    LDX #LO(caps_6_text)
    LDY #HI(caps_6_text)
    JSR tool_print_string
    LDX #5
    JSR print_five_bytes
    LDA diag_caps_bytes
    CMP #1
    BNE caps_invalid
    LDA diag_caps_bytes + 2
    AND #3
    CMP #3                    \ random and managed SSH must both be ready
    BNE caps_invalid
    LDA diag_caps_bytes + 5
    CMP #1                    \ provider readiness byte
    BNE caps_invalid
    LDA diag_caps_bytes + 7
    CMP #'N'
    BNE caps_invalid
    LDA diag_caps_bytes + 8
    CMP #'T'
    BNE caps_invalid
    LDA diag_caps_bytes + 9
    CMP #'S'
    BEQ caps_validated
.caps_invalid
    INC diag_final_fail
.caps_validated

    LDX #LO(continue_roms_text)
    LDY #HI(continue_roms_text)
    JSR tool_print_string
    JSR OSRDCH
    LDA #12
    JSR OSWRCH
    LDX #LO(roms_text)
    LDY #HI(roms_text)
    JSR tool_print_string
    LDX #LO(roms_command)
    LDY #HI(roms_command)
    JSR OSCLI

    LDX #LO(continue_version_text)
    LDY #HI(continue_version_text)
    JSR tool_print_string
    JSR OSRDCH
    LDA #12
    JSR OSWRCH
    LDX #LO(version_text)
    LDY #HI(version_text)
    JSR tool_print_string
    JSR diagnostic_kernel_version
    BCC diagnostic_final_result
    INC diag_final_fail
.diagnostic_final_result
    LDX #LO(final_result_text)
    LDY #HI(final_result_text)
    JSR tool_print_string
    LDA diag_final_fail
    BEQ diagnostic_final_pass
    LDX #LO(final_fail_text)
    LDY #HI(final_fail_text)
    BNE diagnostic_final_print
.diagnostic_final_pass
    LDX #LO(final_pass_text)
    LDY #HI(final_pass_text)
.diagnostic_final_print
    JSR tool_print_string
    JMP application_exit

\ Query ElkWiFi status directly rather than nesting another star command.
\ This keeps the last screen useful when a higher-priority ROM intercepts
\ VERSION, and independently proves the command-80 Pi firmware response.
.diagnostic_kernel_version
    PHP
    SEI
    LDA #0
    LDX #&F0
    LDY #&FF
    JSR net_select_address
    LDA #80
    JSR net_data_write
    LDA #0
    LDX #&F0
    LDY #&FF
    JSR net_select_address
    JSR net_data_read
    CMP #80
    BNE diagnostic_version_protocol
    LDA #&F0
    STA SERVICE_COMMAND
    PLP
    LDA #&2C
    STA diag_wait_lo
    LDA #1
    STA diag_wait_hi
.diagnostic_version_wait
    LDA SERVICE_COMMAND
    BPL diagnostic_version_result
    LDA diag_wait_lo
    BNE diagnostic_version_dec
    LDA diag_wait_hi
    BEQ diagnostic_version_timeout
    DEC diag_wait_hi
.diagnostic_version_dec
    DEC diag_wait_lo
    LDA #19
    JSR OSBYTE
    JMP diagnostic_version_wait
.diagnostic_version_timeout
    LDA #NET_LOCAL_TIMEOUT
.diagnostic_version_result
    BNE diagnostic_version_error
    LDA #1
    STA diag_response_index
.diagnostic_version_copy
    PHP
    SEI
    LDA diag_response_index
    LDX #&F0
    LDY #&FF
    JSR net_select_address
    JSR net_data_read
    STA diag_response_byte
    PLP
    LDA diag_response_byte
    BEQ diagnostic_version_done
    JSR OSWRCH
    INC diag_response_index
    BNE diagnostic_version_copy
.diagnostic_version_done
    CLC
    RTS
.diagnostic_version_protocol
    PLP
    LDA #NET_LOCAL_PROTOCOL
.diagnostic_version_error
    PHA
    LDX #LO(version_error_text)
    LDY #HI(version_error_text)
    JSR tool_print_string
    PLA
    JSR tool_print_hex
    JSR OSNEWL
    SEC
    RTS

.print_diag_word
    LDA diag_word + 1
    JSR tool_print_hex
    LDA diag_word
    JSR tool_print_hex
    JMP OSNEWL

.print_five_bytes
    LDY #5
.print_five_loop
    LDA diag_caps_bytes,X
    JSR tool_print_hex
    INX
    DEY
    BEQ print_five_done
    LDA #' '
    JSR OSWRCH
    JMP print_five_loop
.print_five_done
    JMP OSNEWL

.title_text
    EQUS "1MHzWifi HWDTEST D2",13,0
.entry_text
    EQUS "Entry/opcode: &",0
.loader_envelope_text
    EQUS "Loader OSHWM=&",0
.loader_himem_text
    EQUS " HIMEM=&",0
.loader_missing_text
    EQUS "Loader envelope unavailable",13,0
.before_82_text
    EQUS "Before OSBYTE &82",13,0
.after_82_text
    EQUS "After OSBYTE &82 high=&",0
.before_81_text
    EQUS "Before OSBYTE &81",13,0
.after_81_text
    EQUS "After OSBYTE &81 X=&",0
.tube_text
    EQUS "Tube X=&",0
.oshwm_text
    EQUS "OSHWM=&",0
.himem_text
    EQUS "MEMTOP=&",0
.vectors_text
    EQUS "FILEV FSCV WORDV: ",0
.adjacent_text
    EQUS "FCA6-9 after: ",0
.selector_request_text
    EQUS "FCA9 req 00 F0 FF <= 5E",13,0
.block_text
    EQUS "Addressed JIM block:",0
.ack_text
    EQUS "FCA9 callback ACK:",0
.caps_text
    EQUS "Secure CAPS result=&",0
.caps_1_text
    EQUS "CAPS 1-5: ",0
.caps_6_text
    EQUS "CAPS 6-10: ",0
.continue_roms_text
    EQUS "Capture this screen. Press a key.",13,0
.continue_version_text
    EQUS "Capture ROM list. Press a key.",13,0
.pass_text
    EQUS " PASS",13,0
.fail_text
    EQUS " FAIL",13,0
.roms_text
    EQUS "ROM list follows",13,0
.version_text
    EQUS "Pi1MHz status response follows",13,0
.version_error_text
    EQUS "Kernel status result=&",0
.final_result_text
    EQUS "HWDTEST RESULT ",0
.final_pass_text
    EQUS "PASS",13,0
.final_fail_text
    EQUS "FAIL",13,0
.roms_command
    EQUS "ROMS",13
.block_pattern
    EQUB &00,&FF,&55,&AA,&01,&FE,&10,&EF,&5A,&A5,&33,&CC,&0F,&F0,&69,&96
.diag_machine
    EQUB 0
.diag_host_hi
    EQUW 0
.diag_tube
    EQUB 0
.diag_word
    EQUW 0
.diag_regs
    SKIP 4
.diag_block_bad
    EQUB 0
.diag_caps_result
    EQUB 0
.diag_final_fail
    EQUB 0
.diag_caps_bytes
    SKIP 10
.diag_wait_lo
    EQUB 0
.diag_wait_hi
    EQUB 0
.diag_response_index
    EQUB 0
.diag_response_byte
    EQUB 0

INCLUDE "src/common/pi1mhz_net.asm"
INCLUDE "src/common/tool_common.asm"
INCLUDE "src/common/application.asm"

.end
SAVE start, end, start
