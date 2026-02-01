import argparse
import curses
import os
from typing import List, Optional

from .colors import _hex_to_rgb, _key_to_pair_id, _rgb_to_xterm256, _load_theme
from .render import _render_json_styled, _wrap_styled_lines
from .helpers import _validate_path, _build_offsets, _human_bytes, \
                     _read_line_at, _scan_brief, _parse_row, _die
from .command import _apply_command, _prompt_command


def _viewer(stdscr: "curses._CursesWindow", path: str, theme: str) -> None:
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
    
    color_theme = _load_theme(theme)

    num_pairs = len(color_theme)
    for i, hx in enumerate(color_theme, start=1):
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
    parser.add_argument("-t", "--theme", action="store_true", help="Color theme", default="catppuccin-mocha")
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
        curses.wrapper(_viewer, path, args.theme)
    except KeyboardInterrupt:
        return
    except curses.error as e:
        _die(f"curses error: {e}", code=1)
