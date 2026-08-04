\ Pi1MHz extension: persistent menu source through the &FCA6 services port.
\ The service ROM runs in the I/O processor, so use AP5-forwarded FRED
\ directly; Tube OSCLI/OSWORD calls are already marshalled to this processor.
\
\ Syntax: *MENUSRC
\         *MENUSRC <http-url>
\         *MENUSRC DEFAULT

svc_addr_lo = &A6
svc_addr_mid = &A7
svc_addr_hi = &A8
svc_data = &A9
svc_command = &AA

svc_menu_get = 84
svc_menu_set = 85
svc_menu_default = 86

menusrc_index = errorspace
menusrc_timeout_lo = errorspace+1
menusrc_timeout_hi = errorspace+2

.menusrc_cmd
 jsr skipspace1
 jsr read_cli_param
 lda #svc_menu_get
 cpx #0
 beq menusrc_submit
 jsr menusrc_is_default
 bcc menusrc_not_default
 lda #svc_menu_default
 bcs menusrc_submit
.menusrc_not_default
 lda #svc_menu_set

.menusrc_submit
 jsr menusrc_start
 bcs menusrc_done
 jsr menusrc_print_reply
.menusrc_done
 jmp call_claimed

\ Return carry set only for the exact, case-insensitive word DEFAULT.
.menusrc_is_default
 ldy #0
.menusrc_default_loop
 lda strbuf,y
 and #&DF
 cmp menusrc_default_word,y
 bne menusrc_not_default_word
 iny
 cpy #7
 bne menusrc_default_loop
 lda strbuf,y
 cmp #&0D
 bne menusrc_not_default_word
 sec
 rts
.menusrc_not_default_word
 clc
 rts
.menusrc_default_word
 equs "DEFAULT"

\ Submit the operation in A. Carry is set after a transport or service error.
.menusrc_start
 pha
 lda #0
 sta &FC00+svc_addr_lo
 lda #&FF
 sta &FC00+svc_addr_mid
 sta &FC00+svc_addr_hi
 pla
 pha
 sta &FC00+svc_data
 pla
 cmp #svc_menu_set
 bne menusrc_dispatch
 ldy #0
.menusrc_send_value
 lda strbuf,y
 cmp #&0D
 beq menusrc_send_end
 pha
 iny
 sty menusrc_index
 pla
 sta &FC00+svc_data
 ldy menusrc_index
 bne menusrc_send_value
.menusrc_send_end
 ldy #0
 sty &FC00+svc_data

.menusrc_dispatch
 lda #&FF
 sta &FC00+svc_command
 lda #0
 sta menusrc_timeout_lo
 lda #100
 sta menusrc_timeout_hi
.menusrc_wait
 lda &FC00+svc_command
 bpl menusrc_status
 dec menusrc_timeout_lo
 bne menusrc_wait
 lda #19                  \ yield to the Pi main-loop service poll
 jsr osbyte
 dec menusrc_timeout_hi
 bne menusrc_wait
 ldx #0
.menusrc_timeout_print
 lda menusrc_timeout_text,x
 beq menusrc_failed
 jsr osasci
 inx
 bne menusrc_timeout_print
.menusrc_failed
 sec
 rts

.menusrc_status
 cmp #0
 beq menusrc_response_pointer
 pha
 ldx #0
.menusrc_error_print
 lda menusrc_error_text,x
 beq menusrc_error_code
 jsr osasci
 inx
 bne menusrc_error_print
.menusrc_error_code
 pla
 jsr printhex
 jsr osnewl
 sec
 rts

.menusrc_response_pointer
 lda #1
 sta &FC00+svc_addr_lo
 clc
 rts

.menusrc_print_reply
 ldx #0
.menusrc_label_loop
 lda menusrc_label,x
 beq menusrc_print_loop
 jsr osasci
 inx
 bne menusrc_label_loop
.menusrc_print_loop
 lda #240
 sta menusrc_index
.menusrc_print_character
 lda &FC00+svc_data
 beq menusrc_print_end
 jsr osasci
 dec menusrc_index
 bne menusrc_print_character
 \ A floating data port has no zero terminator.  Bound direct *MENUSRC output
 \ just as tightly as the main compatibility driver.
 jmp menusrc_timeout_print
.menusrc_print_end
 jsr osnewl
 clc
 rts

\ Build "*WGET <configured-url> E00" in heap for *MENU.
.menusrc_make_wget
 ldx #0
.menusrc_prefix_loop
 lda menusrc_wget_prefix,x
 beq menusrc_prefix_done
 sta heap,x
 inx
 bne menusrc_prefix_loop
.menusrc_prefix_done
 stx menusrc_index
 lda #svc_menu_get
 jsr menusrc_start
 bcs menusrc_make_done
.menusrc_copy_url
 lda &FC00+svc_data
 beq menusrc_suffix
 ldy menusrc_index
 sta heap,y
 iny
 sty menusrc_index
 cpy #&F8
 bcc menusrc_copy_url
 bcs menusrc_url_long
.menusrc_suffix
 ldx #0
 ldy menusrc_index
.menusrc_suffix_loop
 lda menusrc_wget_suffix,x
 sta heap,y
 iny
 inx
 cmp #&0D
 bne menusrc_suffix_loop
 clc
.menusrc_make_done
 rts
.menusrc_url_long
 ldx #0
