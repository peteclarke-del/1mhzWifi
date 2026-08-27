\ Small host-side loader shared by the measured MMFS/ADFS and DFS envelopes.
\ At &2000 it lies above DFS OSHWM=&1F00. With HIMEM=&1D00 it initially lies
\ in writable display RAM, then survives because MODE 4 starts at &5800. The
\ main image starts at &2200, beyond the loader's guarded extent.

INCLUDE "src/common/mos.inc"

loader_ptr = &70
LOADER_START = &2000
LOADER_LIMIT = &2200
MAIN_END = APP_START + MAIN_SIZE

ORG LOADER_START
GUARD LOADER_LIMIT

.start
    LDA #&83
    JSR OSBYTE
    STX LOADER_COOKIE + 2
    STY LOADER_COOKIE + 3
    \ With a Tube active, &83 is the parasite language's OSHWM and says
    \ nothing about this &FFFF2000 I/O-processor image. The load metadata is
    \ the processor-selection contract; defer to the fixed host envelope.
    LDA #&EA
    LDX #0
    LDY #&FF
    JSR OSBYTE
    CPX #0
    BNE loader_address_ok
    LDX LOADER_COOKIE + 2
    LDY LOADER_COOKIE + 3
    CPY #HI(LOADER_START)
    BCC loader_address_ok
    BNE loader_wrong_envelope
    CPX #LO(LOADER_START)
    BCC loader_address_ok
    BEQ loader_address_ok
.loader_wrong_envelope
    LDX #LO(wrong_envelope_text)
    LDY #HI(wrong_envelope_text)
    JSR loader_print
    RTS

.loader_address_ok
    LDA #&84
    JSR OSBYTE
    STX LOADER_COOKIE + 4
    STY LOADER_COOKIE + 5
    LDA #'N'
    STA LOADER_COOKIE
    LDA #'T'
    STA LOADER_COOKIE + 1
    LDA #1
    LDX #loader_ptr
    LDY #0
    JSR OSARGS
    LDY #0
.loader_prefix
    LDA target_command,Y
    STA loader_command,Y
    INY
    CMP #' '
    BNE loader_prefix
    LDX #0
.loader_tail
    LDA (loader_ptr,X)
    CMP #13
    BEQ loader_tail_done
    CPY #loader_command_end - loader_command - 1
    BCS loader_tail_done
    STA loader_command,Y
    INY
    INC loader_ptr
    BNE loader_tail_next
    INC loader_ptr + 1
.loader_tail_next
    JMP loader_tail
.loader_tail_done
    LDA #13
    STA loader_command,Y

    \ Preserve the current display mode when its host screen boundary already
    \ leaves room for the main image. With a Tube active OSBYTE &84 describes
    \ the parasite, so retain MODE 4 as the measured host fallback.
    LDA #&EA
    LDX #0
    LDY #&FF
    JSR OSBYTE
    CPX #0
    BNE loader_select_mode4
    LDA LOADER_COOKIE + 5
    CMP #HI(MAIN_END)
    BCC loader_select_mode4
    BNE loader_screen_ready
    LDA LOADER_COOKIE + 4
    CMP #LO(MAIN_END)
    BCS loader_screen_ready
.loader_select_mode4
    LDA #22
    JSR OSWRCH
    LDA #4
    JSR OSWRCH
.loader_screen_ready

    \ OSBYTE &84 is a language-processor value when a Tube is active. Acorn's
    \ Tube contract returns the parasite HIMEM/program boundary, not the I/O
    \ processor's host screen boundary, so comparing it with MAIN_END can
    \ reject a perfectly valid host image. The &FFFFxxxx file addresses keep
    \ both loader stages in the I/O processor; after the guarded mode choice the host
    \ range &2200-MAIN_END is below screen memory. Retain the measured HIMEM
    \ check when no Tube is active, where &84 describes the host directly.
    LDA #&EA
    LDX #0
    LDY #&FF
    JSR OSBYTE
    CPX #0
    BNE loader_run
    LDA #&84
    JSR OSBYTE
    CPY #HI(MAIN_END)
    BCC loader_no_room
    BNE loader_run
    CPX #LO(MAIN_END)
    BCC loader_no_room
.loader_run
    LDX #LO(loader_command)
    LDY #HI(loader_command)
    JSR OSCLI
    RTS
.loader_no_room
    LDX #LO(no_room_text)
    LDY #HI(no_room_text)
.loader_print
    STX loader_ptr
    STY loader_ptr + 1
    LDY #0
.loader_print_loop
    LDA (loader_ptr),Y
    BEQ loader_print_done
    JSR OSASCI
    INY
    BNE loader_print_loop
.loader_print_done
    RTS

.target_command
IF LOADER_ID = 1
    EQUS "NTMENU "
ELIF LOADER_ID = 2
    EQUS "NTTEL "
ELIF LOADER_ID = 3
    EQUS "NTSSH "
ELIF LOADER_ID = 6
    EQUS "NTHWD "
ELIF LOADER_ID = 7
    EQUS "NTSFTP "
ELSE
    ERROR "Unknown LOADER_ID"
ENDIF
.wrong_envelope_text
    EQUS "NetTools loader requires OSHWM <= &2000",13,0
.no_room_text
    EQUS "NetTools loader could not obtain MODE 4 RAM",13,0
.loader_command
    SKIP 96
.loader_command_end

.end
SAVE start, end, start
