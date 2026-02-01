import argparse
import curses
import json
import os
import sys
import zlib
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

MOCHA_ACCENTS_HEX = [
    "#f38ba8",
    "#eba0ac",
    "#fab387",
    "#f9e2af",
    "#a6e3a1",
    "#94e2d5",
    "#89dceb",
    "#74c7ec",
    "#89b4fa",
    "#b4befe",
    "#f5e0dc",
    "#f2cdcd",
    "#f5c2e7",
    "#cba6f7",
]

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


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    """
    Converts a hex color string into RGB values.
    
    Args:
        h: The hex string.
    
    Returns:
        A 3-tuple of the RGB values in base 16, each between 00 and FF inclusive.
    """
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_xterm256(r: int, g: int, b: int) -> int:
    """
    Maps 24-bit RGB values to xterm-256 color indices.
    Will always map the closest possible color.
    
    Args:
        r: The base 16 value for red.
        g: The base 16 value for green.
        b: The base 16 value for blue.
    
    Returns:
        The index of the corresponding xterm-256 color.
    """
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + (r - 8) // 10

    def to_6(x: int) -> int:
        return int(round(x / 255 * 5))

    rr, gg, bb = to_6(r), to_6(g), to_6(b)
    return 16 + 36 * rr + 6 * gg + bb


def _key_to_pair_id(key: str, num_pairs: int) -> int:
    """
    Maps a string to a color via hashing.
    Uses zlib.crc32() as the hash function.
    
    Args:
        key:       The string to assign a color to.
        num_pairs: The number of colors that can be assigned.
        
    Returns:
        The index in curses corresponding to that color.
        Note that index 0 in curses corresponds to the default text color, so the return value is 1-indexed.
    """
    h = zlib.crc32(key.encode("utf-8")) & 0xFFFFFFFF
    return 1 + (h % num_pairs)


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


