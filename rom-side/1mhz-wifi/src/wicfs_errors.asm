\ wicfs_errors.asm
\ 1MHz-WiCFS: the filing system's entry in the shared MOS error table.
\
\ The table in errors.asm is indexed by an entry's offset from error_table, so
\ entries must be contiguous. This file is included immediately after it, and
\ only by the filing system ROM, so the network ROM does not carry a message
\ for a condition it can never report.

.error_wicfs_state      equs "WiCFS state invalid",&0D
