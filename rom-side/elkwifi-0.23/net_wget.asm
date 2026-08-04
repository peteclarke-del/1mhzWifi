\ Pi1MHz-native WGET transport.
\
\ The original ElkWiFi command talks to its 16C2552 at &FC30.  That address
\ is not forwarded by the AP5 and is unsafe from a Tube parasite.  This
\ implementation uses Pi1MHz's URL service through the FCA6 mailbox and
\ accesses the AP5-forwarded FRED services window from the I/O processor.

net_svc_addr_lo = &A6
net_svc_addr_mid = &A7
net_svc_addr_hi = &A8
net_svc_data = &A9
net_svc_command = &AA

net_cmd_url_open = 60
net_cmd_url_read = 61
net_cmd_url_close = 63
net_result_pending = 1
net_result_eof = &20

net_count = heap+&E8
net_cli_y = heap+&E9
net_wait_lo = heap+&EA
net_wait_hi = heap+&EB
net_empty_lo = heap+&EC
net_empty_hi = heap+&ED
net_result = heap+&EE
net_transfer_ok = heap+&EF
net_received = heap+&F0

.pi_wget_cmd
 lda #0
 sta net_transfer_ok
 sta net_received
 sta tflag
 sta sflag
 sta aflag
 sta pflag
 sta uflag
 sta proto
 sta load_addr
 sta load_addr+1
 sta laddr
 sta laddr+1
 lda #&0D
 sta newln

.pi_wget_param
 jsr skipspace1
 jsr read_cli_param
 cpx #0
 bne pi_wget_have_param
 jsr printtext
 equs "Usage: WGET [-TXUS] <url> [address]",&0D,&EA
 jmp call_claimed

.pi_wget_have_param
 lda strbuf
 cmp #'-'
 bne pi_wget_url
 lda strbuf+1
 ora #&20
 cmp #'t'
 beq pi_wget_text
 cmp #'x'
 beq pi_wget_unix_text
 cmp #'u'
 beq pi_wget_uef
 cmp #'s'
 beq pi_wget_sideways
 \ Container formats still use the original decoder, which requires the
 \ cartridge UART.  Fail explicitly instead of touching &FC30 on AP5/Tube.
 ldx #(error_not_implemented-error_table)
 jmp error

.pi_wget_uef
 lda #1
 sta uflag
 bne pi_wget_param

.pi_wget_sideways
 lda #1
 sta sflag
 bne pi_wget_param

.pi_wget_unix_text
 lda #&0A
 sta newln
.pi_wget_text
 lda #1
 sta tflag
 bne pi_wget_param

.pi_wget_url
 \ Preserve the MOS command-line index while building the service request.
 sty net_cli_y
 jsr net_command_address
 lda #net_cmd_url_open
 jsr net_write_a
 lda #4                    \ NET_OPEN_READ
 jsr net_write_a
 ldx #0
.pi_wget_url_copy
 stx net_count
 lda strbuf,x
 cmp #&0D
 bne pi_wget_url_char
 lda #0
.pi_wget_url_char
 jsr net_write_a
 cmp #0
 beq pi_wget_url_done
 ldx net_count
 inx
 bne pi_wget_url_copy
 ldx #(error_bad_param-error_table)
 jmp error

.pi_wget_url_done
 \ Optional load address.  Text mode deliberately ignores it, matching the
 \ ElkWiFi command; binary mode requires it when no container header exists.
 ldy net_cli_y
 jsr skipspace1
 jsr read_cli_param
 ldx #load_addr
 jsr string2hex
 sta net_result
 lda load_addr
 sta laddr
 lda load_addr+1
 sta laddr+1
 lda tflag
 bne pi_wget_address_ok
 lda uflag
 bne pi_wget_address_ok
 lda sflag
 bne pi_wget_address_ok
 lda net_result
 bne pi_wget_address_ready
 jsr wget_set_default_load
 lda laddr
 sta load_addr
 lda laddr+1
 sta load_addr+1
.pi_wget_address_ok
.pi_wget_address_ready

 jsr net_dispatch_wait
 cmp #0
 beq pi_wget_opened
 jsr pi_wget_network_error

.pi_wget_opened
 lda #0
 sta net_empty_lo
 sta pr_r
 sta pr_y
 sta sbufl
 sta sbufh
 lda #10
 sta net_empty_hi

.pi_wget_read
 jsr net_command_address
 lda #net_cmd_url_read
 jsr net_write_a
 lda #240                  \ maximum bytes in the scratch page
 jsr net_write_a
 lda #0
 jsr net_write_a
 jsr net_write_a
 lda #0                    \ JIM offset &00FFF100, little endian
 jsr net_write_a
 lda #&F1
 jsr net_write_a
 lda #&FF
 jsr net_write_a
 lda #0
 jsr net_write_a
 jsr net_dispatch_wait
 cmp #net_result_eof
 bne pi_wget_not_eof
 jmp pi_wget_done
.pi_wget_not_eof
 cmp #0
 beq pi_wget_read_length
 jsr pi_wget_network_error

.pi_wget_read_length
 jsr net_command_address
 lda #1
 jsr net_address_low
 jsr net_read_a
 sta net_count
 beq pi_wget_empty
 lda #0
 sta net_empty_lo
 lda #10
 sta net_empty_hi
 jsr net_scratch_address

.pi_wget_copy
 jsr net_read_a
 ldx tflag
 beq pi_wget_store
 cmp newln
 bne pi_wget_print
 lda #&0D
