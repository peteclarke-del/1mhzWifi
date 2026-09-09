\ wicfs_catalogue.asm
\ 1MHz-WiFi ROM: the catalogue lines WiCFS prints while it walks a tape.
\
\ Written for the 1MHz-WiFi project, replacing the two display routines that
\ remained inherited in wicfs.asm. What they print is not inherited design: it
\ is the cassette catalogue layout the MOS itself uses, a ten column filename
\ followed by the block number, and on the last block the length and, under
\ *OPT1,2, the load and execution addresses. The layout is kept exactly, so
\ *CAT output is unchanged byte for byte; only the code producing it is ours.
\
\ Both routines honour the CFS options byte at &E3 masked with optmask, which
\ is how *OPT1,0 suppresses catalogue messages.

\ Print one catalogue line for the block whose header has just been read, and
\ record the block number. With messages suppressed only the record is updated.

.prblock            LDA &E3                 \ CFS options byte
                    AND optmask
                    BEQ prb_record          \ messages off: just record it

                    LDA #cr                 \ return to the left margin
                    JSR OSWRCH
                    LDX #0
.prb_char           LDA &3B2,X              \ the name as stored, to its null
                    BEQ prb_pad
                    JSR OSWRCH
                    INX
                    BNE prb_char

\ Pad a short name out to the block number column. The test is a carry compare
\ rather than an equality one: a name that reached ten characters without a
\ null would otherwise never match, and the old loop padded on around the whole
\ of X before it stopped.
.prb_pad            CPX #10
                    BCS prb_number
                    LDA #sp
                    JSR OSWRCH
                    INX
                    BNE prb_pad

.prb_number         LDA #sp
                    JSR OSWRCH
                    LDA &3C6                \ block number
                    JSR printhex
.prb_record         LDA &3C6
                    STA curblk
                    RTS


\ Complete the catalogue line for a final block: always the sixteen bit length,
\ and under *OPT1,2 the load and execution addresses as well. Resets the block
\ counters, so it is also the end of one file's catalogue entry.

.lastblk
    if __debug = 1
    php:jsr debug
    equs "in lastblk",&0D,&EA
    plp
    endif
                    LDA &E3
                    AND optmask
                    BEQ lblk_x              \ messages off: counters only

                    LDA #sp
                    JSR OSWRCH
                    LDA &3C6                \ length is the block number...
                    JSR printhex
                    LDA blklen              \ ...followed by the block length
                    JSR printhex

                    LDA &E3                 \ *OPT1,2 sets both message bits
                    AND optmask
                    CMP optmask
                    BNE lblk_a1

                    LDA #sp
                    JSR OSWRCH
                    LDX #&BE                \ load address at &03BE
                    JSR prcat_word
                    LDA #sp
                    JSR OSWRCH
                    LDX #&C2                \ execution address at &03C2
                    JSR prcat_word

.lblk_a1            LDA #cr
                    JSR OSASCI
.lblk_x             LDA #0
                    STA curblk
                    STA nxtblk
                    RTS


\ Print the sixteen bit value held low byte first at &0300+X, high byte first
\ as the catalogue shows it. X is the low byte's offset within page three.

.prcat_word         LDA &0301,X
                    JSR printhex
                    LDA &0300,X
                    JMP printhex
