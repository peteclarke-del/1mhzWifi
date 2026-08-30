\ Interactive FTP client. Control and data sockets remain on the Pi; local
\ files are opened through MOS so ADFS, DFS and MMFS all use their normal
\ filing-system paths. No Tube address is passed to the service.

ftp_cmd_open   = 114
ftp_cmd_exec   = 115
ftp_cmd_read   = 116
ftp_cmd_write  = 117
ftp_cmd_close  = 118
ftp_cmd_cancel = 119
ftp_eof        = &20
ftp_scratch_max = 240
ftp_action_quit = 1
ftp_action_help = 2
ftp_action_get  = 3
ftp_action_put  = 4
ftp_action_list = 5
ftp_delim_exact = 0
ftp_delim_space = 1
ftp_delim_either = 2

ftp_OSFIND = &FFCE
ftp_OSBPUT = &FFD4
ftp_OSBGET = &FFD7

ftp_line_block = heap+&A0
ftp_handle     = heap+&A5
ftp_count      = heap+&A6
ftp_index      = heap+&A7
ftp_transfer   = heap+&A8
ftp_name_lo    = heap+&A9
ftp_name_hi    = heap+&AA
ftp_remote_lo  = heap+&AB
ftp_remote_hi  = heap+&AC
ftp_ptr_lo     = zp+6
ftp_ptr_hi     = zp+7

.ftp_cmd
 jsr skipspace1
 jsr read_cli_param
 cpx #0
 bne ftp_open
 jsr printtext
 equs "Usage: *FTP <host|ftp://host[:port]>",&0D,&EA
 jmp call_claimed

.ftp_open
 lda #ftp_cmd_open
 jsr ftp_request_string
 beq ftp_open_ok
 jmp ftp_error_claimed
.ftp_open_ok
 jsr ftp_print_response
.ftp_loop
 jsr printtext
 equs "ftp> ",&EA
 lda #<strbuf
 sta ftp_line_block
 lda #>strbuf
 sta ftp_line_block+1
 lda #120
 sta ftp_line_block+2
 lda #32
 sta ftp_line_block+3
 lda #126
 sta ftp_line_block+4
 lda #0
 ldx #<ftp_line_block
 ldy #>ftp_line_block
 jsr OSWORD
 bcc ftp_input_ok
 jmp ftp_close_claimed
.ftp_input_ok
 lda #0
 sta strbuf,y
 cpy #0
 beq ftp_loop
 jsr ftp_classify
 cmp #ftp_action_quit
 bne ftp_input_not_quit
 jmp ftp_close_claimed
.ftp_input_not_quit
 cmp #ftp_action_help
 bne ftp_input_not_help
 jmp ftp_help
.ftp_input_not_help
 cmp #ftp_action_get
 bne ftp_input_not_get
 jmp ftp_get
.ftp_input_not_get
 cmp #ftp_action_put
 bne ftp_input_not_put
 jmp ftp_put
.ftp_input_not_put
 cmp #ftp_action_list
 beq ftp_input_list
 jmp ftp_exec_plain
.ftp_input_list
 jmp ftp_exec_list

; Classify only commands requiring local handling. Unknown and near-matching
; words are passed to the Pi unchanged, so GETX/QUERY cannot become GET/QUIT.
.ftp_classify
 lda #<ftp_command_table
 sta ftp_ptr_lo
 lda #>ftp_command_table
 sta ftp_ptr_hi
.ftp_classify_next
 ldy #0
 lda (ftp_ptr_lo),y
 beq ftp_classify_plain
 sta ftp_transfer
 iny
 lda (ftp_ptr_lo),y
 sta ftp_count
 iny
 lda (ftp_ptr_lo),y
 sta ftp_index
 ldx #0
.ftp_classify_char
 iny
 lda strbuf,x
 ora #&20
 cmp (ftp_ptr_lo),y
 bne ftp_classify_advance
 inx
 dec ftp_index
 bne ftp_classify_char
 lda strbuf,x
 ldx ftp_count
 beq ftp_classify_need_end
 cpx #ftp_delim_space
 beq ftp_classify_need_space
 cmp #0
 beq ftp_classify_match
