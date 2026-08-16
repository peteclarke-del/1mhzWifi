\ Validate the address envelope before a transient utility uses the mailbox.
\ A low-memory display mode can place HIMEM at the fixed DFS load address even
\ when OSHWM leaves the application area free. In that case select portable
\ MODE 4 before rejecting the image. This moves screen memory above the tools
\ on Electron and BBC-family hosts without interacting with an installed Tube.
.application_check_workspace
    LDA #&83                 \ OSHWM, returned in YX
    JSR OSBYTE
    STX application_oshwm
    STY application_oshwm + 1
    LDA #&84                 \ HIMEM/display boundary, returned in YX
    JSR OSBYTE
    STX application_himem
    STY application_himem + 1
    LDX application_oshwm
    LDY application_oshwm + 1
    CPY #HI(APP_START)
    BCC application_check_himem
    BNE application_memory_unsafe
    CPX #LO(APP_START)
    BCC application_check_himem
    BEQ application_check_himem
    BNE application_memory_unsafe

.application_check_himem
    LDX application_himem
    LDY application_himem + 1
    CPY #HI(end)
    BCC application_try_mode4
    BNE application_memory_safe
    CPX #LO(end)
    BCC application_try_mode4

.application_memory_safe
    SEC
    RTS

.application_try_mode4
    LDA #22
    JSR OSWRCH
    LDA #4
    JSR OSWRCH
    LDA #&84                 \ re-read HIMEM after changing display mode
    JSR OSBYTE
    STX application_himem
    STY application_himem + 1
    CPY #HI(end)
    BCC application_memory_unsafe
    BNE application_memory_safe
    CPX #LO(end)
    BCC application_memory_unsafe
    BCS application_memory_safe

.application_memory_unsafe
    LDX #0
.application_memory_error_loop
    LDA application_memory_error,X
    BEQ application_memory_error_done
    JSR OSASCI
    INX
    BNE application_memory_error_loop
.application_memory_error_done
    LDA application_oshwm + 1
    JSR application_print_hex
    LDA application_oshwm
    JSR application_print_hex
    LDX #0
.application_memory_himem_loop
    LDA application_memory_himem_text,X
    BEQ application_memory_himem_done
    JSR OSASCI
    INX
    BNE application_memory_himem_loop
.application_memory_himem_done
    LDA application_himem + 1
    JSR application_print_hex
    LDA application_himem
    JSR application_print_hex
    LDX #0
.application_memory_image_loop
    LDA application_memory_image_text,X
    BEQ application_memory_image_done
    JSR OSASCI
    INX
    BNE application_memory_image_loop
.application_memory_image_done
    LDA #HI(APP_START)
    JSR application_print_hex
    LDA #LO(APP_START)
    JSR application_print_hex
    LDA #'-'
    JSR OSASCI
    LDA #HI(end)
    JSR application_print_hex
    LDA #LO(end)
    JSR application_print_hex
    LDA #13
    JSR OSASCI
    CLC
    RTS

.application_print_hex
    PHA
    LSR A
    LSR A
    LSR A
    LSR A
    JSR application_print_nibble
    PLA
    AND #15
.application_print_nibble
    CMP #10
    BCC application_print_digit
    ADC #6
.application_print_digit
    ADC #'0'
    JMP OSASCI

.application_memory_error
    EQUS "NetTools memory: OSHWM=&", 0
.application_memory_himem_text
    EQUS " HIMEM=&", 0
.application_memory_image_text
    EQUS " image=&", 0
.application_oshwm
    EQUW 0
.application_himem
    EQUW 0

\ Leave a host-resident transient utility through the active OSCLI call.
\ Standard host utilities return with RTS both with and without a Tube. They
\ must not re-enter BASIC or modify the language program area on the way out.
.application_exit
    RTS
