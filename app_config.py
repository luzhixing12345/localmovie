from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


CONFIG_FILE = "config.ini"


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    directories: tuple[Path, ...]
    extensions: frozenset[str]
    videos_per_page: int
    generate_thumbnails: bool


def load_config(config_path: Path) -> AppConfig:
    parser = configparser.ConfigParser()
    if not config_path.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    parser.read(config_path, encoding="utf-8")
    host = parser.get("server", "host", fallback="0.0.0.0").strip() or "0.0.0.0"
    port = parser.getint("server", "port", fallback=8455)

    raw_directories = parser.get("video", "directories", fallback="")
    directories = tuple(
        Path(item.strip()).expanduser().resolve()
        for item in raw_directories.split(",")
        if item.strip()
    )
    if not directories:
        raise ValueError("config.ini 中 [video] directories 不能为空")

    raw_extensions = parser.get(
        "video", "extensions", fallback="mp4,mkv,avi,mov,wmv,flv,webm,m4v"
    )
    extensions = frozenset(
        normalize_extension(item) for item in raw_extensions.split(",") if item.strip()
    )
    if not extensions:
        raise ValueError("config.ini 中 [video] extensions 不能为空")

    videos_per_page = max(1, parser.getint("ui", "videos_per_page", fallback=30))
    generate_thumbnails = parser.getboolean("ui", "generate_thumbnails", fallback=False)

    return AppConfig(
        host=host,
        port=port,
        directories=directories,
        extensions=extensions,
        videos_per_page=videos_per_page,
        generate_thumbnails=generate_thumbnails,
    )


def normalize_extension(value: str) -> str:
    value = value.strip().lower()
    return value if value.startswith(".") else f".{value}"