.ftp_classify_need_space
 cmp #' '
 beq ftp_classify_match
 bne ftp_classify_advance
.ftp_classify_need_end
 cmp #0
 bne ftp_classify_advance
.ftp_classify_match
 lda ftp_transfer
 rts
.ftp_classify_advance
 ldy #2
 lda (ftp_ptr_lo),y
 clc
 adc #3
 adc ftp_ptr_lo
 sta ftp_ptr_lo
 bcc ftp_classify_next
 inc ftp_ptr_hi
 bne ftp_classify_next
.ftp_classify_plain
 lda #0
 rts

.ftp_command_table
 equb ftp_action_quit,ftp_delim_exact,4
 equs "quit"
 equb ftp_action_quit,ftp_delim_exact,3
 equs "bye"
 equb ftp_action_help,ftp_delim_exact,4
 equs "help"
 equb ftp_action_get,ftp_delim_space,3
 equs "get"
 equb ftp_action_put,ftp_delim_space,3
 equs "put"
 equb ftp_action_list,ftp_delim_either,3
 equs "dir"
 equb ftp_action_list,ftp_delim_either,2
 equs "ls"
 equb 0

.ftp_exec_plain
 lda #ftp_cmd_exec
 jsr ftp_request_string
 beq ftp_plain_ok
 jmp ftp_show_error
.ftp_plain_ok
 jsr ftp_print_response
 jmp ftp_loop

.ftp_exec_list
 lda #ftp_cmd_exec
 jsr ftp_request_string
 beq ftp_list_ok
 jmp ftp_show_error
.ftp_list_ok
 jsr ftp_print_response
 lda ftp_transfer
 cmp #3
 bne ftp_list_done
 jsr ftp_read_console
 beq ftp_list_done
 jmp ftp_show_error
.ftp_list_done
 jmp ftp_loop

.ftp_get
 jsr ftp_parse_two_names
 bcc ftp_get_parsed
 jmp ftp_usage_command
.ftp_get_parsed
 lda ftp_name_lo
 ora ftp_name_hi
 bne ftp_get_have_local
 jsr ftp_remote_basename
.ftp_get_have_local
 lda #ftp_cmd_exec
 jsr ftp_request_string
 beq ftp_get_started
 jmp ftp_show_error
.ftp_get_started
 jsr ftp_print_response
 lda ftp_transfer
 cmp #1
 beq ftp_get_transfer
 jmp ftp_loop
.ftp_get_transfer
 jsr ftp_name_terminate
 lda #&80
 ldx ftp_name_lo
 ldy ftp_name_hi
 jsr ftp_OSFIND
 sta ftp_handle
 bne ftp_get_file_open
 jmp ftp_local_error
.ftp_get_file_open
.ftp_get_read
 lda #ftp_scratch_max
 jsr ftp_read_begin
 cmp #ftp_eof
 beq ftp_get_done
 cmp #0
 beq ftp_get_data
 jmp ftp_get_failed
.ftp_get_data
 jsr ftp_copy_to_file
 jmp ftp_get_read
.ftp_get_done
 jsr ftp_close_file
 jsr ftp_print_response
 jmp ftp_loop
.ftp_get_failed
 pha
 jsr ftp_close_file
 pla
 jmp ftp_show_error

.ftp_put
 jsr ftp_parse_two_names
 bcc ftp_put_parsed
 jmp ftp_usage_command
.ftp_put_parsed
 lda ftp_name_lo
 sta ftp_remote_lo
 lda ftp_name_hi
 sta ftp_remote_hi
 jsr ftp_first_name
 jsr ftp_name_terminate
 lda #&40
 ldx ftp_name_lo
 ldy ftp_name_hi
 jsr ftp_OSFIND
 sta ftp_handle
 bne ftp_put_file_open
 jmp ftp_local_error
.ftp_put_file_open
 jsr ftp_name_unterminate
 lda ftp_remote_lo
 sta ftp_name_lo
 lda ftp_remote_hi
 sta ftp_name_hi
 jsr ftp_build_put
 lda #ftp_cmd_exec
 jsr ftp_request_string
 beq ftp_put_started
 jmp ftp_put_failed
