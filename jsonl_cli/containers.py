from dataclasses import dataclass
from typing import Any, Optional

# We use this datastructure since different portions of 1 line need to have different curses bitmasks (due to colors and bolding).
Segment = tuple[str, int]  # (raw_text, curses_attribute_bitmask)
StyledLine = list[Segment] # 1 Line in the output

# A container for 1 JSONL row.
@dataclass
class RowData:
    ok: bool                            # Whether the line has been successfully parsed to JSON.
    title: str                          # The status for the row displayed at the top of the window.
    obj: Any = None                     # The parsed Python object for this JSONL row.
    raw_fallback: Optional[str] = None  # Fallback raw JSONL text for failed formatting.