.menusrc_long_print
 lda menusrc_long_text,x
 bne menusrc_long_char
 jmp menusrc_failed
.menusrc_long_char
 jsr osasci
 inx
 bne menusrc_long_print

.menusrc_wget_prefix
 equs "*WGET ",0
.menusrc_wget_suffix
 equs " E00",&0D
.menusrc_label
 equs "Menu source: ",0
.menusrc_timeout_text
 equs "Pi1MHz ElkWiFi service not responding",&0D,0
.menusrc_error_text
 equs "Pi1MHz ElkWiFi error &",0
.menusrc_long_text
 equs "Menu source is too long",&0D,0

\ The published ElkWiFi MENU contains one inlined cartridge bank-select
\ sequence: LDA &FC34 / ORA #8 / STA &FC34. Replace it in place with a
\ length-preserving Pi1MHz JIM window-1 selection. A custom menu without the
\ stock sequence is left unchanged.
.menusrc_patch_menu
 lda #0
 sta zp
 lda #&0E
 sta zp+1
.menusrc_patch_page
 ldy #0
.menusrc_patch_next
 sty menusrc_index
 ldx #0
.menusrc_patch_compare
 lda (zp),y
 cmp menusrc_uart_bank,x
 bne menusrc_patch_mismatch
 iny
 inx
 cpx #8
 bne menusrc_patch_compare
 ldy menusrc_index
 ldx #0
.menusrc_patch_copy
 lda menusrc_jim_bank,x
 sta (zp),y
 iny
 inx
 cpx #8
 bne menusrc_patch_copy
 jsr menusrc_patch_catalogue
 rts
.menusrc_patch_mismatch
 ldy menusrc_index
 iny
 cpy #&F8
 bne menusrc_patch_next
 inc zp+1
 lda zp+1
 cmp #&20
 bne menusrc_patch_page
 rts

.menusrc_uart_bank
 equb &AD,&34,&FC,&09,&08,&8D,&34,&FC
.menusrc_jim_bank
 equb &A9,&01,&EA,&EA,&EA,&8D,&FE,&FC

\ The stock menu assumes its cartridge RAM bank remains selected indefinitely.
\ Pi1MHz shares the JIM aperture with other services, so make each TITLES read
\ reselect window 1. Patch only the known 2,907-byte payload and only when all
\ four instruction sites still contain their published bytes.
.menusrc_patch_catalogue
 lda net_bytes_lo
 cmp #&5B
 bne menusrc_patch_catalogue_fail
 lda net_bytes_hi
 cmp #&0B
 bne menusrc_patch_catalogue_fail
 ldx #0
.menusrc_catalogue_check_read
 lda menusrc_catalogue_reads,x
 sta zp
 lda menusrc_catalogue_reads+1,x
 sta zp+1
 ldy #0
 lda (zp),y
 cmp #&B9                    \ LDA &FD00,Y
 bne menusrc_patch_catalogue_fail
 iny
 lda (zp),y
 bne menusrc_patch_catalogue_fail
 iny
 lda (zp),y
 cmp #&FD
 bne menusrc_patch_catalogue_fail
 inx
 inx
 cpx #6
 bne menusrc_catalogue_check_read
 lda &0ECC
 cmp #&8D                    \ STA &FCFF
 bne menusrc_patch_catalogue_fail
 lda &0ECD
 cmp #&FF
 bne menusrc_patch_catalogue_fail
 lda &0ECE
 cmp #&FC
 bne menusrc_patch_catalogue_fail
 jmp menusrc_patch_catalogue_verified
.menusrc_patch_catalogue_fail
 jmp menusrc_patch_catalogue_done

.menusrc_patch_catalogue_verified
 ldx #0
.menusrc_catalogue_patch_read
 lda menusrc_catalogue_reads,x
 sta zp
 lda menusrc_catalogue_reads+1,x
 sta zp+1
 ldy #0
 lda #&20                    \ JSR &1FF0
 sta (zp),y
 iny
 lda #&F0
 sta (zp),y
 iny
 lda #&1F
 sta (zp),y
 inx
 inx
 cpx #6
 bne menusrc_catalogue_patch_read
 lda #&20                    \ JSR &1FE0
 sta &0ECC
 lda #&E0
 sta &0ECD
 lda #&1F
 sta &0ECE

 ldx #0
.menusrc_catalogue_copy_select
 lda menusrc_catalogue_select,x
 sta &1FE0,x
 inx
 cpx #(menusrc_catalogue_select_end-menusrc_catalogue_select)
 bne menusrc_catalogue_copy_select
 ldx #0
.menusrc_catalogue_copy_read
 lda menusrc_catalogue_read,x
 sta &1FF0,x
 inx
 cpx #(menusrc_catalogue_read_end-menusrc_catalogue_read)
 bne menusrc_catalogue_copy_read
.menusrc_patch_catalogue_done
 rts

.menusrc_catalogue_reads
 equw &1059,&1079,&10AB

\ Copied to &1FE0. Preserve the page in A while selecting JIM window 1.
.menusrc_catalogue_select
 pha
 lda #1
 sta &FCFE
 pla
 sta &FCFF
 rts
.menusrc_catalogue_select_end

\ Copied to &1FF0. Y remains the catalogue offset and A returns the byte.
.menusrc_catalogue_read
 lda #1
 sta &FCFE
 lda &FD00,y
 rts
.menusrc_catalogue_read_end
