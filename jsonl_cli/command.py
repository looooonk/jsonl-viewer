import curses

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