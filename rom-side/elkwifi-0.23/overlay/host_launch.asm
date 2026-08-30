\ Host-side cassette and BASIC transitions shared by the generic UEF loader.
\ These routines never access, reset, disable or transfer through a Tube.

host_tape_addr = &1FC0
host_return_addr = &1FD0
host_basic_slot = heap+&E6

.host_select_tape
    \ Preserve the active disk filing system before selecting cassette. WiCFS
    \ consumes this snapshot so final release returns to ADFS, DFS or MMFS.
    jsr release_owned_wicfs
    bcs host_tape_invalid
    jsr wicfs_snapshot_pre_tape
    jsr wicfs_release_tape_trap
    bcc host_tape_released
.host_tape_invalid
    jsr print_wicfs_power_cycle
    sec
    rts
.host_tape_released
    ldx #(host_tape_command_end-host_tape_command)-1
.host_copy_tape_command
    lda host_tape_command,x
    sta host_tape_addr,x
    dex
    bpl host_copy_tape_command
    ldx #<host_tape_addr
    ldy #>host_tape_addr
    jsr oscli
    clc
    rts

.host_tape_command
    equs "TAPE",&0D
.host_tape_command_end

.print_wicfs_power_cycle
    jsr printtext
    equs "WiCFS state invalid; power cycle",&0D,&EA
    rts

\ WiCFS suppresses OSBYTE &8C while a UEF is active. Restore the BYTEV saved
\ in the RAM trap before deliberately selecting the native cassette system.
.wicfs_release_tape_trap
    lda BYTEV
    cmp #<notape
    bne wicfs_release_tape_done
    lda BYTEV+1
    cmp #>notape
    bne wicfs_release_tape_done
    jsr wicfs_state_load
    bcs wicfs_release_tape_invalid
    php
    sei
    lda bytev_rtn
    sta BYTEV
    lda bytev_rtn+1
    sta BYTEV+1
    plp
.wicfs_release_tape_done
    clc
    rts
.wicfs_release_tape_invalid
    sec
    rts

\ Enter the installed BASIC on the host processor while leaving an attached
\ Tube enabled and untouched. Queue PAGE=&E00 before the short internal QR
\ command so CHAIN uses the same host BASIC workspace with Tube on and off.
.host_basic_cmd
    jsr host_find_basic
    bcc host_basic_found
    jsr printtext
    equs "Host BASIC ROM not found",&0D,&EA
    jmp call_claimed
.host_basic_found
    ldx #0
.host_basic_queue
    stx temp
    lda #&99
    ldy host_basic_commands,x
    bmi host_basic_queued
    ldx #0
    jsr osbyte
    ldx temp
    inx
    bne host_basic_queue
.host_basic_queued
.host_enter_basic
    ldx #(host_basic_enter_end-host_basic_enter)-1
.host_basic_copy
    lda host_basic_enter,x
    sta host_return_addr,x
    dex
    bpl host_basic_copy

    lda host_basic_slot
    sta host_return_addr+(host_basic_slot_immediate-host_basic_enter)+1
    lda #&81
    ldx #0
    ldy #&FF
    jsr osbyte
    stx host_return_addr+(host_machine_immediate-host_basic_enter)+1
    jmp host_return_addr

\ Find the highest-priority language ROM whose title begins with BASIC.
.host_find_basic
    lda #15
.host_find_basic_slot
    sta host_basic_slot
    lda #6
    sta &F6
    lda #&80
    sta &F7
    ldy host_basic_slot
    jsr &FFB9
    and #&40
    beq host_find_basic_next
    lda #9
    sta &F6
    jsr host_basic_match
    bcc host_find_basic_done
.host_find_basic_next
    lda host_basic_slot
    beq host_find_basic_missing
    sec
    sbc #1
    bcs host_find_basic_slot
.host_find_basic_missing
    sec
    rts
.host_find_basic_done
    clc
    rts

.host_basic_match
    ldy host_basic_slot
    jsr &FFB9
    ldx &F6
    cmp host_basic_name-9,x
    bne host_basic_mismatch
    inc &F6
    lda &F6
    cmp #14
    bne host_basic_match
    clc
    rts
.host_basic_mismatch
    sec
    rts

.host_basic_commands
    equs "PAGE=&E00",&0D
    equs "*QR",&0D
    equb &FF
.host_basic_name
    equs "BASIC"

\ This trampoline runs from RAM because selecting BASIC pages this ROM out.
\ Electron ROMSEL is &FE05; BBC B, B+, Master and Compact use &FE30.
.host_basic_enter
    php
    sei
.host_basic_slot_immediate
    lda #0
    sta &F4
    sta &028C
.host_machine_immediate
    ldx #0
    cpx #1
    beq host_select_electron
    sta &FE30
    jmp host_selected
.host_select_electron
    cmp #8
    bcs host_select_electron_slot
    pha
    lda #&0C
    sta &FE05
    pla
.host_select_electron_slot
    sta &FE05
.host_selected
    tax
    lda #0
    sta &025D
    lda #1
    plp
    jmp &8000
.host_basic_enter_end
