\ ElkWiFi driver calls implemented through the Pi1MHz services mailbox.
\ This service ROM executes in the host I/O processor, including when invoked
\ by a Tube parasite, so use the 1MHz-bus FRED window directly.

drv_svc_addr_lo = &A6
drv_svc_addr_mid = &A7
drv_svc_addr_hi = &A8
drv_svc_data = &A9
drv_svc_command = &AA

drv_svc_status = 80
drv_svc_scan = 81
drv_svc_join = 82
drv_svc_ifcfg = 83
drv_svc_lapopt = 87
drv_svc_ping = 88
drv_svc_datetime = 89
drv_svc_cancel = 90
drv_svc_online = 92
drv_svc_uef_normalize = 93

drv_svc_timeout_lo = errorspace+3
drv_svc_timeout_hi = errorspace+4
drv_svc_saved_x = errorspace+5
drv_svc_strings = errorspace+6
drv_net_index = errorspace+7
drv_net_port_lo = errorspace+8
drv_net_port_hi = errorspace+9
drv_net_chunk = errorspace+10
drv_net_seen = errorspace+11
drv_net_copy_count = errorspace+12
drv_net_buf_x = errorspace+13
drv_svc_response_count = errorspace+14
drv_svc_timeout_outer = errorspace+15
drv_svc_command_copy = errorspace+16
drv_svc_cancelled = errorspace+17

drv_net_open = 45
drv_net_dns = 46
drv_net_connect = 47
drv_net_send = 50
drv_net_recv = 51
drv_net_close = 53

.service_driver_init
\Functions 0 and 1 reset the original ESP module. Pi1MHz has no separate
\cartridge processor to reset, so close volatile TCP state and return a
\normal driver response without disturbing the saved WiFi association.
.service_driver_reset
 jsr service_driver_net_close_silent
 ldx #<service_driver_ok_text
 ldy #>service_driver_ok_text
 jmp service_driver_rom_response

.service_driver_version
 lda #drv_svc_status
 jmp service_driver_begin

.service_driver_scan
 lda #drv_svc_scan
 jmp service_driver_begin

.service_driver_ifcfg
 lda #drv_svc_ifcfg
 jmp service_driver_begin

.service_driver_online
 lda #drv_svc_online
 jmp service_driver_begin

\Normalize the UEF window in place. Return only the first response character
\in A: copying the response into pageram would overwrite the UEF header.
.service_driver_uef_normalize
 lda #drv_svc_uef_normalize
 jsr service_driver_write_command
 jsr service_driver_dispatch
 rts

.service_driver_lapopt
 lda #drv_svc_lapopt
 jsr service_driver_write_command
 lda heap
 cmp #'7'
 bne service_driver_lapopt_127
 lda heap+1
 cmp #&0D
 bne service_driver_lapopt_bad
 ldy #7
 bne service_driver_lapopt_send
.service_driver_lapopt_127
 lda heap
 cmp #'1'
 bne service_driver_lapopt_bad
 lda heap+1
 cmp #'2'
 bne service_driver_lapopt_bad
 lda heap+2
 cmp #'7'
 bne service_driver_lapopt_bad
 lda heap+3
 cmp #&0D
 bne service_driver_lapopt_bad
 ldy #127
.service_driver_lapopt_send
 jsr service_driver_write_y
 jmp service_driver_dispatch
.service_driver_lapopt_bad
 jmp service_driver_error_parameter

.service_driver_mode
 ldy #0
 lda (paramblok),y
 beq service_driver_mode_ok
 cmp #'1'
 beq service_driver_mode_ok
 jmp service_driver_net_error
.service_driver_mode_ok
 ldx #<service_driver_mode_text
 ldy #>service_driver_mode_text
 jmp service_driver_rom_response

