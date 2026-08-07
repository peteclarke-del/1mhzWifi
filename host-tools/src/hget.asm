INCLUDE "src/common/mos.inc"
ORG APP_START
GUARD APP_LIMIT
INCLUDE "src/common/tool_scaffold.inc"
.tool_text
    EQUS "HGET: scaffold installed; implementation pending.", 13, 0
.end
SAVE start, end, start
