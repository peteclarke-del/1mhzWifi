\ ElkWiFi-compatible driver for the Pi1MHz 1 MHz-bus service
\ (c) Roland Leurs, May 2020

\ Main service ROM
\ Version 1.00

\ AP5/Pi1MHz exposes &FCFF as a write-only JIM page selector. Keep the shadow
\ and transient machine type in the service driver's private block. The stock
\ `heap` at &0900 is ADFS/application workspace and is not safe during OSWORD.
driver_page_shadow = drv_svc_workspace+19
driver_machine = drv_svc_workspace+20
driver_function = drv_svc_workspace+21
driver_entry_x = drv_svc_workspace+22
driver_entry_y = drv_svc_workspace+23

\ Please note that some functions or routines are not quite logical
\ but they are implemented to keep driver compatibility with the 
\ Atom wifi driver.

.wifidriver
 \ entries are.
 \ 00 init                12 cipstatus
 \ 01 reset               13 cipsend
 \ 02 gmr                 14 cipclose
 \ 03 cwlap               15 cipserver
 \ 04 cwjap               16 cipsto
 \ 05 cwqap               17 ciobaud
 \ 06 cwsap               18 cifsr
 \ 07 cwmode              19 ciupdate
 \ 08 cipstart            20 ipd
 \ 09 cpmux               21 csyswdtenable
 \ 10 cwlif               22 csyswdtdisable
 \ 11 setbuffer           23 getmuxchannel
 \ 24 disable/enable
 \ 25 cwlapopt
 \ 26 sslbufsize
 \ 27 cipmode
 \ 28 ping
 \ 29-31 reserved

 sta save_a                 \ save registers
 stx save_x
 sty save_y
 sta driver_function
 stx driver_entry_x
 sty driver_entry_y
 \ OSBYTE &81 with X=0,Y=&FF is the documented machine-type query. Run it
 \ before touching the JIM high selectors and retain the result only for this
 \ driver call; it is not valid as a reset-time cache.
 lda #&81
 ldx #0
 ldy #&FF
 jsr osbyte
 stx driver_machine
 jsr set_bank_0             \ ElkWiFi buffers are in JIM address 00:00:page
 lda #0
 sta driver_page_shadow
 \ ElkWiFi 0.23 masks public function numbers to five bits after handling its
 \ private flash entry. DATE, TIME and ONLINE call Pi routines directly and
 \ therefore do not consume public driver numbers 32-34.
 lda driver_function
 and #&1F
 cmp #0
 bne service_driver_not_0
 jmp service_driver_init
.service_driver_not_0
 cmp #1
 bne service_driver_not_1
 jmp service_driver_reset
.service_driver_not_1
 cmp #2
 bne service_driver_not_2
 jmp service_driver_version
.service_driver_not_2
 cmp #3
 bne service_driver_not_3
 jmp service_driver_scan
.service_driver_not_3
 cmp #4
 bne service_driver_not_4
 jmp service_driver_join
.service_driver_not_4
 cmp #5
 bne service_driver_not_5
 jmp service_driver_leave
.service_driver_not_5
 cmp #6
 bne service_driver_not_6
 jmp service_driver_ifcfg
.service_driver_not_6
 cmp #18
 bne service_driver_not_18
 jmp service_driver_ifcfg
.service_driver_not_18
 cmp #8
 bne service_driver_not_8
 jmp service_driver_cipstart
.service_driver_not_8
 cmp #13
 bne service_driver_not_13
 jmp service_driver_cipsend
.service_driver_not_13
 cmp #14
 bne service_driver_not_14
 jmp service_driver_cipclose
.service_driver_not_14
 cmp #20
 bne service_driver_not_20
 jmp service_driver_ipd
.service_driver_not_20
 cmp #7
 bne service_driver_not_7
 jmp service_driver_mode
.service_driver_not_7
 cmp #9
 bne service_driver_not_9
 jmp service_driver_cpmux
.service_driver_not_9
 cmp #10
 bne service_driver_not_10
 jmp service_driver_connection_status
.service_driver_not_10
 cmp #11
 bne service_driver_not_11
 jmp service_driver_set_buffer
.service_driver_not_11
 cmp #12
 bne service_driver_not_12
 jmp service_driver_connection_status
.service_driver_not_12
 cmp #15
 bne service_driver_not_15
 jmp service_driver_baud_compat