.pi_wget_print
 jsr osasci
 jmp pi_wget_copied
.pi_wget_store
 pha
 lda uflag
 ora sflag
 beq pi_wget_store_main
 pla
 jsr pi_wget_store_paged
 jmp pi_wget_copied
.pi_wget_store_main
 pla
 ldy #0
 sta (load_addr),y
 inc load_addr
 bne pi_wget_copied
 inc load_addr+1
.pi_wget_copied
 lda #&FF
 sta net_received
 dec net_count
 bne pi_wget_copy
 jsr check_esc
 bcs pi_wget_copy_cancel
 jmp pi_wget_read
.pi_wget_copy_cancel
 jsr pi_wget_close
 jmp call_claimed

.pi_wget_empty
 \ An open HTTP stream may legitimately have no bytes yet.  Allow roughly
 \ 50 seconds without progress, while still honouring Escape.
 jsr check_esc
 bcc pi_wget_empty_wait
 jmp pi_wget_copy_cancel
.pi_wget_empty_wait
 lda #19
 jsr osbyte
 dec net_empty_lo
 beq pi_wget_empty_high
 jmp pi_wget_read
.pi_wget_empty_high
 dec net_empty_hi
 beq pi_wget_empty_timeout
 jmp pi_wget_read
.pi_wget_empty_timeout
 jsr pi_wget_timeout

.pi_wget_done
 lda net_received
 beq pi_wget_empty_response
 lda #&FF
 sta net_transfer_ok
 lda uflag
 ora sflag
 beq pi_wget_finish_close
 jsr wget_context_switch_in
 lda #&FF
 sta pagereg
 lda sbufl
 sta &FDFE
 lda sbufh
 sta &FDFF
 jsr wget_context_switch_out
 lda sflag
 beq pi_wget_finish_close
 jsr wget_copy_file_to_swr
.pi_wget_finish_close
 jsr pi_wget_close
 jsr printtext
 equs "WGET OK",&0D,&EA
 jmp call_claimed

.pi_wget_empty_response
 jsr printtext
 equs "Empty response",&0D,&EA
 jmp pi_wget_close_claimed

.pi_wget_store_paged
 pha
 jsr wget_context_switch_in
 pla
 sta pageram,y
 iny
 bne pi_wget_paged_pointer_ok
 inc pagereg
 beq pi_wget_paged_full
.pi_wget_paged_pointer_ok
 jsr wget_context_switch_out
 inc sbufl
 bne pi_wget_paged_stored
 inc sbufh
.pi_wget_paged_stored
 rts
.pi_wget_paged_full
 jsr wget_context_switch_out
 ldx #(error_buffer_full-error_table)
 jmp error

.pi_wget_close
 jsr net_command_address
 lda #net_cmd_url_close
 jsr net_write_a
 jsr net_dispatch_wait
 rts

\ Select logical JIM &FFF000: Pi1MHz maps it into the reserved service RAM.
.net_command_address
 lda #0
 jsr net_address_low
 lda #&F0
 jsr net_address_mid
 lda #&FF
 jmp net_address_high

.net_scratch_address
 lda #0
 jsr net_address_low
 lda #&F1
 jsr net_address_mid
 lda #&FF
 jmp net_address_high

.net_address_low
 sta &FC00+net_svc_addr_lo
 rts
.net_address_mid
 sta &FC00+net_svc_addr_mid
 rts
.net_address_high
 sta &FC00+net_svc_addr_hi
 rts

.net_write_a
 sta &FC00+net_svc_data
 rts

.net_read_a
 lda &FC00+net_svc_data
 rts

\ Dispatch handle zero (&F0).  Bit 7 means the Pi main loop has not serviced
\ the FIQ latch; result 1 means an async DNS/connect is still pending and must
\ be re-issued.  Both paths are bounded and Escape-aware.
.net_dispatch_wait
 lda #0
 sta net_wait_lo
 lda #&FF                 \ about five seconds at one yield per video frame
 sta net_wait_hi
.net_dispatch_again
 lda #&F0
 sta &FC00+net_svc_command
.net_dispatch_busy
 lda &FC00+net_svc_command
 bpl net_dispatch_ready
 dec net_wait_lo
 bne net_dispatch_busy
 lda #19                  \ yield to the Pi main-loop network poll
 jsr osbyte
 dec net_wait_hi
 bne net_dispatch_busy
 jmp net_dispatch_timeout
.net_dispatch_ready
 cmp #net_result_pending
 bne net_dispatch_return
 jsr check_esc
 bcs net_dispatch_cancel
 lda #19
 jsr osbyte
 dec net_wait_lo
 bne net_dispatch_again
 dec net_wait_hi
 bne net_dispatch_again
 jmp net_dispatch_timeout
.net_dispatch_cancel
 lda #&2A                  \ cancelled: never masquerade as successful EOF
.net_dispatch_return
 rts
.net_dispatch_timeout
 lda #&29                  \ private transport-timeout result
 rts

.pi_wget_timeout
 jsr printtext
 equs "Network timeout",&0D,&EA
 jmp pi_wget_close_claimed

.pi_wget_network_error
 sta net_result
 jsr printtext
 equs "Network error &",&EA
 lda net_result
 jsr printhex
 jsr osnewl
.pi_wget_close_claimed
 jsr pi_wget_close
 jmp call_claimed
