\ Import a UEF file from the current MOS filing system into the same Pi1MHz
\ JIM window used by WGET -U, then start it through the stock WiCFS sequence.
\
\ Syntax: *UEF LOAD <filename>

OSFIND = &FFCE
OSBGET = &FFD7

.uef_cmd
 jsr skipspace1
 jsr read_cli_param
 cpx #4
 beq uef_option_length_ok
 jmp uef_usage
.uef_option_length_ok
 ldx #0
.uef_load_option
 lda strbuf,x
 and #&DF
 cmp uef_load_word,x
 beq uef_option_character_ok
 jmp uef_usage
.uef_option_character_ok
 inx
 cpx #4
 bne uef_load_option
 lda strbuf,x
 cmp #&0D
 beq uef_option_ok
 jmp uef_usage
.uef_option_ok

 jsr skipspace1
 cmp #&0D
 bne uef_filename_ok
 jmp uef_usage
.uef_filename_ok

 \ OSFIND takes a pointer to the CR-terminated filename. Point it at the
 \ unmodified remainder of the MOS command line so filing-system path syntax
 \ is preserved.
 tya
 clc
 adc line
 tax
 lda line+1
 adc #0
 tay
 lda #&40
 jsr OSFIND
 cmp #0
 bne uef_opened
 jmp uef_open_failed
.uef_opened
 tax                         \ X is preserved by OSBGET and holds the handle

 \ The last two bytes of the 64 KiB UEF window are its authoritative length
 \ trailer, so the largest accepted image is &FFFE bytes.
 jsr uef_select_length
 lda #0
 sta &FDFE
 sta &FDFF

.uef_read
 txa
 tay
 jsr OSBGET
 bcs uef_read_end
 pha

 \ The current filing system may use JIM during OSBGET. Reselect the complete
 \ 1MHzWifi address after every byte before reading or writing our state.
 jsr uef_select_length
 lda &FDFE
 sta zp
 lda &FDFF
 cmp #&FF
 bne uef_have_space
 lda zp
 cmp #&FE
 bcc uef_have_space
 jmp uef_full
.uef_have_space
 lda &FDFF
 sta pagereg
 ldy zp
 pla
 sta pageram,y

 jsr uef_select_length
 inc &FDFE
 bne uef_read
 inc &FDFF
 jsr check_esc
 bcc uef_read
 jsr uef_close
 jmp call_claimed

.uef_read_end
 cmp #&FE                    \ normal OSBGET end-of-file indication
 beq uef_complete
 pha
 jsr uef_close
 jsr printtext
 equs "UEF read error &",&EA
 pla
 jsr printhex
 jsr osnewl
 jmp call_claimed

.uef_complete
 jsr uef_close
 jsr uef_select_length
 lda &FDFE
 ora &FDFF
 bne uef_nonempty
 jmp uef_empty
.uef_nonempty
 jsr service_driver_uef_normalize
 cmp #'I'
 bne uef_not_invalid
 jmp uef_invalid
.uef_not_invalid
 cmp #'T'
 bne uef_normalized
 jmp uef_too_large
.uef_normalized
 sta temp
 jsr uef_select_length
 jsr printtext
 equs "UEF ",&EA
 lda temp
 cmp #'G'
 bne uef_format_zip
 jsr printtext
 equs "GZIP ",&EA
 jmp uef_format_done
.uef_format_zip
 cmp #'Z'
 bne uef_format_raw
 jsr printtext
 equs "ZIP ",&EA
 jmp uef_format_done
.uef_format_raw
 jsr printtext
 equs "RAW ",&EA
.uef_format_done
 jsr printtext
 equs "OK &",&EA
 lda &FDFF
 jsr printhex
 lda &FDFE
 jsr printhex
 jsr printtext
 equs " bytes in JIM 1",&0D,&EA

 \ Match the stock *WICFS setup sequence. QUPRUN is an internal second-stage
 \ command: it installs WiCFS and then queues the shorter REWIND/CHAIN pair.
 \ Splitting the sequence is required because the Electron keyboard buffer
 \ cannot hold the setup and launch commands at the same time.
 ldx #0
.uef_queue
 stx temp
 lda #&99
 ldy uef_launch,x
 bmi uef_started
 ldx #0
 jsr osbyte
 ldx temp
 inx
 bne uef_queue
.uef_started
 jmp call_claimed

\ Hidden second-stage command used only by *UEF. The public *WICFS command
\ continues to use QUPCFS and retains its original behaviour.
.uef_run_cmd
 jsr wicfs_install
 ldx #0
.uef_run_queue
 stx temp
 lda #&99
 ldy uef_run_launch,x
 bmi uef_run_started
 ldx #0
 jsr osbyte
 ldx temp
 inx
 bne uef_run_queue
.uef_run_started
 jmp call_claimed

.uef_full
 pla
 jsr uef_close
 ldx #(error_buffer_full-error_table)
 jmp error

.uef_empty
 jsr printtext
 equs "Empty UEF file",&0D,&EA
 jmp call_claimed

.uef_invalid
 jsr printtext
 equs "Invalid UEF, gzip or ZIP file",&0D,&EA
 jmp call_claimed

.uef_too_large
 jsr printtext
 equs "Expanded UEF exceeds &FFFE bytes",&0D,&EA
 jmp call_claimed

.uef_open_failed
 jsr printtext
 equs "UEF file not found",&0D,&EA
 jmp call_claimed

.uef_usage
 jsr printtext
 equs "Usage: *UEF LOAD <filename>",&0D,&EA
 jmp call_claimed

.uef_close
 txa
 tay
 lda #0
 jsr OSFIND
 rts

.uef_select_length
 lda #0
 sta &FCFD
 lda #1
 sta &FCFE
 lda #&FF
 sta pagereg
 rts

.uef_load_word
 equs "LOAD"

.uef_launch
 equs "*TAPE",&0D
 equs "PAGE=&0E00",&0D
 equs "NEW",&0D
 equs "*QUPRUN",&0D
 equb &FF

.uef_run_launch
 equs "*REWIND",&0D
 equs "CHAIN "
 equb &22,&22,&0D
 equb &FF
