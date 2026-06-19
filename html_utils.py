from __future__ import annotations

import html


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)