\ Function 9 selects connection multiplexing. Pi1MHz exposes exactly one raw
\ TCP connection, so the original single-connection request is a successful
\ no-op. Reject multiplexed mode rather than silently promising five sockets.
.service_driver_cpmux
 ldy #0
 lda (paramblok),y
 cmp #'0'
 bne service_driver_cpmux_bad
 iny
 lda (paramblok),y
 cmp #&0D
 bne service_driver_cpmux_bad
 ldx #<service_driver_ok_text
 ldy #>service_driver_ok_text
 jmp service_driver_rom_response
.service_driver_cpmux_bad
 jmp service_driver_error_parameter

.service_driver_unsupported
 ldx #(error_not_implemented-error_table)
 jmp error

.service_driver_mux_channel
 ldy #&FF                  \ single-connection mode
 clc
 rts

.service_driver_wifi_control
 ldx save_x
 \ `*WIFI ON` is the quickest positive Pi-link diagnostic.  Do not return a
 \ ROM-local OK: require command 80 to make a complete FCA6/FCA9 round trip.
 beq service_driver_wifi_off
 jmp service_driver_version
.service_driver_wifi_off
 lda #drv_svc_join
 jsr service_driver_write_command
 ldy #3
 jsr service_driver_write_y
 jmp service_driver_dispatch

.service_driver_ping
 lda #0
 sta drv_svc_cancelled
 lda #drv_svc_ping
 jsr service_driver_write_command
 ldx #0
.service_driver_ping_copy
 txa
 tay
 lda (paramblok),y
 cmp #&0D
 bne service_driver_ping_char
 lda #0
.service_driver_ping_char
 stx drv_svc_saved_x
 tay
 jsr service_driver_write_y
 ldx drv_svc_saved_x
 cmp #0
 bne service_driver_ping_more
 jmp service_driver_dispatch
.service_driver_ping_more
 inx
 bne service_driver_ping_copy
 jmp service_driver_error_parameter

.service_driver_date
 ldy #0
 beq service_driver_datetime
.service_driver_time
 ldy #1
.service_driver_datetime
 lda #drv_svc_datetime
 jsr service_driver_write_command
 jsr service_driver_write_y
 jmp service_driver_dispatch

\ Raw TCP compatibility used by OSWORD &65 and the stock DATE/TIME tools.
.service_driver_cipstart
 jsr service_driver_net_close_silent
 jsr net_command_address
 lda #drv_net_open
 jsr net_write_a
 lda #0                    \ TCP
 jsr net_write_a
 jsr net_dispatch_wait
 cmp #0
 beq service_driver_open_ok
 jmp service_driver_net_error
.service_driver_open_ok

 \ X/Y pointed at CR-separated protocol, hostname, port strings on entry.
 \ Never silently downgrade SSL/UDP to plaintext TCP.
 ldy #0
 lda (paramblok),y
 and #&DF
 cmp #'T'
 beq service_driver_protocol_t
 jmp service_driver_net_error
.service_driver_protocol_t
 iny
 lda (paramblok),y
 and #&DF
 cmp #'C'
 beq service_driver_protocol_tc
 jmp service_driver_net_error
.service_driver_protocol_tc
 iny
 lda (paramblok),y
 and #&DF
 cmp #'P'
 beq service_driver_protocol_ok
 jmp service_driver_net_error
.service_driver_protocol_ok
 ldy #0
.service_driver_skip_protocol
 lda (paramblok),y
 iny
 cmp #&0D
 bne service_driver_skip_protocol
 sty drv_net_index
 jsr net_command_address
 lda #drv_net_dns
 jsr net_write_a
.service_driver_copy_host
 ldy drv_net_index
 lda (paramblok),y
 iny
 sty drv_net_index
 cmp #&0D
 bne service_driver_host_char
 lda #0
.service_driver_host_char
 jsr net_write_a
 cmp #0
 bne service_driver_copy_host
 jsr net_dispatch_wait
 cmp #0
 beq service_driver_dns_ok
 jmp service_driver_net_error
.service_driver_dns_ok

 \ Save resolved address before reusing the command block.
 jsr net_command_address
 lda #4
 jsr net_address_low
 lda #0
 sta drv_net_copy_count
