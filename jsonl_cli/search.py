from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .helpers import _parse_row, _read_line_at


@dataclass(frozen=True)
class SearchSpec:
    query: str
    paths: tuple[str, ...] = ()
    case_sensitive: bool = False
    regex: bool = False

    def label(self) -> str:
        scope = ",".join(self.paths) if self.paths else "all fields"
        return f"{scope}: {self.query}"


@dataclass(frozen=True)
class SearchHit:
    idx: int
    wrapped: bool


_PATHS_RE = re.compile(r"^([A-Za-z0-9_.*\[\]-]+(?:,[A-Za-z0-9_.*\[\]-]+)*):(.*)$")


def _parse_search_spec(raw: str) -> tuple[SearchSpec | None, str | None]:
    text = raw.strip()
    if not text:
        return None, "find expects a search string"

    case_sensitive = False
    regex = False

    while True:
        if text.startswith("-c "):
            case_sensitive = True
            text = text[3:].lstrip()
        elif text.startswith("-r "):
            regex = True
            text = text[3:].lstrip()
        else:
            break

    paths: tuple[str, ...] = ()
    match = _PATHS_RE.match(text)
    if match:
        paths = tuple(p for p in match.group(1).split(",") if p)
        text = match.group(2).strip()

    query = _unquote(text)
    if not query:
        return None, "find expects a search string"

    if regex:
        try:
            re.compile(query)
        except re.error as e:
            return None, f"invalid regex: {e.msg}"

    return SearchSpec(query, paths, case_sensitive, regex), None


def _find_next(
    path: str,
    offsets: list[int],
    total_lines: int,
    idx: int,
    spec: SearchSpec,
    direction: int = 1,
    include_current: bool = False,
) -> SearchHit | None:
    if total_lines <= 0:
        return None

    direction = -1 if direction < 0 else 1
    start = idx if include_current else idx + direction

    for step in range(total_lines):
        row_idx = (start + step * direction) % total_lines
        start_byte = offsets[row_idx]
        end_byte = offsets[row_idx + 1]
        row = _parse_row(_read_line_at(path, start_byte, end_byte), row_idx)
        if row.ok and _matches(row.obj, spec):
            wrapped = row_idx < idx if direction > 0 else row_idx > idx
            return SearchHit(row_idx, wrapped)

    return None


def _matches(obj: Any, spec: SearchSpec) -> bool:
    values: Iterable[Any]
    if spec.paths:
        values = (value for path in spec.paths for value in _path_values(obj, path))
    else:
        values = (obj,)

    return any(_text_matches(text, spec) for value in values for text in _search_texts(value))


def _text_matches(text: str, spec: SearchSpec) -> bool:
    if spec.regex:
        flags = 0 if spec.case_sensitive else re.IGNORECASE
        return re.search(spec.query, text, flags) is not None

    needle = spec.query if spec.case_sensitive else spec.query.casefold()
    haystack = text if spec.case_sensitive else text.casefold()
    return needle in haystack


def _search_texts(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        yield json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        for k, v in value.items():
            yield str(k)
            yield from _search_texts(v)
    elif isinstance(value, list):
        yield json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        for item in value:
            yield from _search_texts(item)
    else:
        yield str(value)


def _path_values(obj: Any, path: str) -> Iterable[Any]:
    values = [obj]
    for token in _path_tokens(path):
        next_values: list[Any] = []
        for value in values:
            next_values.extend(_descend(value, token))
        values = next_values
        if not values:
            break

    return values


def _path_tokens(path: str) -> list[str]:
    tokens: list[str] = []
    for part in path.split("."):
        if not part:
            continue
        while part.endswith("[]"):
            part = part[:-2]
            if part:
                tokens.append(part)
                part = ""
            tokens.append("*")
        if part:
            tokens.append(part)
    return tokens


def _descend(value: Any, token: str) -> list[Any]:
    if token == "*":
        if isinstance(value, dict):
            return list(value.values())
        if isinstance(value, list):
            return list(value)
        return []

    if isinstance(value, dict):
        return [value[token]] if token in value else []

    if isinstance(value, list) and token.isdigit():
        i = int(token)
        return [value[i]] if i < len(value) else []

    return []


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text
