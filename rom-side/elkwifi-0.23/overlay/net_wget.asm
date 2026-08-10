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
net_load_lo = heap+&F1
net_load_hi = heap+&F2
net_bytes_lo = heap+&F3
net_bytes_hi = heap+&F4
net_paged_page = heap+&E4
net_paged_offset = heap+&E5
net_primary_page = heap+&E6

\ Close the ElkWiFi-compatible raw socket and display the Pi response. The
\ inherited wget_close routine is also an internal silent cleanup path.
.disconnect_cmd
 lda #14
 jmp generic_cmd

.pi_wget_cmd
 lda #0
 sta net_transfer_ok
 sta net_received
 sta net_load_lo
 sta net_load_hi
 sta net_bytes_lo
 sta net_bytes_hi
 sta net_paged_page
 sta net_paged_offset
 sta net_primary_page
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
 lda load_addr
 sta net_load_lo
 lda load_addr+1
 sta net_load_hi

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
 bne pi_wget_have_bytes
 jmp pi_wget_empty
.pi_wget_have_bytes
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
 lda net_load_lo
 ora net_load_hi
 bne pi_wget_main_has_space
 lda net_bytes_lo
 ora net_bytes_hi
 beq pi_wget_main_has_space
 jsr pi_wget_close
 ldx #(error_buffer_full-error_table)
 jmp error
.pi_wget_main_has_space
 lda net_load_lo
 sta load_addr
 lda net_load_hi
 sta load_addr+1
 pla
 ldy #0
 sta (load_addr),y
 inc load_addr
 bne pi_wget_save_main_pointer
 inc load_addr+1
.pi_wget_save_main_pointer
 lda load_addr
 sta net_load_lo
 lda load_addr+1
 sta net_load_hi
.pi_wget_copied
 lda #&FF
 sta net_received
 inc net_bytes_lo
 bne pi_wget_counted
 inc net_bytes_hi
.pi_wget_counted
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
 bne pi_wget_has_response
 jmp pi_wget_empty_response
.pi_wget_has_response
 lda #&FF
 sta net_transfer_ok
 lda uflag
 ora sflag
 bne pi_wget_paged_finish
 jmp pi_wget_finish_close
.pi_wget_paged_finish
 lda #0
 sta pr_r
 sta pr_y
 lda net_bytes_lo
 sta sbufl
 lda net_bytes_hi
 sta sbufh
 jsr set_bank_1
 lda #&FF
 sta pagereg
 lda net_bytes_lo
 sta &FDFE
 lda net_bytes_hi
 sta &FDFF
 lda uflag
 beq pi_wget_normalized
 \ ElkWiFi -U means "store in paged RAM"; it does not promise that the
 \ payload is a UEF.  The published MENU downloads its raw TITLES catalogue
 \ with -U.  Only ask the Pi to expand inputs carrying a gzip or ZIP signature.
 \ This also keeps ordinary -U transfers compatible with kernels predating
 \ the optional normalisation service.
 lda #'R'
 sta net_result
 lda #0
 sta pagereg
 lda pageram
 cmp #&1F
 bne pi_wget_check_zip
 lda pageram+1
 cmp #&8B
 beq pi_wget_normalize_compressed
.pi_wget_check_zip
 lda pageram
 cmp #'P'
 bne pi_wget_raw_paged
 lda pageram+1
 cmp #'K'
 bne pi_wget_raw_paged
.pi_wget_normalize_compressed
 jsr service_driver_uef_normalize
 cmp #'I'
 bne pi_wget_not_invalid_uef
 jsr pi_wget_close
 jsr set_bank_0
 jmp uef_invalid
.pi_wget_not_invalid_uef
 cmp #'T'
 bne pi_wget_normalize_ok
 jsr pi_wget_close
 jsr set_bank_0
 jmp uef_too_large
.pi_wget_normalize_ok
 sta net_result
 \ Command 93 rewrites the authoritative trailer with the expanded length.
 lda &FDFE
 sta net_bytes_lo
 sta sbufl
 lda &FDFF
 sta net_bytes_hi
 sta sbufh
 jmp pi_wget_normalized
.pi_wget_raw_paged
 lda #&FF
 sta pagereg
.pi_wget_normalized
 jsr set_bank_0
 lda net_primary_page
 sta pagereg
 lda sflag
 beq pi_wget_finish_close
 jsr wget_copy_file_to_swr
.pi_wget_finish_close
 jsr pi_wget_close
 jsr printtext
 equs "WGET ",&EA
 lda uflag
 beq pi_wget_report_format_done
 lda net_result
 cmp #'G'
 bne pi_wget_report_zip
 jsr printtext
 equs "GZIP ",&EA
 jmp pi_wget_report_format_done
.pi_wget_report_zip
 cmp #'Z'
 bne pi_wget_report_raw
 jsr printtext
 equs "ZIP ",&EA
 jmp pi_wget_report_format_done
.pi_wget_report_raw
 jsr printtext
 equs "RAW ",&EA
.pi_wget_report_format_done
 jsr printtext
 equs "OK &",&EA
 lda net_bytes_hi
 jsr printhex
 lda net_bytes_lo
 jsr printhex
 jsr printtext
 equs " bytes",&EA
 lda tflag
 bne pi_wget_report_end
 lda uflag
 ora sflag
 bne pi_wget_report_jim
 jsr printtext
 equs " at &",&EA
 lda laddr+1
 jsr printhex
 lda laddr
 jsr printhex
 jsr printtext
 equs "-&",&EA
 lda net_load_hi
 jsr printhex
 lda net_load_lo
 jsr printhex
 lda net_bytes_hi
 bne pi_wget_report_head
 lda net_bytes_lo
 cmp #4
 bcc pi_wget_report_end
.pi_wget_report_head
 jsr printtext
 equs " head &",&EA
 lda #0
 sta net_count
.pi_wget_report_head_byte
 lda laddr
 sta load_addr
 lda laddr+1
 sta load_addr+1
 ldy net_count
 lda (load_addr),y
 jsr printhex
 inc net_count
 lda net_count
 cmp #4
 bne pi_wget_report_head_byte
 jmp pi_wget_report_end
.pi_wget_report_jim
 jsr printtext
 equs " in JIM",&EA
.pi_wget_report_end
 jsr osnewl
 jmp call_claimed

.pi_wget_empty_response
 jsr printtext
 equs "Empty response",&0D,&EA
 jmp pi_wget_close_claimed

.pi_wget_store_paged
 php
 sei                         \ FCFF and the JIM aperture are shared by AP5 users
 pha
 jsr set_bank_1
 lda net_paged_page
 sta pagereg
 ldy net_paged_offset
 pla
 sta pageram,y
 iny
 bne pi_wget_paged_pointer_ok
 inc net_paged_page
 beq pi_wget_paged_full
 lda net_paged_page
 sta pagereg
.pi_wget_paged_pointer_ok
 sty net_paged_offset
 jsr set_bank_0
 lda net_primary_page
 sta pagereg
 plp
 rts
.pi_wget_paged_full
 jsr set_bank_0
 lda net_primary_page
 sta pagereg
 plp
 jsr pi_wget_close
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
