import json
import curses
from typing import Any

from .containers import StyledLine

def _json_atom(v: Any) -> str:
    """
    Convert a terminal endpoint in a JSONL file to a string.
    
    Args:
        v: A terminal endpoint in the JSONL file, i.e. a value or an item in a list.
    
    Returns:
        The string corresponding to the given terminal endpoint.
    """
    return json.dumps(v, ensure_ascii=False)


def _render_json_styled(
    v: Any,
    indent: int,
    key_attr_fn,
    normal_attr: int,
    indent_delta: int,
) -> list[StyledLine]:
    """
    Recursively renders a Python object corresponding to 1 line in a JSONL file.
    
    Args:
        v:            The Python object to render.
        indent:       The base indent to use.
        key_attr_fn:  Function that maps strings to curses bitmasks. Applies to keys.
        normal_attr:  Function that maps strings to curses bitmasks. Applies to everything else.
        indent_delta: Amount to indent each line.
    
    Returns:
        The rendered Python object in a list of StyledLines.
    """
    lines: list[StyledLine] = []

    is_root = (indent == 0)
    
    sp = " " * indent
    sp_child = " " * (indent + indent_delta)

    if isinstance(v, dict):
        if is_root:
            lines.append([(sp + "{", normal_attr)])
        items = list(v.items())
        for i, (k, val) in enumerate(items):
            last = (i == len(items) - 1)

            k_str = json.dumps(k, ensure_ascii=False)
            k_attr = key_attr_fn(str(k))

            if isinstance(val, (dict, list)):
                opener = "{" if isinstance(val, dict) else "["
                line: StyledLine = [
                    (sp_child, normal_attr),
                    (k_str, k_attr),
                    (": " + opener, normal_attr),
                ]
                lines.append(line)
                lines.extend(_render_json_styled(val, indent + indent_delta, key_attr_fn, normal_attr, indent_delta))
                closer = "}" if isinstance(val, dict) else "]"
                tail = closer + ("" if last else ",")
                lines.append([(sp_child + tail, normal_attr)]) if lines[-1] else lines.append([(sp_child + tail, normal_attr)])
            else:
                atom = _json_atom(val)
                comma = "" if last else ","
                lines.append([
                    (sp_child, normal_attr),
                    (k_str, k_attr),
                    (": " + atom + comma, normal_attr),
                ])
        if is_root:
            lines.append([(sp + "}", normal_attr)])
        
        return lines

    if isinstance(v, list):
        if is_root:
            lines.append([(sp + "[", normal_attr)])
        
        for i, item in enumerate(v):
            last = (i == len(v) - 1)
            if isinstance(item, (dict, list)):
                opener = "{" if isinstance(item, dict) else "["
                lines.append([(sp_child + opener, normal_attr)])
                lines.extend(_render_json_styled(item, indent + indent_delta, key_attr_fn, normal_attr, indent_delta))
                closer = "}" if isinstance(item, dict) else "]"
                tail = closer + ("" if last else ",")
                lines.append([(sp_child + tail, normal_attr)]) if lines[-1] else lines.append([(sp_child + tail, normal_attr)])
            else:
                atom = _json_atom(item)
                comma = "" if last else ","
                lines.append([(sp_child + atom + comma, normal_attr)])
        
        if is_root:
            lines.append([(sp + "]", normal_attr)])
        
        return lines

    lines.append([(sp + _json_atom(v), normal_attr)])
    
    return lines


def _wrap_styled_lines(lines: list[StyledLine], width: int) -> list[StyledLine]:
    """
    Wrap styled lines to fit window width.
    Preserves per-segment attributes and breaks only at character boundaries.
    
    Args:
        lines: List of StyledLines to wrap.
        width: Width to wrap to.
        
    Returns:
        The resulting list of StyledLines that have been wrapped.
    """
    if width <= 1:
        return lines

    out: list[StyledLine] = []

    for line in lines:
        rendered = "".join(t for t, _ in line)

        sep = rendered.find(": ")
        if sep != -1:
            align = sep + 2
        else:
            align = 0
            while align < len(rendered) and rendered[align] == " ":
                align += 1

        align = min(align, max(0, width - 1))

        cur: StyledLine = []
        cur_len = 0
        first_visual_line = True

        def _append(text: str, attr: int) -> None:
            nonlocal cur, cur_len
            if not text:
                return
            if cur and cur[-1][1] == attr:
                cur[-1] = (cur[-1][0] + text, attr)
            else:
                cur.append((text, attr))
            cur_len += len(text)

        def flush() -> None:
            nonlocal cur, cur_len, first_visual_line
            out.append(cur if cur else [("", curses.A_NORMAL)])
            cur = []
            cur_len = 0
            first_visual_line = False

            if align > 0:
                _append(" " * align, curses.A_NORMAL)

        for text, attr in line:
            if not text:
                continue

            i = 0
            while i < len(text):
                space = width - cur_len
                if space <= 0:
                    flush()
                    space = width - cur_len

                chunk = text[i:i + space]
                i += len(chunk)

                _append(chunk, attr)

                if cur_len >= width:
                    flush()

        out.append(cur if cur else [("", curses.A_NORMAL)])

    return out