.service_driver_not_15
 cmp #16
 bne service_driver_not_16
 jmp service_driver_baud_compat
.service_driver_not_16
 cmp #17
 bne service_driver_not_17
 jmp service_driver_baud_compat
.service_driver_not_17
 cmp #21
 bne service_driver_not_21
 jmp service_driver_ok
.service_driver_not_21
 cmp #22
 bne service_driver_not_22
 jmp service_driver_ok
.service_driver_not_22
 cmp #23
 bne service_driver_not_23
 jmp service_driver_mux_channel
.service_driver_not_23
 cmp #24
 bne service_driver_not_24
 jmp service_driver_wifi_control
.service_driver_not_24
 cmp #25
 bne service_driver_not_25
 jmp service_driver_lapopt
.service_driver_not_25
 cmp #26
 bne service_driver_not_26
 jmp service_driver_ok
.service_driver_not_26
 cmp #27
 bne service_driver_not_27
 jmp service_driver_mode_unsupported
.service_driver_not_27
 cmp #28
 bne service_driver_not_28
 jmp service_driver_ping
.service_driver_not_28
 cmp #29
 bne service_driver_not_29
 jmp service_driver_unsupported
.service_driver_not_29
 jmp service_driver_unsupported
\ Initialize the data buffer, by resetting the paged ram register to 0. This
\ call does not clear the buffer and will mostly be called after a command
\ is executed and the response is processed.
.reset_buffer
 php
 sei
 ldx #&00
 stx driver_page_shadow
 txa
 jsr select_public_page_a
 plp
 rts

\ Initialize the data buffer, by resetting the paged ram register to 0
\ and clearing the first byte. After a command is executed and if the first
\ byte is 0 then there was no response from the ESP8266. This call is intended
\ before a command is executed.
.clear_buffer
 jsr reset_buffer
 php
 sei
 txa
 jsr select_public_page_a
 stx pageram
 jsr wicfs_bus_delay
 plp
; txa
;.irb_l1
; sta pageram,x
; inx
; bne irb_l1
 rts

\ Reads a character from the paged ram buffer at position X
\ returns the character in A and the X register points 
\ to the next data byte.
.read_buffer
 php
 sei
 lda driver_page_shadow
 jsr select_public_page_a
 lda pageram,x
 plp
 jsr read_buffer_inc
 ora #0                    \ return N/Z for the byte read
 rts
.read_buffer_inc
 inx
 bne read_buffer_end
 jsr inc_page_reg
.read_buffer_end
 rts

\ Writes a character to the paged ram buffer at position X
\ returns with X pointing to the next byte
.write_buffer
 php
 sei
 pha
 lda driver_page_shadow
 jsr select_public_page_a
 pla
 sta pageram,x
 jsr wicfs_bus_delay
 plp
 jmp read_buffer_inc

\ Decrements the 24 bit data pointer. On the Electron most transfers will be smaller than
\ 64 KB but it is possible to send up to 4 MB per transfer.
.dec_data_counter
 sec
 lda data_counter
 sbc #1
 sta data_counter
 lda data_counter+1
 sbc #0
 sta data_counter+1
 lda data_counter+2
 sbc #0
 sta data_counter+2
 ora data_counter+1
 ora data_counter
 rts
\ Finalise a Pi1MHz response buffered in JIM.
.restore_env
.set_buffer
 stx datalen            \ save end of data
 ldx driver_page_shadow
 stx datalen+1
 ldx datalen            \ restore x register
rts

\ Increments the paged ram register and sets the (X) pointer to the beginning of the page. 
\ If the end of paged ram has been reached then the page register will roll over from &FF
\ to &00 and the Z flag is set. The pageregister and X will not be updated and the routine
\ returns with Z=1. The calling routine can test this flag for the end of buffer.
.inc_page_reg
 ldx driver_page_shadow \ use the write-only page register's RAM shadow
 inx                    \ increment the value
 beq buffer_end         \ if it becomes zero then the end of the buffer (paged ram) is reached
 stx driver_page_shadow
 php
 sei
 txa
 jsr select_public_page_a \ write back to page register (i.e. select next page)
 plp
 ldx #0                 \ reset y register
 cpx #1                 \ clears Z-flag
.buffer_end
 rts                    \ return to store routine
