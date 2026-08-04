\ MENU downloads the active source, adapts the stock payload for Pi1MHz JIM,
\ then defers its BASIC CALL through the keyboard buffer.

.menu_cmd
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
    lda &0E00
    beq menu_download_invalid
    jsr menusrc_patch_menu

    ldx #0
.menu_queue_call
    stx temp
    lda #&99
    ldy menu_call,x
    bmi menu_quit
    ldx #0
    jsr osbyte
    ldx temp
    inx
    bne menu_queue_call
.menu_quit
    jmp call_claimed

.menu_download_invalid
    jsr printtext
    equs "Menu download failed",&0D,&EA
    jmp menu_quit

.menu_call
    equs "CALL &E00",&0D
    equb &FF
    equb &EA