.service_driver_copy_ip
 jsr net_read_a
 ldx drv_net_copy_count
 sta heap+&E0,x
 inc drv_net_copy_count
 lda drv_net_copy_count
 cmp #4
 bne service_driver_copy_ip

 \ Decimal TCP port follows the hostname.
 lda #0
 sta drv_net_port_lo
 sta drv_net_port_hi
.service_driver_port_digit
 ldy drv_net_index
 lda (paramblok),y
 cmp #&0D
 beq service_driver_connect
 sec
 sbc #'0'
 cmp #10
 bcc service_driver_port_valid
 jmp service_driver_net_error
.service_driver_port_valid
 pha
 lda drv_net_port_lo       \ port = port*10 + digit
 sta zp
 lda drv_net_port_hi
 sta zp+1
 asl drv_net_port_lo
 rol drv_net_port_hi
 asl drv_net_port_lo
 rol drv_net_port_hi
 lda drv_net_port_lo
 clc
 adc zp
 sta drv_net_port_lo
 lda drv_net_port_hi
 adc zp+1
 sta drv_net_port_hi
 asl drv_net_port_lo
 rol drv_net_port_hi
 pla
 clc
 adc drv_net_port_lo
 sta drv_net_port_lo
 bcc service_driver_port_next
 inc drv_net_port_hi
.service_driver_port_next
 inc drv_net_index
 bne service_driver_port_digit

.service_driver_connect
 jsr net_command_address
 lda #drv_net_connect
 jsr net_write_a
 lda #0
 sta drv_net_index
.service_driver_write_ip
 ldx drv_net_index
 lda heap+&E0,x
 jsr net_write_a
 inc drv_net_index
 lda drv_net_index
 cmp #4
 bne service_driver_write_ip
 lda drv_net_port_lo
 jsr net_write_a
 lda drv_net_port_hi
 jsr net_write_a
 jsr net_dispatch_wait
 cmp #0
 beq service_driver_connect_ok
 jmp service_driver_net_error
.service_driver_connect_ok
 ldx #<service_driver_connect_text
 ldy #>service_driver_connect_text
 jmp service_driver_rom_response

.service_driver_cipsend
 ldx save_x
 lda &0000,x
 sta data_pointer
 lda &0001,x
 sta data_pointer+1
 lda &0002,x
 sta data_counter
 lda &0003,x
 sta data_counter+1
 lda &0004,x
 sta data_counter+2
.service_driver_send_more
 lda data_counter
 ora data_counter+1
 ora data_counter+2
 beq service_driver_receive
 lda #240
 sta drv_net_chunk
 lda data_counter+1
 ora data_counter+2
 bne service_driver_copy_send
 lda data_counter
 cmp #240
 bcs service_driver_copy_send
 sta drv_net_chunk
.service_driver_copy_send
 jsr net_scratch_address
 lda drv_net_chunk
 sta drv_net_copy_count
.service_driver_copy_send_byte
 ldy #0
 lda (data_pointer),y
 jsr net_write_a
 inc data_pointer
 bne service_driver_send_pointer_ok
 inc data_pointer+1
.service_driver_send_pointer_ok
 jsr dec_data_counter
 dec drv_net_copy_count
 bne service_driver_copy_send_byte

 jsr net_command_address
 lda #drv_net_send
 jsr net_write_a
 lda drv_net_chunk
 jsr net_write_a
 lda #0
 jsr net_write_a
 jsr net_write_a
 lda #0                    \ source offset &00FFF100
 jsr net_write_a
 lda #&F1
 jsr net_write_a
 lda #&FF
 jsr net_write_a
 lda #0
 jsr net_write_a
 jsr net_dispatch_wait
 cmp #0
 beq service_driver_send_ok
 jmp service_driver_net_error
.service_driver_send_ok
 jmp service_driver_send_more

.service_driver_ipd
.service_driver_receive
 ldx #0
 stx driver_page_shadow
 stx pagereg
 stx drv_net_seen
 stx drv_net_buf_x
 stx net_empty_lo
 lda #10
 sta net_empty_hi
