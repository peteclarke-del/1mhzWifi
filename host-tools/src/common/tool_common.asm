\ Common routines for short, non-interactive NetTools clients.

.tool_print_string
    STX tool_print_read + 1
    STY tool_print_read + 2
    LDY #0
.tool_print_read
    LDA &FFFF,Y
    BEQ tool_print_done
    JSR OSASCI
    INY
    BNE tool_print_read
.tool_print_done
    RTS

.tool_print_hex
    PHA
    LSR A
    LSR A
    LSR A
    LSR A
    JSR tool_print_nibble
    PLA
    AND #15
.tool_print_nibble
    CMP #10
    BCC tool_print_digit
    ADC #'A' - 11
    JMP OSWRCH
.tool_print_digit
    ADC #'0'
    JMP OSWRCH

.tool_show_error
    PHA
    LDX #LO(tool_error_text)
    LDY #HI(tool_error_text)
    JSR tool_print_string
    PLA
    JSR tool_print_hex
    JMP OSNEWL

\ Copy the first command-tail word into tool_argument and NUL terminate it.
\ Returns C set when a non-empty argument was copied.
.tool_read_argument
    LDY #0
.tool_skip_space
    LDA (command_line),Y
    CMP #' '
    BNE tool_argument_start
    INY
    BNE tool_skip_space
.tool_argument_start
    CMP #13
    BEQ tool_argument_missing
    CMP #0
    BEQ tool_argument_missing
    LDX #0
.tool_argument_copy
    CMP #' '
    BEQ tool_argument_done
    CMP #13
    BEQ tool_argument_done
    CMP #0
    BEQ tool_argument_done
    STA tool_argument,X
    INX
    CPX #127
    BCS tool_argument_missing
    INY
    LDA (command_line),Y
    JMP tool_argument_copy
.tool_argument_done
    LDA #0
    STA tool_argument,X
    SEC
    RTS
.tool_argument_missing
    CLC
    RTS

.tool_print_u8
    PHA
    LDA #0
    STA tool_u8_had_hundreds
    PLA
    LDX #'0'
.tool_u8_hundreds
    CMP #100
    BCC tool_u8_hundreds_done
    SBC #100
    INX
    BNE tool_u8_hundreds
.tool_u8_hundreds_done
    PHA
    CPX #'0'
    BEQ tool_u8_no_hundreds
    PHA
    LDA #1
    STA tool_u8_had_hundreds
    PLA
    TXA
    JSR OSWRCH
.tool_u8_no_hundreds
    PLA
    LDX #'0'
.tool_u8_tens
    CMP #10
    BCC tool_u8_tens_done
    SBC #10
    INX
    BNE tool_u8_tens
.tool_u8_tens_done
    PHA
    CPX #'0'
    BNE tool_u8_show_tens
    LDA tool_u8_had_hundreds
    BEQ tool_u8_no_tens
.tool_u8_show_tens
    TXA
    JSR OSWRCH
.tool_u8_no_tens
    PLA
    CLC
    ADC #'0'
    JMP OSWRCH

.tool_error_text
    EQUS "NetTools 0.1.55 network error &", 0
.tool_u8_had_hundreds
    EQUB 0
.tool_argument
    SKIP 128
