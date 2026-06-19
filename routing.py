from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote, unquote


def first(query: dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key)
    return values[0] if values else default


def positive_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


def normalize_relative_path(value: str) -> str:
    value = unquote(value).replace("\\", "/").strip("/")
    if not value:
        return ""
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("非法路径")
    return pure.as_posix()


def join_rel(base: str, name: str) -> str:
    return (PurePosixPath(base) / name).as_posix() if base else PurePosixPath(name).as_posix()


def build_query(root_index: int, relative: str = "", page: int | None = None) -> str:
    parts = [f"root={root_index}"]
    if relative:
        parts.append("path=" + quote(relative))
    if page is not None:
        parts.append(f"page={page}")
    return "&".join(parts)
