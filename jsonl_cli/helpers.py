import sys
import json
import os
from typing import List, Tuple

from .containers import RowData

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