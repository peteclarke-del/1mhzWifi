\ 1mhzwicfs.asm
\ 1MHz-WiCFS: the UEF cassette filing system, as a sideways ROM of its own.
\
\ This is the second of the two images the project builds. It exists because
\ wicfs.asm is the only file left that derives from somebody else's work, from
\ ElkWiFi 0.23 and through it from Martin Barr's UPCFS, and neither author has
\ stated any licence terms. Keeping it in its own ROM means the 1MHz-WiFi image
\ is entirely ours and can be licensed, published or offered upstream on its
\ own, while this one can be withheld, or shipped as patches rather than as a
\ binary, until that is settled.
\
\ The two ROMs do not call each other. What passes between them is data in the
\ JIM window: *WGET -U downloads a normalised UEF image there and records its
\ length and cursor in the four bytes machine.asm documents as the contract,
\ and this ROM streams the image out of the same window. Either ROM works with
\ the other absent, so a machine can be fitted with one, the other or both.
\
\ Pi1MHz serves sideways ROMs from its own directory, so this costs no physical
\ ROM socket on any of the four target machines.

include "machine.asm"

\ ---------------------------------------------------------------------------
\ Image headers
\ ---------------------------------------------------------------------------

.atmheader          equs "1mhzwicfs.rom",0,0,0
                    equw &1800
                    equw &1800
                    equw romend-romstart

.romstart           equb 0
                    equb 0
                    equb 0
                    jmp service
                    equb &82                    \ service ROM, no language
                    equb (copyright-romstart)
                    equb &30
.romtitle           equs "1MHz-WiCFS"
                    equb 0
.romversion         equs "0.1.67"
.copyright          equb 0
                    equs "(C)2026 Peter Clarke"
                    equb 0

\ The keyword *HELP matches on, stored reversed.
.commands           equs "SFCIW"

\ ---------------------------------------------------------------------------
\ Service entry
\ ---------------------------------------------------------------------------
\ Reason 1 is answered so the filing system can release its vectors after a
\ reset. This ROM does not claim OSWORD &65: that is the network ROM's
\ interface and only one image may answer it.

.service            cmp #4
                    beq command
                    cmp #9
                    beq help
                    cmp #1
                    bne service_done
                    jmp autorun
.service_done       rts

\ ---------------------------------------------------------------------------
\ Command dispatch
\ ---------------------------------------------------------------------------
\ Identical in shape to the network ROM's: an entry is the command name in
\ ASCII followed by the handler address, high byte first, and a bare address
\ with no name terminates the table. Every BNE after an INX stands in for a
\ JMP, since X only returns to zero if the table passes 256 bytes.

\ Without a writable workspace every handler below would scribble on memory
\ this ROM does not own, so none of them may run.  Decline the service call
\ rather than raising an error: A is still 4 and nothing has been pushed, so
\ the MOS carries on offering the command to lower-priority ROMs and reports
\ "Bad command" if nobody takes it.
\
\ Raising an error here instead, which is what this did first, was wrong
\ twice over.  The test runs before the command table is searched, so it
\ answered for every unrecognised command on the machine and not just this
\ ROM's, which broke other ROMs' commands and the MOS's own.  And the error
\ was a BRK with its message inline in the bank, which the MOS cannot read
\ back once it has paged this ROM out: the screen filled with whatever the
\ incoming ROM had at those addresses, which on an Electron is BASIC's
\ keyword table.  The reason is printed once at reset instead, where OSWRCH
\ works and the text is addressable.
.command            bit ws_flag
                    bpl command_declined
IF WS_IN_IMAGE = 0
                    \ Claimed host RAM is not ours the way an image is: the
                    \ flag alone would be a single byte of uninitialised RAM
                    \ that could read back as set, so the signature autorun
                    \ stamped beside it is checked as well.
                    lda ws_signature
                    cmp #ws_signature_lo
                    bne command_declined
                    lda ws_signature+1
                    cmp #ws_signature_hi
                    bne command_declined
                    lda #4                      \ the compares clobbered A
ENDIF
                    jmp command_have_ws
.command_declined   lda #4                      \ unclaimed: pass it on
                    rts
.command_have_ws    tya
                    pha
                    txa
                    pha
                    cld
                    ldx #0
.cmd_entry          ldy #0
                    jsr skipspace
                    dey
.cmd_step           iny
                    lda commandtable,x
                    bmi cmd_dispatch
                    cmp (line),y
                    bne cmd_mismatch
                    inx
                    bne cmd_step

.cmd_mismatch       lda (line),y
                    cmp #'.'
                    beq cmd_abbreviated
.cmd_skip_name      lda commandtable,x
                    bmi cmd_skip_address
                    inx
                    bne cmd_skip_name
.cmd_skip_address   inx
                    inx
                    bne cmd_entry

.cmd_abbreviated    iny
.cmd_abbrev_skip    lda commandtable,x
                    bmi cmd_dispatch
                    inx
                    bne cmd_abbrev_skip

.cmd_dispatch       sta zp+1
                    lda commandtable+1,x
                    sta zp
                    jmp (zp)