.service_driver_receive_more
 jsr net_command_address
 lda #drv_net_recv
 jsr net_write_a
 lda #240
 jsr net_write_a
 lda #0
 jsr net_write_a
 jsr net_write_a
 lda #0
 jsr net_write_a
 lda #&F1
 jsr net_write_a
 lda #&FF
 jsr net_write_a
 lda #0
 jsr net_write_a
 jsr net_dispatch_wait
 cmp #&20
 beq service_driver_receive_done
 cmp #0
 beq service_driver_receive_ok
 jmp service_driver_net_error
.service_driver_receive_ok
 jsr net_command_address
 lda #1
 jsr net_address_low
 jsr net_read_a
 sta drv_net_chunk
 beq service_driver_receive_empty
 lda #1
 sta drv_net_seen
 jsr net_scratch_address
.service_driver_receive_copy
 jsr net_read_a
 ldx drv_net_buf_x
 sta pageram,x
 inx
 stx drv_net_buf_x
 bne service_driver_receive_copy_next
 inc driver_page_shadow
 lda driver_page_shadow
 sta pagereg
 bne service_driver_receive_copy_next
 jmp service_driver_net_error
.service_driver_receive_copy_next
 dec drv_net_chunk
 bne service_driver_receive_copy
 jmp service_driver_receive_more
.service_driver_receive_empty
 lda drv_net_seen
 bne service_driver_receive_done
 lda #19
 jsr osbyte
 dec net_empty_lo
 beq service_driver_receive_empty_high
 jmp service_driver_receive_more
.service_driver_receive_empty_high
 dec net_empty_hi
 beq service_driver_receive_done
 jmp service_driver_receive_more
.service_driver_receive_done
 ldx drv_net_buf_x
 lda #0
 sta pageram,x
 jmp restore_env

.service_driver_cipclose
 jsr service_driver_net_close_silent
 ldx #<service_driver_close_text
 ldy #>service_driver_close_text
 jmp service_driver_rom_response

.service_driver_net_close_silent
 jsr net_command_address
 lda #drv_net_close
 jsr net_write_a
 jsr net_dispatch_wait
 rts

.service_driver_net_error
 pha
 jsr service_driver_net_close_silent
 pla
 ldx #0
 stx driver_page_shadow
 stx pagereg
 lda #'E'
 sta pageram,x
 inx
 lda #'R'
 sta pageram,x
 inx
 sta pageram,x
 inx
 lda #&0D
 sta pageram,x
 inx
 lda #0
 sta pageram,x
 jmp restore_env

\ X/Y point at a NUL-terminated ROM string.
.service_driver_rom_response
 stx zp
 sty zp+1
 ldx #0
 stx driver_page_shadow
 stx pagereg
 ldy #0
.service_driver_rom_response_copy
 lda (zp),y
 sta pageram,x
 inx
 iny
 cmp #0
 bne service_driver_rom_response_copy
 dex
 jmp restore_env

.service_driver_connect_text
 equs "CONNECT",&0D,&0A,&0D,&0A,"OK",&0D,&0A,&0D,&0A,0
.service_driver_close_text
 equs "CLOSED",&0D,&0A,&0D,&0A,"OK",&0D,&0A,&0D,&0A,0
.service_driver_mode_text
 equs "+CWMODE:1",&0D,&0A,&0D,&0A,"OK",&0D,&0A,0
.service_driver_ok_text
 equs "OK",&0D,&0A,0

.service_driver_join
 lda #drv_svc_join
 jsr service_driver_write_command
 ldy #0
 lda (paramblok),y
 beq service_driver_join_query
 ldy #1
 jsr service_driver_write_y
 lda #2
 sta drv_svc_strings
 ldx #0
.service_driver_join_copy
 txa
 tay
 lda (paramblok),y
 cmp #&0D
 bne service_driver_join_char
 lda #0
 dec drv_svc_strings
