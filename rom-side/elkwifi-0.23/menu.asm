\ MENU downloads the active source, adapts the stock payload for Pi1MHz JIM,
\ then runs it on the I/O processor. The RAM return stub keeps this safe if
\ the payload changes ROMSEL, and avoids executing host code on a Tube parasite.

menu_tape_addr = &1FC0
menu_return_addr = &1FD0

.menu_cmd
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

    \ The stock ElkWiFi MENU is a cassette filing-system program. If ADFS,
    \ MMFS or another filing system is current, it renders the first catalogue
    \ row and returns to the prompt. Invoke the same host command that works
    \ interactively; direct OSBYTE &8C is not equivalent under Electron ADFS.
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
