\ Pi1MHz JIM helpers retained under the stock ElkWiFi labels. An unmodified
\ Electron AP5 forwards only &FCFF and JIM, so it must not touch &FCFD/&FCFE.
\ Direct BBC-family Pi1MHz systems expose those selectors and must explicitly
\ return them to bank 00:00 after another JIM client has changed them.

.detect_jim_machine
 pha
 txa
 pha
 tya
 pha
 lda #&81
 ldx #0
 ldy #&FF
 jsr osbyte
 stx driver_machine
 pla
 tay
 pla
 tax
 pla
 rts

.set_bank_0
 lda #0
 jsr select_public_page_a
 lda #0
 rts

\ Select JIM address 00:00:A while preserving X. Electron/AP5 does not forward
\ FCFD/FCFE; direct BBC-family hosts must reassert them in every masked JIM
\ transaction because another expansion or interrupt handler may change them.
.select_public_page_a
 pha
 txa
 pha
 lda #0
 ldx driver_machine
 cpx #1
 beq set_bank_0_page
 sta &FCFD
 jsr wicfs_bus_delay
 sta &FCFE
 jsr wicfs_bus_delay
.set_bank_0_page
 pla
 tax
 pla
 sta pagereg
 jsr wicfs_bus_delay
 rts

set_bank_1 = set_bank_0
