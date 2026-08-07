\ Pi1MHz JIM helpers retained under the stock ElkWiFi labels. An unmodified
\ AP5 forwards only &FCFF and JIM, so the host-visible buffer is one 64K bank.
\ &FCFD/&FCFE must not be used: they never reach the Pi on real hardware.

.save_bank_nr
 rts

.restore_bank_nr
 rts

.set_bank_nr
 and #&01
 rts

.set_bank_0
 lda #0
 rts

.set_bank_1
 lda #1
 rts

.set_bank_a
 and #&01
 rts

.test_wifi_ena
 lda #0
 and #&01
 rts
