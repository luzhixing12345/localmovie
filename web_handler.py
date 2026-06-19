from __future__ import annotations

import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlparse

from app_config import AppConfig
from html_utils import escape
from media import CHUNK_SIZE, file_size, is_video, list_directory, parse_range
from routing import build_query, first, join_rel, normalize_relative_path, positive_int
from subtitles import find_subtitle, srt_to_vtt
from templates import (
    render_breadcrumb,
    render_browse,
    render_index,
    render_page,
    render_pager,
    render_row,
    render_subtitle_track,
    render_watch,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def make_app_handler(config: AppConfig):
    class LocalMovieHandler(BaseHTTPRequestHandler):
        server_version = "LocalMovie/1.0"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            routes = {
                "/": self.handle_index,
                "/browse": self.handle_browse,
                "/watch": self.handle_watch,
                "/video": self.handle_video,
                "/subtitle": self.handle_subtitle,
                "/style.css": self.handle_legacy_css,
            }
            handler = routes.get(parsed.path)
            if handler is not None:
                handler(parse_qs(parsed.query))
                return
            if parsed.path.startswith("/static/"):
                self.handle_static(parsed.path)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def log_message(self, format: str, *args: object) -> None:
            sys.stderr.write(
                "%s - - [%s] %s\n"
                % (self.client_address[0], self.log_date_time_string(), format % args)
            )

        def handle_index(self, query: dict[str, list[str]]) -> None:
            rows = []
            for index, root in enumerate(config.directories):
                exists_label = "" if root.exists() and root.is_dir() else "（目录不存在）"
                rows.append(
                    render_row(
                        escape(root.name or str(root)),
                        f"/browse?root={index}",
                        escape(str(root)) + exists_label,
                        "folder",
                    )
                )
            self.send_html(escape("本地视频"), render_index("".join(rows)))

        def handle_browse(self, query: dict[str, list[str]]) -> None:
            try:
                root_index, relative, current = self.resolve_query_path(query, allow_file=False)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Bad request")
                return

            if not current.exists() or not current.is_dir():
                self.send_error(HTTPStatus.NOT_FOUND, "Directory not found")
                return

            page = positive_int(first(query, "page", "1"), 1)
            directories, videos = list_directory(current)
            videos = [path for path in videos if is_video(path, config.extensions)]
            entries = sorted(
                [("folder", path) for path in directories]
                + [("video", path) for path in videos],
                key=lambda item: item[1].name.casefold(),
            )
            start = (page - 1) * config.videos_per_page
            end = start + config.videos_per_page
            page_entries = entries[start:end]
            total_pages = max(
                1, (len(entries) + config.videos_per_page - 1) // config.videos_per_page
            )

            root = config.directories[root_index]
            breadcrumb = render_breadcrumb(root_index, relative)
            rows = []
            if relative:
                parent_rel = str(PurePosixPath(relative).parent)
                if parent_rel == ".":
                    parent_rel = ""
                rows.append(
                    render_row(
                        "..",
                        "/browse?" + build_query(root_index, parent_rel),
                        "返回上级",
                        "up",
                    )
                )

            for kind, path in page_entries:
                if kind == "folder":
                    rows.append(
                        render_row(
                            escape(path.name),
                            "/browse?"
                            + build_query(root_index, join_rel(relative, path.name)),
                            escape(str(path)),
                            "folder",
                        )
                    )
                else:
                    rows.append(
                        render_row(
                            escape(path.name),
                            "/watch?"
                            + build_query(root_index, join_rel(relative, path.name)),
                            file_size(path),
                            "video",
                        )
                    )
            pager = render_pager(root_index, relative, page, total_pages)
            empty = (
                '<div class="empty">这个目录里没有可播放的视频。</div>'
                if not rows
                else ""
            )

            body = render_browse(
                "/",
                escape(current.name or str(root)),
                breadcrumb,
                "".join(rows),
                pager,
                empty,
            )
            self.send_html(escape(root.name or str(root)), body)

        def handle_watch(self, query: dict[str, list[str]]) -> None:
            try:
                root_index, relative, current = self.resolve_query_path(query, allow_file=True)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Bad request")
                return

            if not is_video(current, config.extensions):
                self.send_error(HTTPStatus.NOT_FOUND, "Video not found")
                return

            parent_rel = str(PurePosixPath(relative).parent)
            if parent_rel == ".":
                parent_rel = ""
            video_url = "/video?" + build_query(root_index, relative)
            browse_url = "/browse?" + build_query(root_index, parent_rel)
            subtitle = find_subtitle(current)
            tracks = (
                render_subtitle_track("/subtitle?" + build_query(root_index, relative))
                if subtitle
                else ""
            )
            body = render_watch(
                browse_url,
                escape(current.name),
                escape(str(current)),
                video_url,
                tracks,
            )
            self.send_html(escape(current.name), body)

        def handle_video(self, query: dict[str, list[str]]) -> None:
            try:
                _, _, current = self.resolve_query_path(query, allow_file=True)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Bad request")
                return

            if not is_video(current, config.extensions):
                self.send_error(HTTPStatus.NOT_FOUND, "Video not found")
                return

            self.stream_file(current)

        def handle_subtitle(self, query: dict[str, list[str]]) -> None:
            try:
                _, _, current = self.resolve_query_path(query, allow_file=True)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Bad request")
                return

            if not is_video(current, config.extensions):
                self.send_error(HTTPStatus.NOT_FOUND, "Video not found")
                return

            subtitle = find_subtitle(current)
            if subtitle is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Subtitle not found")
                return

            payload = srt_to_vtt(subtitle).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/vtt; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def handle_legacy_css(self, query: dict[str, list[str]]) -> None:
            self.serve_static_file(STATIC_DIR / "style.css", "text/css; charset=utf-8")

        def handle_static(self, request_path: str) -> None:
            relative = request_path.removeprefix("/static/").replace("\\", "/")
            if not relative or "/" in relative or relative in {".", ".."}:
                self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
                return
            self.serve_static_file(STATIC_DIR / relative)

        def serve_static_file(
            self, path: Path, content_type: str | None = None
        ) -> None:
            try:
                resolved = path.resolve()
                resolved.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
                return

            if not resolved.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
                return

            payload = resolved.read_bytes()
            content_type = (
                content_type
                or mimetypes.guess_type(resolved.name)[0]
                or "application/octet-stream"
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def resolve_query_path(
            self, query: dict[str, list[str]], allow_file: bool
        ) -> tuple[int, str, Path]:
            root_value = first(query, "root", "")
            if not root_value.isdigit():
                raise ValueError("缺少有效 root 参数")
            root_index = int(root_value)
            if root_index < 0 or root_index >= len(config.directories):
                raise ValueError("root 参数超出范围")

            relative = normalize_relative_path(first(query, "path", ""))
            root = config.directories[root_index]
            current = (
                (root / Path(*PurePosixPath(relative).parts)).resolve()
                if relative
                else root
            )

            try:
                current.relative_to(root)
            except ValueError as exc:
                raise ValueError("非法路径") from exc

            if not allow_file and current.exists() and not current.is_dir():
                raise ValueError("路径不是目录")
            return root_index, relative, current

        def stream_file(self, path: Path) -> None:
            total_size = path.stat().st_size
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            range_header = self.headers.get("Range")
            start = 0
            end = total_size - 1
            status = HTTPStatus.OK

            if range_header:
                try:
                    start, end = parse_range(range_header, total_size)
                    status = HTTPStatus.PARTIAL_CONTENT
                except ValueError:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{total_size}")
                    self.end_headers()
                    return

            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
            self.end_headers()

            with path.open("rb") as file:
                file.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = file.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                        return
                    remaining -= len(chunk)

        def send_html(self, title: str, body: str) -> None:
            payload = render_page(title, body).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return LocalMovieHandler
