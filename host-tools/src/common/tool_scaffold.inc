\ Shared executable skeleton for planned, independently loadable SSD tools.
.start
    LDX #LO(tool_text)
    LDY #HI(tool_text)
    STX tool_read + 1
    STY tool_read + 2
.tool_print_loop
    LDY #0
.tool_read
    LDA &FFFF,Y
    BEQ tool_done
    JSR OSASCI
    INC tool_read + 1
    BNE tool_print_loop
    INC tool_read + 2
    JMP tool_print_loop
.tool_done
    RTS