.service_driver_join_char
 stx drv_svc_saved_x
 tay
 jsr service_driver_write_y
 ldx drv_svc_saved_x
 lda drv_svc_strings
 beq service_driver_dispatch
 inx
 bne service_driver_join_copy
 jmp service_driver_error
.service_driver_join_query
 ldy #0
 jsr service_driver_write_y
 jmp service_driver_dispatch

.service_driver_leave
 lda #drv_svc_join
 jsr service_driver_write_command
 ldy #2
 jsr service_driver_write_y
 jmp service_driver_dispatch

.service_driver_begin
 jsr service_driver_write_command
 jmp service_driver_dispatch

\ A contains the service command. Set command-page address and write byte 0.
.service_driver_write_command
 pha
 lda #0
 sta &FC00+drv_svc_addr_lo
 lda #&FF
 sta &FC00+drv_svc_addr_mid
 sta &FC00+drv_svc_addr_hi
 \ The services emulator makes all three address bytes readable.  Check them
 \ before touching the command block so an absent/unforwarded FCA6-FCA9 port
 \ is reported as a missing device, rather than timing out ambiguously.
 lda &FC00+drv_svc_addr_lo
 bne service_driver_port_missing_near
 lda &FC00+drv_svc_addr_mid
 cmp #&FF
 bne service_driver_port_missing_near
 lda &FC00+drv_svc_addr_hi
 cmp #&FF
 bne service_driver_port_missing_near
 pla
 sta drv_svc_command_copy
 sta &FC00+drv_svc_data
 \ Rewind byte zero and read it back.  The read auto-increments to byte one,
 \ which is exactly where callers expect to append their request arguments.
 pha
 lda #0
 sta &FC00+drv_svc_addr_lo
 pla
 cmp &FC00+drv_svc_data
 bne service_driver_port_missing_near
 rts
.service_driver_port_missing_near
 jmp service_driver_port_missing
.service_driver_write_y
 tya
 sta &FC00+drv_svc_data
 rts

.service_driver_dispatch
 lda #&FF
 sta &FC00+drv_svc_command
 lda #0
 sta drv_svc_timeout_lo
 lda #1
 sta drv_svc_timeout_outer
 \ Initial radio/firmware bring-up and a real `*LAP` scan are asynchronous.
 \ Give commands 80/81 a long window; an absent or unclaimed service is still
 \ detected immediately by the read-back and &FF checks above.
 lda drv_svc_command_copy
 cmp #drv_svc_status
 bne service_driver_timeout_not_status
 \ Function 2 is *VERSION/GMR and must never inherit the many-minute radio
 \ startup window required by function 24 (*WIFI ON). Both use command 80,
 \ but save_a retains the public driver function number for this call.
 lda save_a
 cmp #2
 beq service_driver_short_timeout
 jmp service_driver_long_timeout
.service_driver_timeout_not_status
 cmp #drv_svc_scan
 beq service_driver_long_timeout
 cmp #drv_svc_join
 beq service_driver_long_timeout
 cmp #drv_svc_ping
 beq service_driver_long_timeout
 cmp #drv_svc_datetime
 bne service_driver_short_timeout
.service_driver_long_timeout
 lda #&FF
 sta drv_svc_timeout_hi
 lda #8
 sta drv_svc_timeout_outer
 jmp service_driver_wait
.service_driver_short_timeout
 lda #100                 \ two seconds at one yield per video frame
 bne service_driver_set_timeout
.service_driver_set_timeout
 sta drv_svc_timeout_hi
.service_driver_wait
 lda &FC00+drv_svc_command
 cmp #&FF
 bne service_driver_wait_claimed
 jmp service_driver_service_unclaimed
.service_driver_wait_claimed
 bpl service_driver_result
 dec drv_svc_timeout_lo
 bne service_driver_wait
 lda drv_svc_command_copy
 cmp #drv_svc_cancel
 beq service_driver_wait_yield
 jsr check_esc
 bcc service_driver_wait_yield
 lda #&FF
 sta drv_svc_cancelled
 lda #drv_svc_cancel
 jmp service_driver_begin