.ftp_put_started
 jsr ftp_print_response
 lda ftp_transfer
 cmp #2
 beq ftp_put_transfer
 jsr ftp_close_file
 jmp ftp_loop
.ftp_put_transfer
.ftp_put_fill
 jsr net_scratch_address
 lda #0
 sta ftp_count
.ftp_put_byte
 ldy ftp_handle
 jsr ftp_OSBGET
 bcs ftp_put_send
 jsr net_write_a
 inc ftp_count
 lda ftp_count
 cmp #ftp_scratch_max
 bne ftp_put_byte
.ftp_put_send
 lda ftp_count
 jsr ftp_write_count
 sta ftp_transfer
 lda ftp_count
 beq ftp_put_finished
 lda ftp_transfer
 cmp #0
 beq ftp_put_fill
 jmp ftp_put_failed
.ftp_put_finished
 lda ftp_transfer
 cmp #ftp_eof
 beq ftp_put_complete
 jmp ftp_put_failed
.ftp_put_complete
 jsr ftp_close_file
 jsr ftp_print_response
 jmp ftp_loop
.ftp_put_failed
 pha
 jsr ftp_close_file
 pla
 jmp ftp_show_error

.ftp_read_console
.ftp_read_console_again
 lda #ftp_scratch_max
 jsr ftp_read_begin
 cmp #ftp_eof
 beq ftp_read_console_done
 cmp #0
 bne ftp_read_console_rts
 jsr net_scratch_address
.ftp_read_console_byte
 lda ftp_count
 beq ftp_read_console_again
 jsr net_read_a
 jsr osasci
 dec ftp_count
 bne ftp_read_console_byte
 beq ftp_read_console_again
.ftp_read_console_done
 jsr ftp_print_response
 lda #0
.ftp_read_console_rts
 rts

.ftp_copy_to_file
 jsr net_scratch_address
.ftp_copy_to_file_byte
 lda ftp_count
 beq ftp_copy_to_file_done
 jsr net_read_a
 ldy ftp_handle
 jsr ftp_OSBPUT
 dec ftp_count
 bne ftp_copy_to_file_byte
.ftp_copy_to_file_done
 rts

.ftp_read_begin
 pha
 jsr net_command_address
 lda #ftp_cmd_read
 jsr net_write_a
 pla
 jsr net_write_a
 jsr ftp_dispatch
 pha
 jsr net_command_address
 lda #1
 jsr net_address_low
 jsr net_read_a
 sta ftp_count
 pla
 rts

.ftp_write_count
 pha
 jsr net_command_address
 lda #ftp_cmd_write
 jsr net_write_a
 pla
 jsr net_write_a
 jmp ftp_dispatch

.ftp_request_string
 pha
 jsr net_command_address
 pla
 jsr net_write_a
 ldx #0
.ftp_request_copy
 lda strbuf,x
 jsr net_write_a
 beq ftp_request_sent
 inx
 cpx #121
 bne ftp_request_copy
 lda #&23
 rts
.ftp_request_sent
 jmp ftp_dispatch

.ftp_dispatch
 jsr net_dispatch_wait
 cmp #&2A
 bne ftp_dispatch_done
 jsr net_command_address
 lda #ftp_cmd_cancel
 jsr net_write_a
 jsr net_dispatch_wait
 lda #&2A
.ftp_dispatch_done
 rts

.ftp_print_response
 jsr net_command_address
 lda #1
 jsr net_address_low
 jsr net_read_a
 sta ftp_transfer
 jsr net_read_a
.ftp_print_response_loop
 beq ftp_print_response_done
 jsr osasci
 jsr net_read_a
 bne ftp_print_response_loop
.ftp_print_response_done
 rts

.ftp_parse_two_names
 lda #0
 sta ftp_name_lo
 sta ftp_name_hi
 ldx #3
 lda strbuf,x
 cmp #' '
 bne ftp_parse_bad
.ftp_parse_skip
 inx
 lda strbuf,x
 cmp #' '
 beq ftp_parse_skip
 cmp #0
 beq ftp_parse_bad
