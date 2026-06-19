from __future__ import annotations

import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

from app_config import CONFIG_FILE, load_config
from media import display_host
from web_handler import make_app_handler


def main() -> None:
    config = load_config(Path(CONFIG_FILE))
    missing = [
        str(path) for path in config.directories if not path.exists() or not path.is_dir()
    ]
    if missing:
        print("以下视频目录不存在或不可访问：", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)

    # if config.generate_thumbnails:
    #     print("提示：当前版本不生成缩略图，会直接按目录和视频文件展示。")

    handler = make_app_handler(config)
    server = ThreadingHTTPServer((config.host, config.port), handler)
    local_url = f"http://127.0.0.1:{config.port}/"
    lan_url = f"http://{display_host(config.host)}:{config.port}/"
    print(f"  本机访问:   {local_url}")
    print(f"  局域网访问: {lan_url}")
    print("\n  按 Ctrl+C 停止服务")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
