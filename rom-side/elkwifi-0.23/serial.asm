\ Pi1MHz JIM address helpers retained under the stock ElkWiFi labels.
\ The cartridge UART is not present and no &FC30-&FC3F code is emitted.

bank_high_save = heap+&D6
bank_mid_save = heap+&D7

.save_bank_nr
 pha
 lda &FCFD
 sta bank_high_save
 lda &FCFE
 sta bank_mid_save
 pla
 rts

.restore_bank_nr
 pha
 lda bank_high_save
 sta &FCFD
 lda bank_mid_save
 sta &FCFE
 pla
 rts

.set_bank_nr
 pha
 and #&01
 pha
 lda #0
 sta &FCFD
 pla
 sta &FCFE
 pla
 rts

.set_bank_0
 lda #0
 sta &FCFD
 sta &FCFE
 rts

.set_bank_1
 lda #0
 sta &FCFD
 lda #1
 sta &FCFE
 rts

.set_bank_a
 and #&01
 pha
 lda #0
 sta &FCFD
 pla
 sta &FCFE
 rts

.test_wifi_ena
 lda #0
 and #&01
 rts