.ftp_parse_remote
 inx
 lda strbuf,x
 beq ftp_parse_ok
 cmp #' '
 bne ftp_parse_remote
 lda #0
 sta strbuf,x
.ftp_parse_local_skip
 inx
 lda strbuf,x
 cmp #' '
 beq ftp_parse_local_skip
 cmp #0
 beq ftp_parse_ok
 txa
 clc
 adc #<strbuf
 sta ftp_name_lo
 lda #>strbuf
 adc #0
 sta ftp_name_hi
.ftp_parse_ok
 clc
 rts
.ftp_parse_bad
 sec
 rts

.ftp_first_name
 lda #<(strbuf+4)
 sta ftp_name_lo
 lda #>(strbuf+4)
 sta ftp_name_hi
 rts

.ftp_remote_basename
 ldx #4
 stx ftp_index
.ftp_basename_loop
 lda strbuf,x
 beq ftp_basename_done
 cmp #'/'
 bne ftp_basename_next
 inx
 stx ftp_index
 dex
.ftp_basename_next
 inx
 bne ftp_basename_loop
.ftp_basename_done
 ldx ftp_index
 txa
 clc
 adc #<strbuf
 sta ftp_name_lo
 lda #>strbuf
 adc #0
 sta ftp_name_hi
 rts

.ftp_build_put
 \ The local file is already open. If a second argument was supplied it is
 \ the remote name; otherwise reuse the local name following PUT and space.
 lda ftp_name_lo
 ora ftp_name_hi
 beq ftp_build_put_done
 jsr ftp_set_name_pointer
 ldy #0
 ldx #4
.ftp_build_put_loop
 lda (ftp_ptr_lo),y
 sta strbuf,x
 beq ftp_build_put_done
 inx
 iny
 bne ftp_build_put_loop
.ftp_build_put_done
 lda #'P'
 sta strbuf
 lda #'U'
 sta strbuf+1
 lda #'T'
 sta strbuf+2
 lda #' '
 sta strbuf+3
 rts

.ftp_name_terminate
 jsr ftp_set_name_pointer
 ldy #0
.ftp_name_end_loop
 lda (ftp_ptr_lo),y
 beq ftp_name_end
 iny
 bne ftp_name_end_loop
.ftp_name_end
 lda #&0D
 sta (ftp_ptr_lo),y
 rts

.ftp_name_unterminate
 jsr ftp_set_name_pointer
 ldy #0
.ftp_name_unterminate_loop
 lda (ftp_ptr_lo),y
 cmp #&0D
 beq ftp_name_unterminate_done
 iny
 bne ftp_name_unterminate_loop
.ftp_name_unterminate_done
 lda #0
 sta (ftp_ptr_lo),y
 rts

.ftp_set_name_pointer
 lda ftp_name_lo
 sta ftp_ptr_lo
 lda ftp_name_hi
 sta ftp_ptr_hi
 rts

.ftp_close_file
 ldy ftp_handle
 beq ftp_close_file_done
 lda #0
 jsr ftp_OSFIND
 lda #0
 sta ftp_handle
.ftp_close_file_done
 rts

.ftp_help
 jsr printtext
 equs "USER PASS PWD CD DIR LS GET PUT",&0D
 equs "DELETE MKDIR RMDIR ASCII BINARY QUIT",&0D,&EA
 jmp ftp_loop
.ftp_usage_command
 jsr printtext
 equs "Usage: GET remote [local]",&0D
 equs "       PUT local [remote]",&0D,&EA
 jmp ftp_loop
.ftp_local_error
 jsr printtext
 equs "Cannot open local file",&0D,&EA
 jmp ftp_loop
.ftp_show_error
 jsr ftp_error_text
 jmp ftp_loop
.ftp_error_claimed
 jsr ftp_error_text
 jmp call_claimed
.ftp_error_text
 pha
 jsr printtext
 equs "FTP error &",&EA
 pla
 jsr printhex
 jmp osnewl
.ftp_close_claimed
 jsr net_command_address
 lda #ftp_cmd_close
 jsr net_write_a
 jsr ftp_dispatch
 jmp call_claimed
