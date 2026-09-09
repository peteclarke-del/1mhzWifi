\ machine.asm
\ 1MHz-WiFi ROM: machine definitions, MOS entry points and workspace layout.
\
\ Written for the 1MHz-WiFi project. This file replaces the equate header the
\ ROM inherited from ElkWiFi 0.23. Nothing here is copied from it: the MOS
\ entry addresses and the AP5 register addresses are properties of the machine
\ and of the Pi1MHz hardware, and the workspace assignments below are the ones
\ this ROM's own code needs. The values that must agree with something else are
\ marked as such, because those are the ones that cannot be moved freely.

\ ---------------------------------------------------------------------------
\ Target selection
\ ---------------------------------------------------------------------------
\ The ROM is built once and runs on both machine families. __ELECTRON__ selects
\ the code paths that differ; it is not a claim about which machine is present,
\ which is decided at run time through OSBYTE &81.

            __ELECTRON__ = 1
            __ATOM__     = 0

\ ---------------------------------------------------------------------------
\ MOS entry points (Acorn published interface)
\ ---------------------------------------------------------------------------

            osrdch = &FFE0
            osasci = &FFE3
            osnewl = &FFE7
            oswrch = &FFEE
            osbyte = &FFF4
            oscli  = &FFF7

\ ---------------------------------------------------------------------------
\ 1MHz bus / AP5 interface
\ ---------------------------------------------------------------------------
\ The service cursor at &FCA6-&FCAA and the JIM window are the whole of this
\ ROM's transport. The cartridge UART the original hardware used at &FC30 is
\ deliberately not defined here: nothing in this ROM may reach for it.

            pagereg = &FCFF         \ AP5-visible JIM page selector, write only
            pageram = &FD00         \ JIM page data window, 256 bytes

\ ---------------------------------------------------------------------------
\ Zero page
\ ---------------------------------------------------------------------------
\ &B0-&BF is the sideways-ROM scratch the MOS leaves to the active ROM, and
\ &F2/&F3 is the MOS command-line pointer. Offsets inside the &B0 block are
\ grouped by the routine that owns them; several deliberately overlap, because
\ the block is only sixteen bytes and no two overlapping users are ever live at
\ the same time.

            line = &F2              \ MOS command line pointer (OS defined)
            zp   = &B0              \ base of this ROM's zero page block

            \ General scratch. Owned by whichever routine is running; the
            \ driver saves the caller's registers here across a Pi request.
            save_a = zp+2
            save_y = zp+3
            save_x = zp+4
            pr24pad = zp+5

            \ The OSWORD &65 parameter block pointer shares save_y: the driver
            \ has finished with the saved Y by the time it needs the pointer.
            paramblok = save_y

            \ Transfer sizes and addresses.
            data_counter = zp+6
            blocksize    = zp+6
            load_addr    = zp+9

            \ Serial parameters. baudrate must share blocksize because both are
            \ fed to the same multiply-by-ten helper.
            baudrate = zp+6
            parity   = zp+9
            databits = zp+10
            stopbits = zp+11

            \ Buffer walk. buffer_ptr and data_pointer must stay adjacent so a
            \ sixteen bit pointer can be incremented across the pair.
            buffer_ptr   = zp+9
            data_pointer = zp+11
            size         = zp+11    \ search length, shares data_pointer
            needle       = zp+12    \ search string pointer, 2 bytes
            datalen      = zp+13    \ remaining data length, 2 bytes
            crc          = zp+15    \ calculated CRC, 2 bytes
            servercrc    = zp+17    \ CRC reported by the far end, 2 bytes

            \ Connection state read by the public OSWORD &65 driver.
            mux_status  = &90
            mux_channel = &91       \ five bytes

\ ---------------------------------------------------------------------------
\ Main memory workspace
\ ---------------------------------------------------------------------------
\ These are volatile scratch areas below PAGE. Each is used only for the span
\ of one command, so the overlaps below are safe and are documented where they
\ are not obvious.

            errorspace = &100       \ MOS BRK block is assembled here
            timer      = &140       \ countdown timer, 3 bytes
            time_out   = timer + 4  \ timeout setting, 1 byte
            heap       = &900       \ command parameter block
            strbuf     = &A00       \ command line parameter string

            \ Retired network printer workspace. The printer support this ROM
            \ inherited has been removed, so the bytes are free; the dynamic
            \ error block is built here rather than on the &0100 stack.
            uptvec = &222           \ user print vector
            netprt = &D90           \ 32 bytes
            uptype = &DB0
            uptsav = &DB1

            switch = &FE05
            shadow = &F4

\ The image carries the ATM header the loader expects ahead of the ROM itself.

ORG &8000-22
