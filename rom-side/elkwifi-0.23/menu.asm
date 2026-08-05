\ MENU downloads the active source, adapts the stock payload for Pi1MHz JIM,
\ then runs it on the I/O processor. The RAM return stub keeps this safe if
\ the payload changes ROMSEL, and avoids executing host code on a Tube parasite.

menu_tape_addr = &1FC0
menu_return_addr = &1FD0

.menu_cmd
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