.command_x6         pla
                    tax
                    pla
                    tay
                    lda #4
                    rts

\ ---------------------------------------------------------------------------
\ *HELP
\ ---------------------------------------------------------------------------

.help               tya
                    pha
                    txa
                    pha
                    lda (line),y
                    cmp #&D
                    beq help_l2
                    ldx #4
.help_l1            lda (line),y
                    cmp commands,x
                    bne help_l3
                    iny
                    dex
                    bpl help_l1
                    jsr print_help
                    jmp call_claimed
.help_l2            jsr help_version
                    jsr printtext
                    equb &D,&20,&20
                    equs "WICFS",&D,&EA
.help_l3            pla
                    tax
                    pla
                    tay
                    lda #9
                    rts

\ ---------------------------------------------------------------------------
\ Reset
\ ---------------------------------------------------------------------------
\ The MOS rebuilds the standard and extended vectors before this call, so
\ persisted state is only meaningful if BYTEV still proves the RAM cassette
\ trap survived. Read it only then, and release only the entries this ROM
\ owns. This moved here with the filing system: the network ROM used to reach
\ into it, and no longer needs to know the filing system exists.

.autorun
IF WS_IN_IMAGE = 0
                    \ Service call 1 hands the first free page of absolute
                    \ workspace in Y. This image needs a fixed range, because
                    \ every workspace reference in it is an absolute address,
                    \ so it can only take that range if nothing claimed
                    \ earlier has already reached past the start of it. When
                    \ it can, it raises Y over the pages it takes; when it
                    \ cannot, it claims nothing and leaves the signature
                    \ below unwritten, so the command entry refuses rather
                    \ than writing into another ROM's workspace.
                    cpy #WS_HOST_PAGE
                    beq autorun_may_claim
                    bcc autorun_may_claim
                    clc                         \ carry clear: not ours
                    bcc autorun_claim_decided   \ always
.autorun_may_claim  ldy #ws_host_end            \ raise Y over our pages
                    sec                         \ carry set: claimed
.autorun_claim_decided
ENDIF
                    tya
                    pha
                    txa
                    pha

IF WS_IN_IMAGE = 0
                    bcc autorun_claim_done      \ nothing claimed, touch none
ENDIF
                    \ Is the image writable?  Pi1MHz loads this ROM into
                    \ sideways RAM, where the workspace above the code is
                    \ ours to use.  Burnt into a real ROM the writes would go
                    \ nowhere, and every command would read back whatever the
                    \ image holds, so record the answer once, here, and let
                    \ the command entry refuse rather than misbehave.
                    \ ws_flag is itself inside the image: in ROM it keeps its
                    \ assembled 0 however often this runs.
                    lda ws_base
                    pha                         \ do not disturb the workspace
                    lda #&A5
                    sta ws_base
                    cmp ws_base
                    bne autorun_read_only
                    lda #&5A                    \ both ways: a bus that floats
                    sta ws_base                 \ high would pass the first
                    cmp ws_base
                    bne autorun_read_only
                    lda #&80                    \ bit 7, so the command entry
                    sta ws_flag                 \ can test it with BIT/BMI
.autorun_read_only  pla
                    sta ws_base
IF WS_IN_IMAGE = 0
                    \ Claimed host RAM is not ours the way an image is: the
                    \ flag alone would be a single byte of uninitialised RAM
                    \ that could read back as set. Stamp a signature beside
                    \ it and have the command entry check both, so workspace
                    \ this image never claimed, or that another ROM has since
                    \ taken, is refused instead of used.
                    lda #ws_signature_lo
                    sta ws_signature
                    lda #ws_signature_hi
                    sta ws_signature+1
.autorun_claim_done
ENDIF

                    \ Say why, once.  Without this the filing system just
                    \ answers "Bad command" to *UEF and *WICFS and gives the
                    \ user nothing to go on.  The network image prints the
                    \ same line under its banner; this one has no banner, so
                    \ it prints on its own.
                    bit ws_flag
                    bmi autorun_ws_ready
                    jsr printtext
                    equs "1MHz-WiCFS needs sideways RAM",&D,&EA
.autorun_ws_ready

                    lda BYTEV
                    cmp #<notape
                    bne autorun_released
                    lda BYTEV+1
                    cmp #>notape
                    bne autorun_released
                    jsr release_owned_wicfs
                    bcs autorun_abort
.autorun_released   pla
                    tax
                    pla
                    tay
                    lda #1
                    rts

\ Release failed. Leave the vectors alone rather than resetting into an
\ inconsistent filing system.
.autorun_abort      pla
                    tax
                    pla
                    tay
                    lda #1
                    rts

\ ---------------------------------------------------------------------------
\ Command table
\ ---------------------------------------------------------------------------
\ Longer names must precede any name they begin with, so QUPRUN is listed
\ before QR and QUPCFS before neither, being distinct.

