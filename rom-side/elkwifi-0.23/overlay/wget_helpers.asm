\ Helpers shared by the Pi1MHz WGET implementation.
\ The inherited UART/AT-command downloader is deliberately not emitted.

proto = heap+&F5
newln = heap+&F6
clptr = heap+&F7
index = heap+&F8
sflag = heap+&F9
tflag = heap+&FA
aflag = heap+&FB
pflag = heap+&FC
uflag = heap+&FD
laddr = heap+&FE

.wget_context_switch_in
 pha
 lda net_primary_page
 sta load_addr+1
 jsr set_bank_1
 lda pr_r
 sta pagereg
 ldy pr_y
 pla
 rts

.wget_context_switch_out
 pha
 sty pr_y
 jsr set_bank_0
 lda load_addr+1
 sta net_primary_page
 sta pagereg
 pla
 rts

.wget_set_default_load
 pha
 txa
 pha
 tya
 pha
 lda #&83
 jsr osbyte
 stx laddr
 sty laddr+1
 pla
 tay
 pla
 tax
 pla
 rts

.wget_copy_file_to_swr
 ldy #(wget_swramload_end-wget_swramload)
.wget_copy_file_l1
 lda wget_swramload,y
 sta heap,y
 dey
 bpl wget_copy_file_l1
 jsr wget_context_switch_in
 jsr heap
 jsr wget_context_switch_out
 rts

.wget_swramload
 lda #15
 sta switch
 lda laddr
 and #&0F
 sta switch
 sei
 ldx #0
 stx pr_r
 stx pagereg
 stx zp+2
 lda #&80
 sta zp+3
 lda #&40
 sta zp+4
 ldy #0
.wget_swramload_l1
 lda pageram,x
 sta (zp+2),y
 cmp (zp+2),y
 bne wget_swramload_err
 inx
 iny
 bne wget_swramload_l1
 inc pr_r
 lda pr_r
 sta pagereg
 inc zp+3
 dec zp+4
 bne wget_swramload_l1
 lda shadow
 sta switch
 cli
 rts

.wget_swramload_err
 lda shadow
 sta switch
 cli
 brk
 equb 0
 equs "Not swram",0
.wget_swramload_end
