from __future__ import annotations

import re
import socket
from pathlib import Path


CHUNK_SIZE = 1024 * 1024


def display_host(host: str) -> str:
    if host not in {"", "0.0.0.0", "::"}:
        return host

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def is_video(path: Path, extensions: frozenset[str]) -> bool:
    return path.is_file() and path.suffix.lower() in extensions


def natural_sort_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", value)
    )


def filename_sort_key(
    value: str,
) -> tuple[int, tuple[tuple[int, int | str], ...]]:
    return -value.count("★"), natural_sort_key(value)


def list_directory(path: Path) -> tuple[list[Path], list[Path]]:
    directories: list[Path] = []
    files: list[Path] = []
    try:
        for child in path.iterdir():
            if child.is_dir():
                directories.append(child)
            elif child.is_file():
                files.append(child)
    except OSError:
        return [], []

    key = lambda item: filename_sort_key(item.name)
    return sorted(directories, key=key), sorted(files, key=key)


def file_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def parse_range(range_header: str, total_size: int) -> tuple[int, int]:
    if not range_header.startswith("bytes="):
        raise ValueError("Unsupported range")
    value = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
    if "-" not in value:
        raise ValueError("Invalid range")

    start_text, end_text = value.split("-", 1)
    if start_text == "":
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("Invalid suffix range")
        start = max(0, total_size - suffix_length)
        end = total_size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else total_size - 1

    if start < 0 or end < start or start >= total_size:
        raise ValueError("Range out of bounds")
    return start, min(end, total_size - 1)
