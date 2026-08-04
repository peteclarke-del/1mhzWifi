\ Sideway ROM for Electron Wifi board
\ (c) Roland Leurs, May 2020

\ Pi1MHz WIFI command response handling.
\ Syntax: *WIFI [ON | OFF | SR | HR]

.wifi_cmd       lda (line),y
                cmp #&0D
                beq wifi_badcmd
                jsr skipspace
                cmp #'O'
                beq wifi_on_off
                cmp #'S'
                beq wifi_sr
                cmp #'H'
                beq wifi_hr
.wifi_badcmd    jmp wifi_help

.wifi_hr        ldx #1
                bne wifi_reset

.wifi_sr        ldx #0
.wifi_reset     iny
                lda (line),y
                cmp #'R'
                bne wifi_badcmd
                txa
                jmp generic_cmd             \ perform it and print the device response

.wifi_on_off    jsr skipspace
                cmp #'N'
                beq wifi_on
                cmp #'F'
                bne wifi_badcmd

.wifi_off       jsr printtext
                equs "Switching wifi off",&0D,&EA
                ldx #0
.wifi_off_l1    lda #24
                jmp generic_cmd             \ print WIFI OFF/ready state and final OK

.wifi_on        jsr printtext
                equs "Switching wifi on",&0D,&EA
                ldx #1
                bne wifi_off_l1

.wifi_help      jsr printtext
                equs " ON   enable wifi",&0D
                equs " OFF  disable wifi",&0D
                equs " SR   perform soft reset",&0D
                equs " HR   perform hard reset",&0D,&EA
                jmp call_claimed
