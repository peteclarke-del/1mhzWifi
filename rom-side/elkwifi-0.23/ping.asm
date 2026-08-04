\ ElkWiFi-compatible PING through the Pi1MHz service.

ping_wait_count = errorspace+18

.ping_cmd
 jsr skipspace1
 jsr read_cli_param
 cpx #&00
 bne ping_start
 jsr printtext
 equs "Usage: *PING <hostname or IP>",&0D,&EA
 jmp call_claimed

.ping_start
 ldx #5
 stx size
 ldx #32
 stx time_out
.ping_loop
 ldx #>strbuf
 ldy #<strbuf
 lda #28
 jsr wifidriver
 lda drv_svc_cancelled
 bne ping_cancelled

 lda pageram
 cmp #'+'
 bne ping_error
 lda pageram+1
 cmp #'t'
 beq ping_time_out
 jsr printtext
 equs "Received response in ",&EA
 ldy #1
.ping_print_ms
 lda pageram,y
 cmp #&0D
 beq ping_ms
 sta save_y
 jsr oswrch
 lda save_y
 iny
 bpl ping_print_ms
.ping_ms
 jsr printtext
 equs " ms",&0D,&EA
.ping_wait
 ldx #50
 stx ping_wait_count
.ping_wait_loop
 jsr check_esc
 bcs ping_cancelled
 lda #19
 jsr osbyte
 dec ping_wait_count
 bne ping_wait_loop

 dec size
 bne ping_loop
.ping_cancelled
 jmp call_claimed

.ping_error
 jsr printtext
 equs "Host error (dns or network)",&0D,&EA
 jmp ping_wait

.ping_time_out
 jsr printtext
 equs "No response received from host",&0D,&EA
 jmp ping_wait
