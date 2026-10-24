"""代码行数统计（排除依赖库、构建产物、数据库文件）。

用法（在项目根目录）：python tools/count_lines.py
"""
from __future__ import annotations

import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"node_modules", "dist", ".git", ".venv", ".libs", "wheels", ".tmp", "uploads", "__pycache__", ".vite"}
EXCLUDE_FILES = {"package-lock.json", "fittrack.db"}

BACKEND_EXT = {".py", ".sql"}
FRONTEND_EXT = {".vue", ".js", ".css", ".html"}


def walk(exts: set[str]) -> tuple[int, int, Counter]:
    """返回 (文件数, 行数, 按扩展名分布)。"""
    files = 0
    lines = 0
    dist: Counter = Counter()
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES or path.name.startswith("."):
            continue
        if path.suffix.lower() not in exts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        n = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        # 去掉纯空行，统计"有效代码行"
        effective = sum(1 for line in text.splitlines() if line.strip())
        files += 1
        lines += n
        dist[f"{path.suffix.lower()} 行(有效)"] += effective
        dist[f"{path.suffix.lower()} 行(含空行)"] += n
    return files, lines, dist


def main() -> int:
    """分别统计后端与前端，并打印汇总。"""
    # 后端：backend/ 下的 py + sql
    be_files = be_lines = 0
    be_eff = 0
    for path in (ROOT / "backend").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in BACKEND_EXT:
            continue
        if any(p in EXCLUDE_DIRS for p in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        be_files += 1
        be_lines += text.count("\n")
        be_eff += sum(1 for line in text.splitlines() if line.strip())

    # 前端
    fe_files = fe_lines = fe_eff = 0
    for path in (ROOT / "frontend").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in FRONTEND_EXT:
            continue
        if any(p in EXCLUDE_DIRS for p in path.parts) or path.name in EXCLUDE_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        fe_files += 1
        fe_lines += text.count("\n")
        fe_eff += sum(1 for line in text.splitlines() if line.strip())

    print("=" * 58)
    print(f"后端（Python + SQL）  {be_files:>3} 个文件   {be_lines:>6} 行（有效 {be_eff} 行）")
    print(f"前端（Vue/JS/CSS/HTML）{fe_files:>3} 个文件   {fe_lines:>6} 行（有效 {fe_eff} 行）")
    print(f"合计                  {be_files + fe_files:>3} 个文件   {be_lines + fe_lines:>6} 行（有效 {be_eff + fe_eff} 行）")
    print("=" * 58)

    # 按模块细分后端
    print("\n后端按目录：")
    groups = {
        "核心层 core": "backend/app/core",
        "数据模型 models": "backend/app/models",
        "出入参 schemas": "backend/app/schemas",
        "路由 api/v1": "backend/app/api/v1",
        "服务 services": "backend/app/services",
        "建表/数据 sql": "backend/sql",
        "工具脚本 tools": "backend/tools",
    }
    for label, sub in groups.items():
        base = ROOT / sub
        n = 0
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in BACKEND_EXT:
                n += path.read_text(encoding="utf-8", errors="ignore").count("\n")
        print(f"  {label:<18} {n:>6} 行")

    print("\n前端按目录：")
    for label, sub in {"页面 views": "frontend/src/views", "接口 api": "frontend/src/api",
                       "布局/组件": "frontend/src/layouts", "路由/状态/样式": "frontend/src/router"}.items():
        base = ROOT / sub
        n = 0
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in FRONTEND_EXT:
                n += path.read_text(encoding="utf-8", errors="ignore").count("\n")
        print(f"  {label:<18} {n:>6} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
