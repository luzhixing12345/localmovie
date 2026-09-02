from __future__ import annotations

from pathlib import Path, PurePosixPath


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"


def load_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def render_template(template_name: str, **context: object) -> str:
    return load_template(template_name).format(**context)


def render_page(title: str, body: str) -> str:
    return render_template("base.html", title=title, body=body)


def render_index(rows: str) -> str:
    return render_template(
        "index.html",
        rows=rows or '<div class="empty">没有配置视频目录。</div>',
    )


def render_browse(
    back_url: str,
    random_url: str,
    title: str,
    breadcrumb: str,
    rows: str,
    pager: str,
    empty: str,
) -> str:
    return render_template(
        "browse.html",
        back_url=back_url,
        random_url=random_url,
        title=title,
        breadcrumb=breadcrumb,
        rows=rows,
        pager=pager,
        empty=empty,
    )


def render_favorites(rows: str) -> str:
    return render_template(
        "favorites.html",
        rows=rows
        or '<div class="panel"><div class="empty">还没有收藏视频。</div></div>',
    )


def render_favorite_group(title: str, rows: str) -> str:
    return render_template("favorite_group.html", title=title, rows=rows)


def render_watch(
    back_url: str,
    title: str,
    path: str,
    video_url: str,
    tracks: str,
    root_index: int,
    relative: str,
    is_favorite: bool,
) -> str:
    return render_template(
        "watch.html",
        back_url=back_url,
        title=title,
        path=path,
        video_url=video_url,
        tracks=tracks,
        root_index=root_index,
        relative=relative,
        favorite_class=" is-favorite" if is_favorite else "",
        favorite_icon="★" if is_favorite else "☆",
        favorite_pressed="true" if is_favorite else "false",
        favorite_label="取消收藏" if is_favorite else "收藏视频",
    )


def render_subtitle_track(subtitle_url: str) -> str:
    return render_template("subtitle_track.html", subtitle_url=subtitle_url)


def render_row(name: str, href: str, detail: str, kind: str) -> str:
    icons = {"folder": "📁", "video": "▶", "favorite": "★", "up": "↩"}
    return render_template(
        "row.html",
        icon=icons.get(kind, ""),
        icon_class=" icon--favorite" if kind == "favorite" else "",
        name=name,
        href=href,
        detail=detail,
    )


def render_breadcrumb(root_index: int, relative: str) -> str:
    from html_utils import escape
    from routing import build_query, join_rel

    parts = list(PurePosixPath(relative).parts) if relative else []
    links = [f'<a href="/browse?root={root_index}">根目录</a>']
    current = ""
    for part in parts:
        current = join_rel(current, part)
        links.append(f'<a href="/browse?{build_query(root_index, current)}">{escape(part)}</a>')
    return render_template("breadcrumb.html", links=" / ".join(links))


def render_pager(root_index: int, relative: str, page: int, total_pages: int) -> str:
    from routing import build_query

    if total_pages <= 1:
        return ""
    previous_link = (
        f'<a href="/browse?{build_query(root_index, relative, page - 1)}">上一页</a>'
        if page > 1
        else "<span>上一页</span>"
    )
    next_link = (
        f'<a href="/browse?{build_query(root_index, relative, page + 1)}">下一页</a>'
        if page < total_pages
        else "<span>下一页</span>"
    )
    return render_template(
        "pager.html",
        previous_link=previous_link,
        current=f"{page} / {total_pages}",
        next_link=next_link,
    )
