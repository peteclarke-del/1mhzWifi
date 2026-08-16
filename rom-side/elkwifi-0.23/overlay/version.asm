\ 1MHzWifi version and shared simple-command response handler.

\ Syntax: *VERSION

.version_cmd
  jsr printtext
 equs "1MHzWifi 0.1.53 (C) 2026 Peter Clarke",&0D
  equs "Original elkWifi (C) 2020 Roland Leurs",&0D,&EA

  \ Print the Pi1MHz service version after the two ROM attribution lines.
  lda #2

.generic_cmd
  jsr wifidriver
  jsr reset_buffer
  jsr read_buffer
  beq no_device
  dex
.version_l2
  jsr read_buffer
  jsr oswrch
  lda datalen+1
  cmp driver_page_shadow
  bne version_l2
  cpx datalen
  bne version_l2

.version_end
  jmp call_claimed

.no_device
  ldx #(error_no_response-error_table)
  jmp error
