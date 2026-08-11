\ MENU downloads the active source, adapts the stock payload for Pi1MHz JIM,
\ then runs it on the I/O processor. The RAM return stub keeps this safe if
\ the payload changes ROMSEL, and avoids executing host code on a Tube parasite.

menu_tape_addr = &1FC0
menu_return_addr = &1FD0
menu_basic_slot = heap+&E6

.menu_cmd
    \ The published default MENU payload is an Electron program. Other hosts
    \ must select a machine-appropriate payload with MENUSRC.
    jsr menusrc_check_menu_platform
    bcc menu_platform_ok
    jmp menu_quit
.menu_platform_ok
    \ The stock ElkWiFi MENU is a cassette filing-system program, and heap at
    \ &0900 overlaps Electron ADFS workspace. Select cassette filing before
    \ constructing the WGET command or touching heap. This matches the proven
    \ interactive sequence: *TAPE followed by *MENU.
    jsr wicfs_release_tape_trap
    ldx #(menu_tape_command_end-menu_tape_command)-1
.menu_copy_tape_command
    lda menu_tape_command,x
    sta menu_tape_addr,x
    dex
    bpl menu_copy_tape_command
    ldx #<menu_tape_addr
    ldy #>menu_tape_addr
    jsr oscli

    jsr printtext
    equs "Downloading menu",&0D,&EA
    jsr menusrc_make_wget
    bcs menu_quit
    lda #0
    sta &0E00
    sta net_transfer_ok
    ldx #<heap
    ldy #>heap
    jsr oscli
    lda net_transfer_ok
    beq menu_download_invalid
    lda net_bytes_hi
    bne menu_download_size_ok
    lda net_bytes_lo
    cmp #16
    bcc menu_download_invalid
.menu_download_size_ok
    \ A directly executable menu starts with a subroutine call or jump. This
    \ catches HTTP error text and incomplete transfers before executing them.
    lda &0E00
    cmp #&20
    beq menu_download_entry_ok
    cmp #&4C
    bne menu_download_invalid
.menu_download_entry_ok
    jsr menusrc_patch_menu

    jsr printtext
    equs "Starting menu",&0D,&EA

    \ The stock program is tail-called from BASIC and eventually exits through
    \ an OSBYTE RTS. Put an equivalent return target above the downloaded
    \ payload, rather than in the &0900 filing-system workspace or in a
    \ sideways-ROM address which the program may have paged out.
    ldx #(menu_return_stub_end-menu_return_stub)-1
.menu_copy_return_stub
    lda menu_return_stub,x
    sta menu_return_addr,x
    dex
    bpl menu_copy_return_stub
    lda #>(menu_return_addr-1)
    pha
    lda #<(menu_return_addr-1)
    pha
    jmp &0E00
.menu_quit
    jmp call_claimed

.menu_tape_command
    equs "TAPE",&0D
.menu_tape_command_end

\ WiCFS suppresses OSBYTE &8C while a downloaded UEF is active. Multi-stage
\ cassette loaders, including Zalaga, restore the MOS vectors and issue *TAPE;
\ suppressing that request is part of the original WiCFS contract. MENU is the
\ one controlled transition back to cassette state. Restore the BYTEV saved in
\ the RAM trap before MENU deliberately executes its own TAPE command.
.wicfs_release_tape_trap
    lda BYTEV
    cmp #<notape
    bne wicfs_release_tape_done
    lda BYTEV+1
    cmp #>notape
    bne wicfs_release_tape_done
    php
    sei
    lda notape+(osb_j-osb_s)+1
    sta BYTEV
    lda notape+(osb_j-osb_s)+2
    sta BYTEV+1
    plp
.wicfs_release_tape_done
    rts

.menu_download_invalid
    jsr printtext
    equs "Menu download failed",&0D,&EA
    jmp menu_quit

.menu_return_stub
    pla
    tax
    pla
    tay
    lda #0
    rts
.menu_return_stub_end

\ Enter the installed BASIC on the host processor, leaving an attached Tube
\ enabled and otherwise untouched. The stock menu calls this only when Tube
\ services are active. A cold host BASIC otherwise derives PAGE from the
\ active Tube environment. Queue PAGE=&E00 before the short internal QR
\ command so CHAIN uses the same host BASIC workspace with Tube on and off.
\ The complete fourteen-byte sequence fits in the Electron keyboard buffer.
.menu_host_cmd
    jsr menu_find_basic
    bcc menu_host_basic_found
    jsr printtext
    equs "Host BASIC ROM not found",&0D,&EA
    jmp call_claimed
.menu_host_basic_found
    ldx #0
.menu_host_queue
    stx temp
    lda #&99
    ldy menu_host_commands,x
    bmi menu_host_queued
    ldx #0
    jsr osbyte
    ldx temp
    inx
    bne menu_host_queue
.menu_host_queued
    ldx #(menu_host_enter_end-menu_host_enter)-1
.menu_host_copy
    lda menu_host_enter,x
    sta menu_return_addr,x
    dex
    bpl menu_host_copy

    \ Patch both values before paging this ROM out. The copied trampoline has
    \ no dependency on data in the 1MHzWifi ROM after it selects BASIC.
    lda menu_basic_slot
    sta menu_return_addr+(menu_host_slot_immediate-menu_host_enter)+1
    lda #&81
    ldx #0
    ldy #&FF
    jsr osbyte
    stx menu_return_addr+(menu_host_machine_immediate-menu_host_enter)+1
    jmp menu_return_addr

\ Find the highest-priority language ROM whose title begins with BASIC.
\ OSRDRM reads it without changing the currently selected 1MHzWifi ROM.
.menu_find_basic
    lda #15
.menu_find_basic_slot
    sta menu_basic_slot
    lda #6
    sta &F6
    lda #&80
    sta &F7
    ldy menu_basic_slot
    jsr &FFB9
    and #&40
    beq menu_find_basic_next
    lda #9
    sta &F6
    jsr menu_basic_match
    bcc menu_find_basic_done
.menu_find_basic_next
    lda menu_basic_slot
    beq menu_find_basic_missing
    sec
    sbc #1
    bcs menu_find_basic_slot
.menu_find_basic_missing
    sec
    rts
.menu_find_basic_done
    clc
    rts

.menu_basic_match
    ldy menu_basic_slot
    jsr &FFB9
    ldx &F6
    cmp menu_basic_name-9,x
    bne menu_basic_mismatch
    inc &F6
    lda &F6
    cmp #14
    bne menu_basic_match
    clc
    rts
.menu_basic_mismatch
    sec
    rts

.menu_host_commands
    equs "PAGE=&E00",&0D
    equs "*QR",&0D
    equb &FF
.menu_basic_name
    equs "BASIC"

\ This code runs from RAM because the instruction after ROM selection cannot
\ be fetched from 1MHzWifi. Electron ROMSEL is &FE05; BBC B, B+, Master and
\ Compact use &FE30. A=1 is the normal cold language-entry reason.
.menu_host_enter
.menu_host_slot_immediate
    lda #0
    sta &F4
    sta &028C
.menu_host_machine_immediate
    ldx #0
    cpx #1
    beq menu_host_select_electron
    sta &FE30
    bne menu_host_selected
.menu_host_select_electron
    pha
    lda #&0C
    sta &FE05
    pla
    sta &FE05
.menu_host_selected
    lda #0
    sta &025D
    lda #1
    jmp &8000
.menu_host_enter_end
