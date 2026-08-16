\ Import a UEF file from the current MOS filing system into the same Pi1MHz
\ JIM window used by WGET -U, then start it through the stock WiCFS sequence.
\
\ Syntax: *UEF LOAD <filename>

OSFIND = &FFCE
OSBGET = &FFD7

.uef_cmd
 jsr wicfs_detect_machine
 jsr skipspace1
 ldx #0
.uef_load_option
 lda (line),y
 and #&DF
 cmp uef_load_word,x
 beq uef_option_character_ok
 jmp uef_usage
.uef_option_character_ok
 iny
 inx
 cpx #4
 bne uef_load_option
 lda (line),y
 cmp #&20
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
 pha                         \ file handle below the two-byte length frame

 \ The last two bytes of the 64 KiB UEF window are its authoritative length
 \ trailer, so the largest accepted image is &FFFE bytes. Keep the live
 \ length in a two-byte stack frame. No fixed RAM address is safe across all
 \ filing systems, and the frame remains private across balanced MOS calls.
 lda #0
 pha                         \ high byte at &0102,S
 pha                         \ low byte at &0101,S
 php
 sei
 lda #0
 ldy #0
 jsr uef_commit_length
 plp

.uef_read
 tsx
 ldy &0103,x                 \ recover handle after TSX length operations
 jsr OSBGET
 bcs uef_read_end
 sta temp

 \ Check the CPU-side length before entering the atomic JIM transaction.
 tsx
 lda &0102,x
 cmp #&FF
 bne uef_have_space
 lda &0101,x
 cmp #&FE
 bcc uef_have_space
 jmp uef_full
.uef_have_space
 \ The current filing system may use JIM during OSBGET. Reselect the complete
 \ 1MHzWifi address before writing the downloaded byte.
 php
 sei
 jsr wicfs_select_public_zero
 tsx
 lda &0103,x                \ high byte below saved flags
 sta pagereg
 jsr wicfs_bus_delay
 ldy &0102,x                \ low byte below saved flags
 lda temp
 sta pageram,y
 jsr wicfs_bus_delay
 inc &0102,x
 bne uef_byte_stored
 inc &0103,x
.uef_byte_stored
 plp
 tsx
 lda &0101,x
 bne uef_read
 php
 sei
 ldy &0102,x
 jsr uef_commit_length
 plp
 jsr check_esc
 bcc uef_read
 jsr uef_close
 pla
 pla
 pla
 jmp call_claimed

.uef_read_end
 cmp #&FE                    \ normal OSBGET end-of-file indication
 beq uef_complete
 sta temp
 jsr uef_close
 jsr printtext
 equs "UEF read error &",&EA
 lda temp
 jsr printhex
 jsr osnewl
 pla
 pla
 pla
 jmp call_claimed

.uef_complete
 jsr uef_close
 php
 sei
 tsx
 lda &0102,x                \ low byte below saved flags
 ldy &0103,x                \ high byte below saved flags
 jsr uef_commit_length
 jsr uef_select_length
 lda &FDFE
 sta temp
 lda &FDFF
 tsx
 sta &0103,x                \ high frame byte below saved flags
 lda temp
 sta &0102,x                \ low frame byte below saved flags
 plp
 tsx
 lda &0102,x                \ high frame byte after saved flags are removed
 ora &0101,x                \ low frame byte
 bne uef_nonempty
 jmp uef_empty
.uef_nonempty
 jsr service_driver_uef_normalize
 cmp #'I'
 bne uef_not_invalid
 jmp uef_invalid_cleanup
.uef_not_invalid
 cmp #'T'
 bne uef_normalized
 jmp uef_too_large_cleanup
.uef_normalized
 pha                         \ preserve normalize result above length frame
 php
 sei
 jsr uef_select_length
 lda &FDFE
 sta temp
 lda &FDFF
 tsx
 sta &0104,x
 lda temp
 sta &0103,x
 plp
 pla
 sta temp
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
 tsx
 lda &0102,x
 jsr printhex
 tsx
 lda &0101,x
 jsr printhex
 jsr printtext
 equs " bytes in JIM",&0D,&EA

 \ Both Tube-active and Tube-off paths must first make the same host-side
 \ filing-system transition. This runs through host OSCLI only; it neither
 \ addresses nor transfers data to the Tube.
 jsr menu_select_tape
 bcc uef_tape_selected
 pla
 pla
 pla
 jmp call_claimed
.uef_tape_selected
 pla
 pla
 pla

 \ A Tube language would otherwise consume the queued CHAIN. Enter the host
 \ language without disabling, resetting or transferring through the Tube.
 lda #&EA
 ldx #0
 ldy #&FF
 jsr osbyte
 cpx #&FF
 bne uef_queue_start
 jmp menu_host_cmd

 \ Match the stock *WICFS setup sequence. QUPRUN is an internal second-stage
 \ command: it installs WiCFS and then queues the shorter REWIND/CHAIN pair.
 \ Splitting the sequence is required because the Electron keyboard buffer
 \ cannot hold the setup and launch commands at the same time.
.uef_queue_start
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
 jsr uef_close
 pla
 pla
 pla
 ldx #(error_buffer_full-error_table)
 jmp error

.uef_empty
 pla
 pla
 pla
 jsr printtext
 equs "Empty UEF file",&0D,&EA
 jmp call_claimed

.uef_invalid_cleanup
 pla
 pla
 pla
.uef_invalid
 jsr printtext
 equs "Invalid UEF, gzip or ZIP file",&0D,&EA
 jmp call_claimed

.uef_too_large_cleanup
 pla
 pla
 pla
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
 tsx
 \ JSR uef_close has placed its two-byte return address above the live
 \ low/high length frame. The OSFIND handle is therefore five bytes above
 \ the current stack pointer here, rather than the inline read-loop offset.
 ldy &0105,x
 lda #0
 jsr OSFIND
 rts

.uef_select_length
 jsr wicfs_select_public_zero
 lda #&FF
 sta pagereg
 jsr wicfs_bus_delay
 rts

.uef_commit_length
 pha                         \ uef_select_length uses A for page &FF
 jsr uef_select_length
 pla
 sta &FDFE
 jsr wicfs_bus_delay
 tya
 sta &FDFF
 jsr wicfs_bus_delay
 rts

.uef_load_word
 equs "LOAD"

.uef_launch
 equs "PAGE=&0E00",&0D
 equs "NEW",&0D
 equs "*QUPRUN",&0D
 equb &FF

.uef_run_launch
 equs "*REWIND",&0D
 equs "CHAIN "
 equb &22,&22,&0D
 equb &FF