def _die(msg: str, code: int = 2) -> None:
    """
    Raises SystemExit.
    
    Args:
        msg:  The message to display to the user.
        code: The system exit code.
    
    Raises:
        SystemExit unconditionally.
    """
    print(f"jsonl: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _human_bytes(n: int) -> str:
    """
    Converts number of bytes into a human-readable form.
    
    Args:
        n: The number of bytes to convert.
    
    Returns:
        The human-readable conversion of n bytes.
    """
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    x = float(n)
    for u in units:
        if x < 1024.0 or u == units[-1]:
            if u == "B":
                return f"{int(x)} {u}"
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{n} B"


def _validate_path(path: str) -> str:
    """
    Validates whether a path is a valid JSONL file.
    
    Args:
        path: The path to the JSONL file.
    
    Returns:
        The given path without modification.

    Raises:
        SystemExit if path is abnormal.
    """
    if not path.endswith(".jsonl"):
        _die("FILE must end with .jsonl")
    if not os.path.exists(path):
        _die(f"FILE not found: {path}")
    if not os.path.isfile(path):
        _die(f"FILE is not a regular file: {path}")
    return path


def _scan_brief(path: str) -> Tuple[int, int, List[str], int]:
    """
    Returns a summary of the given JSONL file.
    Columns are the union of keys across all JSON objects that are dicts.
    
    Args:
        path: The path to the JSONL file.
    
    Returns:
        A 4-tuple of (line_count, file_size_bytes, columns_sorted, invalid_json_lines).
    """
    st = os.stat(path)
    size = st.st_size
    line_count = 0
    invalid = 0
    cols = set()

    with open(path, "rb") as f:
        for raw in f:
            line_count += 1
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    cols.update(obj.keys())
            except json.JSONDecodeError:
                invalid += 1

    return line_count, size, sorted(cols), invalid


def _build_offsets(path: str) -> List[int]:
    """
    Builds file 0-indexed offsets for each line start.
    
    Args:
        path: The path to the JSONL file.
    
    Returns:
        A list of 0-indexed offsets of length equal to the number of lines in the JSONL file.
    """
    offsets: List[int] = []
    pos = 0
    
    offsets.append(pos)
    with open(path, "rb") as f:
        for raw in f:
            pos += len(raw)
            offsets.append(pos)
    
    return offsets


def _read_line_at(path: str, start: int, end: int) -> bytes:
    """
    Wrapper for reading lines of a file, i.e. start <= && < end
    
    Args:
        path:  The path to the JSONL file.
        start: The index of the byte to start reading.
        end:   The index of the byte right after the byte to end reading.
    
    Returns:
        A segment of bytes of the given JSONL file.
    """
    with open(path, "rb") as f:
        f.seek(start)
        return f.read(end - start)


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
        # Build the rendered plain text for alignment calculations
        rendered = "".join(t for t, _ in line)

        # Prefer aligning to value start (first occurrence of ": ")
        sep = rendered.find(": ")
        if sep != -1:
            align = sep + 2  # start of value, right after ": "
        else:
            # Fallback: align to leading indentation (spaces at start)
            align = 0
            while align < len(rendered) and rendered[align] == " ":
                align += 1

        # Never let alignment consume the full line width
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

            # Prefix continuation lines so wrapped content starts at value column
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

        # Final line for this logical line
        out.append(cur if cur else [("", curses.A_NORMAL)])

    return out


def _parse_row(raw_line: bytes, row_idx: int) -> RowData:
    """
    Parses raw bytes of a JSONL row into a RowData structure.
    
    Args:
        raw_line: Bytes of the JSONL row.
        row_idx:  0-indexed row number.
    
    Returns:
        A RowData structure corresponding to the given row bytes.
        
    Raises:
        JSONDecodeError if the row cannot be parsed.
    """
    s = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
    if not s.strip():
        return RowData(ok=True, title=f"Row {row_idx+1}: (empty line)", obj="")

    try:
        obj = json.loads(s)
        return RowData(ok=True, title=f"Row {row_idx+1}: OK", obj=obj)
    except json.JSONDecodeError as e:
        msg = f"Row {row_idx+1}: INVALID JSON ({e.msg} at col {e.colno})"
        return RowData(ok=False, title=msg, obj=None, raw_fallback=s)


def _prompt_command(stdscr: "curses._CursesWindow", prompt: str = ":") -> str | None:
    """
    Read a command from the bottom line.

    Args:
        stdscr: The curses window to display to.
        prompt: The prompt / command to read.
    
    Returns:
        The command string (without leading ':') or None if cancelled (ESC).
    """
    height, width = stdscr.getmaxyx()
    y = height - 1

    buf: list[str] = []
    pos = 0

    stdscr.move(y, 0)
    stdscr.clrtoeol()
    stdscr.addnstr(y, 0, prompt, width - 1, curses.A_REVERSE)
    stdscr.refresh()

    while True:
        ch = stdscr.get_wch()

        if ch == "\x1b":
            return None

        if ch in ("\n", "\r"):
            return "".join(buf).strip()

        if ch in (curses.KEY_BACKSPACE, "\b", "\x7f"):
            if pos > 0:
                buf.pop(pos - 1)
                pos -= 1

        elif ch == curses.KEY_LEFT:
            pos = max(0, pos - 1)
        elif ch == curses.KEY_RIGHT:
            pos = min(len(buf), pos + 1)
        elif ch == curses.KEY_HOME:
            pos = 0
        elif ch == curses.KEY_END:
            pos = len(buf)
        elif isinstance(ch, str) and ch.isprintable():
            buf.insert(pos, ch)
            pos += 1

        cmd_text = prompt + "".join(buf)
        if len(cmd_text) >= width:
            cmd_text = cmd_text[-(width - 1):]
        stdscr.move(y, 0)
        stdscr.clrtoeol()
        stdscr.addnstr(y, 0, cmd_text, width - 1, curses.A_REVERSE)

        cursor_x = min(width - 1, len(prompt) + pos)
        stdscr.move(y, cursor_x)
        stdscr.refresh()


def _apply_command(cmd: str, total_lines: int, idx: int) -> tuple[int, str | None]:
    """
    Applies a command string.
    
    Args:
        cmd:         The command inputted.
        total_lines: The number of rows in the JSONL file.
        idx:         The current index being viewed.
    
    Returns:
        A tuple (new_idx, status_message_or_None).
    """
    if not cmd:
        return idx, None

    parts = cmd.split()
    name = parts[0].lower()

    if name in ("goto", "g") and len(parts) == 2:
        try:
            n = int(parts[1])
        except ValueError:
            return idx, "goto expects an integer row number"

        if total_lines <= 0:
            return idx, "file has no rows"

        n = max(1, min(total_lines, n))
        return n - 1, None

    if name in ("q", "quit", "exit"):
        return -1, None

    return idx, f"unknown command: {cmd}"


def _viewer(stdscr: "curses._CursesWindow", path: str) -> None:
    """
    Main driver code for the curses window.
    
    Args:
        stdscr: The curses window to display to.
        path:   Path to the JSONL file.
    """
    curses.curs_set(0)
    
    status_msg: str | None = None
    
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass

    num_pairs = len(MOCHA_ACCENTS_HEX)
    for i, hx in enumerate(MOCHA_ACCENTS_HEX, start=1):
        r, g, b = _hex_to_rgb(hx)
        fg = _rgb_to_xterm256(r, g, b)
        try:
            curses.init_pair(i, fg, -1)
        except curses.error:
            pass

    def key_attr_fn(key: str) -> int:
        pid = _key_to_pair_id(key, num_pairs)
        return curses.A_BOLD | curses.color_pair(pid)

    normal_attr = curses.A_NORMAL
    
    stdscr.keypad(True)

    offsets = _build_offsets(path)
    total_lines = max(0, len(offsets) - 1)

    idx = 0
    scroll = 0
    indent_delta = 4

    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()

        if total_lines == 0:
            stdscr.addnstr(0, 0, "Empty file. Press q to quit.", width - 1)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in (ord("q"), ord("Q")):
                return
            continue

        if idx < 0:
            idx = 0
        if idx >= total_lines:
            idx = total_lines - 1

        start = offsets[idx]
        end = offsets[idx + 1]
        raw = _read_line_at(path, start, end)
        row = _parse_row(raw, idx)

        header = f"{os.path.basename(path)}  |  {idx + 1}/{total_lines}  |  ↑/↓ scroll  ←/→ row  PgUp/PgDn indent  q quit"
        stdscr.addnstr(0, 0, header, max(0, width - 1), curses.A_REVERSE)

        title = row.title
        stdscr.addnstr(1, 0, title, max(0, width - 1), curses.A_BOLD)

        content_height = max(0, height - 3)
        content_width = max(1, width - 1)

        if row.ok:
            styled_lines = _render_json_styled(row.obj, 0, key_attr_fn, normal_attr, indent_delta)
        else:
            raw = row.raw_fallback or ""
            styled_lines = [[(raw, curses.A_DIM)]]
        
        if row.ok:
            styled_lines = _render_json_styled(row.obj, 0, key_attr_fn, normal_attr, indent_delta)
        else:
            raw = row.raw_fallback or ""
            styled_lines = [[(raw, curses.A_DIM)]]

        styled_lines = _wrap_styled_lines(styled_lines, content_width)

        max_scroll = max(0, len(styled_lines) - content_height)
        if scroll > max_scroll:
            scroll = max_scroll
        if scroll < 0:
            scroll = 0

        view = styled_lines[scroll : scroll + content_height]

        for i, line in enumerate(view):
            y = 2 + i
            x = 0
            remaining = content_width
            for text, attr in line:
                if remaining <= 0:
                    break
                if not text:
                    continue
                chunk = text[:remaining]
                try:
                    stdscr.addstr(y, x, chunk, attr)
                except curses.error:
                    pass
                x += len(chunk)
                remaining -= len(chunk)


        if max_scroll > 0:
            footer = None
            if status_msg:
                footer = status_msg
            elif max_scroll > 0:
                footer = f"Lines {scroll} - {min(scroll + content_height, len(styled_lines))}"

            if footer:
                stdscr.addnstr(height - 1, 0, footer, max(0, width - 1), curses.A_DIM)


        stdscr.refresh()
        ch = stdscr.getch()

        if ch in (ord("q"), ord("Q")):
            return
        elif ch == ord(":"):
            cmd = _prompt_command(stdscr, prompt=":")
            status_msg = None
            if cmd is not None:
                new_idx, msg = _apply_command(cmd, total_lines, idx)
                if new_idx == -1:
                    return
                idx = new_idx
                scroll = 0
                status_msg = msg
            continue
        elif ch == curses.KEY_DOWN:
            scroll += 1
        elif ch == curses.KEY_UP:
            scroll -= 1
        elif ch == curses.KEY_LEFT:
            idx -= 1
            scroll = 0
        elif ch == curses.KEY_RIGHT:
            idx += 1
            scroll = 0
        elif ch in (curses.KEY_NPAGE,):
            indent_delta = max(indent_delta - 1, 1)
        elif ch in (curses.KEY_PPAGE,):
            indent_delta = min(indent_delta + 1, 8)
        elif ch == curses.KEY_RESIZE:
            pass
        else:
            pass


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="jsonl", add_help=True)
    parser.add_argument("file", metavar="FILE", help="Path to a .jsonl file")
    parser.add_argument("-b", "--brief", action="store_true", help="Show file characteristics and exit")
    args = parser.parse_args(argv)

    path = _validate_path(args.file)

    if args.brief:
        line_count, size, cols, invalid = _scan_brief(path)
        print(f"File: {path}")
        print(f"Size: {_human_bytes(size)} ({size} bytes)")
        print(f"Lines: {line_count}")
        if invalid:
            print(f"Invalid JSON lines: {invalid}")
        print("Columns:")
        if cols:
            for c in cols:
                print(f"  - {c}")
        else:
            print("  (no object keys found)")
        return

    try:
        curses.wrapper(_viewer, path)
    except KeyboardInterrupt:
        return
    except curses.error as e:
        _die(f"curses error: {e}", code=1)
