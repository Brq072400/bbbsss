"""开发/生产启动入口。

用法：
    python run.py                 # 开发模式，热重载，端口 8000
    python run.py --port 9000     # 指定端口
    python run.py --no-reload     # 关闭热重载（生产）
"""
from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    """解析命令行参数并启动 uvicorn。"""
    parser = argparse.ArgumentParser(description="启动 FitTrack 后端")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", dest="reload", action="store_true", default=True, help="开启热重载")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="关闭热重载")
    parser.add_argument("--workers", type=int, default=1, help="worker 数量（多进程时请关闭 reload）")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload and args.workers == 1,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
