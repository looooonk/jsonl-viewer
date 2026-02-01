import zlib
import json
from pathlib import Path
from typing import List


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


def _load_theme(theme: str) -> List[str]:
    path = Path(__file__).parent / "themes" / f"{theme}.json"
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["key-colors"]