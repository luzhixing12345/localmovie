from __future__ import annotations

import re
from pathlib import Path


SUBTITLE_SUFFIXES = (".srt",)
TIMESTAMP_RE = re.compile(
    r"^(\d{1,2}:\d{2}:\d{2}),(\d{3})\s+-->\s+"
    r"(\d{1,2}:\d{2}:\d{2}),(\d{3})(.*)$"
)


def find_subtitle(video_path: Path) -> Path | None:
    for suffix in SUBTITLE_SUFFIXES:
        subtitle = video_path.with_suffix(suffix)
        if subtitle.is_file():
            return subtitle
    return None


def srt_to_vtt(path: Path) -> str:
    content = read_subtitle_text(path)
    lines = ["WEBVTT", ""]
    for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        match = TIMESTAMP_RE.match(line)
        if match:
            line = (
                f"{match.group(1)}.{match.group(2)} --> "
                f"{match.group(3)}.{match.group(4)}{match.group(5)}"
            )
        lines.append(line)
    return "\n".join(lines)


def read_subtitle_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
