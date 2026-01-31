import argparse
import curses
import json
import os
import sys
import zlib
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

# Catppuccin Mocha accent colors
MOCHA_ACCENTS_HEX = [
    "#f5e0dc",
    "#f2cdcd",
    "#f5c2e7",
    "#cba6f7",
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
]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_xterm256(r: int, g: int, b: int) -> int:
    """
    Approximate mapping from 24-bit RGB to xterm-256 color index.
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
    # Stable across runs/platforms
    h = zlib.crc32(key.encode("utf-8")) & 0xFFFFFFFF
    return 1 + (h % num_pairs)


Segment = tuple[str, int]
StyledLine = list[Segment]


def _json_atom(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def _render_json_styled(
    v: Any,
    indent: int,
    key_attr_fn,
    normal_attr: int,
) -> list[StyledLine]:
    """
    Render JSON in a json.dumps-like layout but with styles:
    - keys styled using key_attr_fn(key_str) (should include bold+color)
    - everything else uses normal_attr
    """
    lines: list[StyledLine] = []

    sp = " " * indent
    sp2 = " " * (indent + 2)

    if isinstance(v, dict):
        lines.append([(sp + "{", normal_attr)])
        items = list(v.items())
        for i, (k, val) in enumerate(items):
            last = (i == len(items) - 1)

            k_str = json.dumps(k, ensure_ascii=False)
            k_attr = key_attr_fn(str(k))

            if isinstance(val, (dict, list)):
                opener = "{" if isinstance(val, dict) else "["
                line: StyledLine = [
                    (sp2, normal_attr),
                    (k_str, k_attr),
                    (": " + opener, normal_attr),
                ]
                lines.append(line)
                lines.extend(_render_json_styled(val, indent + 2, key_attr_fn, normal_attr))
                closer = "}" if isinstance(val, dict) else "]"
                tail = closer + ("" if last else ",")
                lines[-1].append((tail, normal_attr)) if lines[-1] else lines.append([(sp2 + tail, normal_attr)])
            else:
                atom = _json_atom(val)
                comma = "" if last else ","
                lines.append([
                    (sp2, normal_attr),
                    (k_str, k_attr),
                    (": " + atom + comma, normal_attr),
                ])

        lines.append([(sp + "}", normal_attr)])
        return lines

    if isinstance(v, list):
        lines.append([(sp + "[", normal_attr)])
        for i, item in enumerate(v):
            last = (i == len(v) - 1)
            if isinstance(item, (dict, list)):
                opener = "{" if isinstance(item, dict) else "["
                lines.append([(sp2 + opener, normal_attr)])
                lines.extend(_render_json_styled(item, indent + 2, key_attr_fn, normal_attr))
                closer = "}" if isinstance(item, dict) else "]"
                tail = closer + ("" if last else ",")
                lines[-1].append((tail, normal_attr)) if lines[-1] else lines.append([(sp2 + tail, normal_attr)])
            else:
                atom = _json_atom(item)
                comma = "" if last else ","
                lines.append([(sp2 + atom + comma, normal_attr)])
        lines.append([(sp + "]", normal_attr)])
        return lines

    lines.append([(sp + _json_atom(v), normal_attr)])
    return lines

def _die(msg: str, code: int = 2) -> None:
    print(f"jsonl: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _human_bytes(n: int) -> str:
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
    if not path.endswith(".jsonl"):
        _die("FILE must end with .jsonl")
    if not os.path.exists(path):
        _die(f"FILE not found: {path}")
    if not os.path.isfile(path):
        _die(f"FILE is not a regular file: {path}")
    return path


def _scan_brief(path: str) -> Tuple[int, int, List[str], int]:
    """
    Returns: (line_count, file_size_bytes, columns_sorted, invalid_json_lines)
    Columns are the union of keys across all JSON objects that are dicts.
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
    Build file offsets for each line start so we can seek to any row.
    offsets[i] is the byte position where line i starts (0-indexed).
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
    with open(path, "rb") as f:
        f.seek(start)
        return f.read(end - start)


def _wrap_styled_lines(lines: list[list[tuple[str, int]]], width: int) -> list[list[tuple[str, int]]]:
    """
    Wrap styled lines (list of (text, attr) segments) to fit `width`.
    Preserves per-segment attributes. Breaks only at character boundaries.
    """
    if width <= 1:
        return lines

    out: list[list[tuple[str, int]]] = []

    for line in lines:
        cur: list[tuple[str, int]] = []
        cur_len = 0

        def flush() -> None:
            nonlocal cur, cur_len
            out.append(cur if cur else [("", curses.A_NORMAL)])
            cur = []
            cur_len = 0

        for text, attr in line:
            if not text:
                continue

            i = 0
            while i < len(text):
                space = width - cur_len
                if space <= 0:
                    flush()
                    space = width

                chunk = text[i:i + space]
                i += len(chunk)

                if cur and cur[-1][1] == attr:
                    cur[-1] = (cur[-1][0] + chunk, attr)
                else:
                    cur.append((chunk, attr))

                cur_len += len(chunk)

                if cur_len >= width:
                    flush()

        flush()

    return out


@dataclass
class RowData:
    ok: bool
    title: str
    obj: Any = None
    raw_fallback: Optional[str] = None


def _parse_row(raw_line: bytes, row_idx: int) -> RowData:
    s = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
    if not s.strip():
        return RowData(ok=True, title=f"Row {row_idx+1}: (empty line)", obj="")

    try:
        obj = json.loads(s)
        return RowData(ok=True, title=f"Row {row_idx+1}: OK", obj=obj)
    except json.JSONDecodeError as e:
        msg = f"Row {row_idx+1}: INVALID JSON ({e.msg} at col {e.colno})"
        return RowData(ok=False, title=msg, obj=None, raw_fallback=s)


def _viewer(stdscr: "curses._CursesWindow", path: str) -> None:
    curses.curs_set(0)
    
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

        header = f"{os.path.basename(path)}  |  {idx+1}/{total_lines}  |  ↑/↓ row  PgUp/PgDn scroll  q quit"
        stdscr.addnstr(0, 0, header, max(0, width - 1), curses.A_REVERSE)

        title = row.title
        stdscr.addnstr(1, 0, title, max(0, width - 1), curses.A_BOLD)

        content_height = max(0, height - 3)
        content_width = max(1, width - 1)

        if row.ok:
            styled_lines = _render_json_styled(row.obj, 0, key_attr_fn, normal_attr)
        else:
            raw = row.raw_fallback or ""
            styled_lines = [[(raw, curses.A_DIM)]]
        
        if row.ok:
            styled_lines = _render_json_styled(row.obj, 0, key_attr_fn, normal_attr)
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
            footer = f"Scroll: {scroll}/{max_scroll}"
            stdscr.addnstr(height - 1, 0, footer, max(0, width - 1), curses.A_DIM)

        stdscr.refresh()
        ch = stdscr.getch()

        if ch in (ord("q"), ord("Q")):
            return
        elif ch == curses.KEY_DOWN:
            idx += 1
            scroll = 0
        elif ch == curses.KEY_UP:
            idx -= 1
            scroll = 0
        elif ch in (curses.KEY_NPAGE,):
            scroll += max(1, content_height)
        elif ch in (curses.KEY_PPAGE,):
            scroll -= max(1, content_height)
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