.commandtable       equs "QUPRUN"
                    equb >uef_run_cmd, <uef_run_cmd
                    equs "QR"
                    equb >uef_run_cmd, <uef_run_cmd
                    equs "QAUTO"
                    equb >uef_auto_cmd, <uef_auto_cmd
                    equs "QHOST"
                    equb >host_basic_cmd, <host_basic_cmd
                    equs "QUPCFS"
                    equb >bUPCFS, <bUPCFS
                    equs "UEF"
                    equb >uef_cmd, <uef_cmd
                    equs "WICFS"
                    equb >wicfs_cmd, <wicfs_cmd
                    equs "REWIND"
                    equb >rewind_cmd, <rewind_cmd
                    equb >command_x6, <command_x6

.help_version       ldx #0
.help_vl1           lda romtitle,x
                    bne help_vl2
                    lda #&20
.help_vl2           jsr osasci
                    inx
                    cpx #(copyright-romtitle)
                    bne help_vl1
                    rts

\ The names come out of the command table, which already holds them: storing
\ a second copy with each description cost 200 of this block's 643 bytes, and
\ room in the bank is what decides whether a filing system can share it.  The
\ descriptions below are in TABLE order, so they stay paired with the names.
.print_help         jsr help_version
                    lda #<commandtable
                    sta help_tbl
                    lda #>commandtable
                    sta help_tbl+1
                    lda #<help_descriptions
                    sta help_txt
                    lda #>help_descriptions
                    sta help_txt+1
                    lda #&0D
                    jsr OSASCI
.phd_entry          ldy #0
                    lda (help_tbl),y
                    bmi phd_done
                    lda #' '
                    jsr OSWRCH
                    ldx #1                      \ columns used, including it
.phd_name           lda (help_tbl),y
                    bmi phd_name_done
                    jsr OSWRCH
                    iny
                    inx
                    bne phd_name
.phd_name_done      iny                         \ step over the address bytes
                    iny
                    tya
                    clc
                    adc help_tbl
                    sta help_tbl
                    bcc phd_pad
                    inc help_tbl+1
\ Line the descriptions up at column 11.  A name that already reaches it
\ gets a single space instead of none: *DISCONNECT is ten characters, which
\ with the leading space fills the column exactly, and without this its
\ description ran straight into the name as "DISCONNECTClose the connection".
.phd_pad            cpx #11
                    bcc phd_pad_one
                    lda #' '
                    jsr OSWRCH
                    bne phd_desc                \ always: A is a space
.phd_pad_one        lda #' '
                    jsr OSWRCH
                    inx
                    bne phd_pad
.phd_desc           ldy #0
.phd_dchar          lda (help_txt),y
                    jsr OSASCI
                    iny
                    cmp #&0D
                    bne phd_dchar
                    tya
                    clc
                    adc help_txt
                    sta help_txt
                    bcc phd_entry
                    inc help_txt+1
                    jmp phd_entry
.phd_done           rts
\ One line per command table entry, read in lockstep with it. QUPRUN and QR
\ are the same handler under ElkWiFi's two published names, so both are
\ listed and both are described.
.help_descriptions
                    equs "Run a UEF file",&0D
                    equs "Run a UEF file",&0D
                    equs "Autorun a UEF file",&0D
                    equs "Enter host BASIC",&0D
                    equs "Start the UEF filing system",&0D
                    equs "Load local UEF file",&0D
                    equs "Enable WiFi CFS",&0D
                    equs "Rewind the UEF stream",&0D
.print_help_end

include "util.asm"
include "errors.asm"
include "wicfs_errors.asm"   \ appends to the table errors.asm starts
include "serial.asm"
include "service_driver.asm"
include "net_transport.asm"   \ after service_driver.asm, which sizes its workspace
include "driver.asm"
include "wicfs.asm"
include "wicfs_messages.asm"   \ after wicfs.asm, which defines cr
include "wicfs_catalogue.asm"
include "uef.asm"
include "host_launch.asm"

rom_content_end = P%
IF WS_IN_IMAGE
ASSERT rom_content_end <= ws_base

\ ---------------------------------------------------------------------------
\ Workspace, inside the image (see machine.asm)
\ ---------------------------------------------------------------------------
\ At the top of the bank, so everything below rom_content_end is free for code.
skipto ws_base
.ws_netprt          skip &20        \ netprt: timeouts, cursor, error block
.ws_writable        equb 0          \ ws_flag: set by the probe in autorun
.ws_mux_status      equb 0          \ mux_status, unused by this ROM
skipto heap
.ws_heap            skip &100       \ heap
.ws_strbuf          skip &100       \ strbuf
ELSE
\ A real ROM keeps nothing in the image: the workspace is three pages of host
\ RAM claimed at service call 1, so the whole bank below &C000 is code.
ASSERT rom_content_end <= &C000
ENDIF

skipto &C000
.romend

\ The EPROM build is a different image from the one Pi1MHz serves - it keeps
\ no workspace in the bank and claims host RAM instead - so it is saved under
\ its own name rather than overwriting the default.
IF WS_IN_IMAGE
SAVE "1mhz-wicfs-atm.rom", atmheader, romend
SAVE "1mhz-wicfs.rom", romstart, romend
ELSE
SAVE "1mhz-wicfs-eprom.rom", romstart, romend
ENDIF