.service_driver_wait_yield
 lda #19                  \ yield so the Pi cooperative poll can run
 jsr osbyte
 dec drv_svc_timeout_hi
 bne service_driver_wait
 dec drv_svc_timeout_outer
 beq service_driver_timeout
 lda #&FF
 sta drv_svc_timeout_hi
 jmp service_driver_wait
.service_driver_timeout
 jmp service_driver_no_response

.service_driver_result
 cmp #0
 bne service_driver_error
 lda drv_svc_command_copy
 cmp #drv_svc_uef_normalize
 beq service_driver_result_no_copy
 lda #1
 sta &FC00+drv_svc_addr_lo
 \ Every implemented service response starts with visible non-space ASCII.
 \ Reject a floating/unimplemented FCA9 port before relying on JIM paged RAM;
 \ AP5 open-bus values are commonly &20, &FF or &00.
 lda &FC00+drv_svc_data
 cmp #&21
 bcs service_driver_response_visible
 jmp service_driver_no_response
.service_driver_response_visible
 cmp #&7F
 bcc service_driver_response_ascii
 jmp service_driver_no_response
.service_driver_response_ascii
 pha
 lda #0
 sta data_pointer
 lda #240
 sta drv_svc_response_count
 ldx #0
 stx driver_page_shadow
 stx pagereg
 pla
 sta pageram,x
 inx
 stx data_pointer
 dec drv_svc_response_count
.service_driver_copy_response
 lda &FC00+drv_svc_data
 beq service_driver_response_done
 ldx data_pointer
 sta pageram,x
 inx
 stx data_pointer
 dec drv_svc_response_count
 bne service_driver_copy_response
 \ A Pi1MHz reply is limited to 239 bytes plus its terminator.  A missing
 \ terminator usually means an absent service/floating 1MHz bus; never walk
 \ through 64K of host memory or raise ElkWiFi's misleading Buffer full error.
 jmp service_driver_no_response
.service_driver_response_done
 ldx data_pointer
 lda #0
 sta pageram,x
 jmp restore_env
.service_driver_result_no_copy
 lda #1
 sta &FC00+drv_svc_addr_lo
 lda &FC00+drv_svc_data
 rts

.service_driver_error
 cmp #&42
 beq service_driver_error_unsupported
 cmp #&40
 beq service_driver_error_parameter
 cmp #&43
 bne service_driver_error_not_connect
 lda drv_svc_command_copy
 cmp #drv_svc_datetime
 beq service_driver_error_datetime
 jmp service_driver_error_connect
.service_driver_error_not_connect
 cmp #&44
 beq service_driver_error_no_wifi
 ldx #(error_no_response-error_table)
 jmp error
.service_driver_error_unsupported
 ldx #(error_not_implemented-error_table)
 jmp error
.service_driver_error_parameter
 ldx #(error_bad_option-error_table)
 jmp error
.service_driver_error_connect
 ldx #(error_opencon-error_table)
 jmp error
.service_driver_error_datetime
 ldx #(error_no_date_time-error_table)
 jmp error
.service_driver_error_no_wifi
 ldx #(error_device_not_found-error_table)
 jmp error

.service_driver_port_missing
 \ Address/data read-back failed: FCA6-FCA9 is not being served by Pi1MHz.
 ldx #(error_device_not_found-error_table)
 jmp error

.service_driver_service_unclaimed
 \ The services port echoed the dispatch page but no registered range claimed
 \ command 80.  This specifically identifies an old/mismatched Pi kernel.
 ldx #(error_not_implemented-error_table)
 jmp error

.service_driver_no_response
 \ Do not communicate this through pageram: when the Pi/JIM service is absent
 \ there is nowhere for that write to land and generic_cmd prints open-bus
 \ spaces.  Raise the stock ElkWiFi error directly instead.
 ldx #(error_no_response-error_table)
 jmp error
