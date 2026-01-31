import argparse
import curses
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


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


def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _wrap_lines(lines: List[str], width: int) -> List[str]:
    """
    Wrap each logical line to fit width. Keeps indentation visually.
    """
    if width <= 1:
        return lines

    out: List[str] = []
    for ln in lines:
        if len(ln) <= width:
            out.append(ln)
            continue

        indent_len = len(ln) - len(ln.lstrip(" "))
        indent = " " * indent_len
        text = ln
        
        out.append(text[:width])
        text = text[width:]

        cont_width = max(1, width - indent_len)
        while text:
            chunk = text[:cont_width]
            out.append(indent + chunk)
            text = text[cont_width:]

    return out


@dataclass
class RowData:
    ok: bool
    title: str
    body_lines: List[str]


def _parse_row(raw_line: bytes, row_idx: int) -> RowData:
    s = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
    if not s.strip():
        return RowData(ok=True, title=f"Row {row_idx+1}: (empty line)", body_lines=[""])

    try:
        obj = json.loads(s)
        pretty = _pretty_json(obj)
        lines = pretty.splitlines() if pretty else [""]
        return RowData(ok=True, title=f"Row {row_idx+1}: OK", body_lines=lines)
    except json.JSONDecodeError as e:
        msg = f"Row {row_idx+1}: INVALID JSON ({e.msg} at col {e.colno})"
        return RowData(ok=False, title=msg, body_lines=[s])


def _viewer(stdscr: "curses._CursesWindow", path: str) -> None:
    curses.curs_set(0)
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

        wrapped = _wrap_lines(row.body_lines, content_width)
        max_scroll = max(0, len(wrapped) - content_height)
        if scroll > max_scroll:
            scroll = max_scroll
        if scroll < 0:
            scroll = 0

        view = wrapped[scroll : scroll + content_height]
        for i, ln in enumerate(view):
            stdscr.addnstr(2 + i, 0, ln, content_width)

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
