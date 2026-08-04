\ Pi1MHz JIM window helpers retained under the stock ElkWiFi labels.
\ The cartridge UART is not present and no &FC30-&FC3F code is emitted.

bank_save = save_a

.save_bank_nr
 pha
 lda &FCFE
 sta bank_save
 pla
 rts

.restore_bank_nr
 pha
 lda bank_save
 sta &FCFE
 pla
 rts

.set_bank_nr
 pha
 and #&01
 sta &FCFE
 pla
 rts

.set_bank_0
 lda #0
 sta &FCFE
 rts

.set_bank_1
 lda #1
 sta &FCFE
 rts

.set_bank_a
 and #&01
 sta &FCFE
 rts

.test_wifi_ena
 lda #0
 and #&01
 rts
