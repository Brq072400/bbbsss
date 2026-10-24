"""生成 MySQL 建表语句与初始化数据 SQL。

用法（在 backend 目录）：
    python tools/gen_sql.py            # 生成 sql/schema_mysql.sql 与 sql/seed_data.sql

原理：直接读取 SQLAlchemy 模型的 metadata，用 MySQL 方言编译，保证
生成出来的 DDL 与代码里的模型永远一致。
"""
from __future__ import annotations

import re  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects import mysql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

import app.models  # noqa: F401,E402  注册所有模型
from app.core.base import Base  # noqa: E402
from app.services.bootstrap import (  # noqa: E402
    COURSE_CATEGORIES,
    COURSES,
    EXERCISE_CATEGORIES,
    EXERCISES,
    FOODS,
    PLAN_TEMPLATES,
)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def _q(value) -> str:
    """把 Python 值转成 SQL 字面量。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{text}'"


def _fix_column_order(ddl: str) -> str:
    """修正 MySQL 列属性顺序：AUTO_INCREMENT 必须出现在 COMMENT 之前。

    SQLAlchemy 生成的顺序是 `... NOT NULL COMMENT '...' AUTO_INCREMENT`，
    MySQL 会因此报语法错误，这里重排一下。
    """
    out_lines: list[str] = []
    for line in ddl.split("\n"):
        if "AUTO_INCREMENT" in line:
            line = line.replace(" AUTO_INCREMENT", "").replace("AUTO_INCREMENT", "")
            # 在列名与类型之后插入 AUTO_INCREMENT
            line = re.sub(r"^(\s*`?\w+`?\s+\w+(?:\([^)]*\))?)", r"\1 AUTO_INCREMENT", line, count=1)
        out_lines.append(line)
    return "\n".join(out_lines)


def gen_schema() -> str:
    """生成全部建表语句。"""
    lines = [
        "-- ============================================================",
        "-- FitTrack 健身系统 —— MySQL 8.0 建表脚本",
        "-- 由 backend/tools/gen_sql.py 从 SQLAlchemy 模型自动生成，请勿手改",
        "-- 字符集统一 utf8mb4，引擎 InnoDB",
        "-- ============================================================",
        "",
        "CREATE DATABASE IF NOT EXISTS `fittrack` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "USE `fittrack`;",
        "",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
    ]
    dialect = mysql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
        ddl = _fix_column_order(ddl)
        ddl = ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
        # 追加字符集与注释
        if not ddl.rstrip().endswith(";"):
            ddl += ";"
        ddl = ddl.rstrip(";") + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
        comment = (table.comment or "").replace("'", "''")
        lines.append(f"-- {comment or table.name}")
        lines.append(ddl)
        for index in table.indexes:
            lines.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
        lines.append("")
    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    lines.append("")
    return "\n".join(lines)


def gen_seed() -> str:
    """生成初始化数据（管理员、动作库、课程、食物、计划模板）。"""
    from app.core.config import settings
    from app.core.security import hash_password

    out: list[str] = [
        "-- ============================================================",
        "-- FitTrack 初始化数据（管理员 / 动作库 / 课程 / 食物库 / 计划模板）",
        "-- 与应用首次启动时写入的种子数据一致",
        "-- 默认管理员：%s / %s （请登录后立即修改密码）" % (settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD),
        "-- ============================================================",
        "",
        "USE `fittrack`;",
        "SET NAMES utf8mb4;",
        "",
        "-- 管理员",
        f"INSERT INTO `admins` (`username`, `password_hash`, `real_name`, `role`, `is_active`) VALUES "
        f"({_q(settings.DEFAULT_ADMIN_USERNAME)}, {_q(hash_password(settings.DEFAULT_ADMIN_PASSWORD))}, '超级管理员', 'super', 1);",
        "",
    ]

    # 动作分类
    out.append("-- 动作分类")
    for i, c in enumerate(EXERCISE_CATEGORIES, start=1):
        out.append(
            "INSERT INTO `exercise_categories` (`id`, `name`, `slug`, `body_part`, `sort_order`) VALUES "
            f"({i}, {_q(c['name'])}, {_q(c['slug'])}, {_q(c['body_part'])}, {c['sort_order']});"
        )
    out.append("")

    # 动作
    cat_id = {c["slug"]: i for i, c in enumerate(EXERCISE_CATEGORIES, start=1)}
    out.append("-- 动作库")
    for e in EXERCISES:
        out.append(
            "INSERT INTO `exercises` (`category_id`, `name`, `name_en`, `equipment`, `difficulty`, "
            "`description`, `key_points`, `common_mistakes`, `primary_muscles`, `secondary_muscles`, "
            "`tips`, `keywords`, `is_active`) VALUES "
            f"({cat_id[e['cat']]}, {_q(e['name'])}, {_q(e['name_en'])}, {_q(e['equipment'])}, {e['difficulty']}, "
            f"{_q(e['description'])}, {_q(e['key_points'])}, {_q(e['common_mistakes'])}, {_q(e['primary_muscles'])}, "
            f"{_q(e['secondary_muscles'])}, {_q(e['tips'])}, {_q(e['keywords'])}, 1);"
        )
    out.append("")

    # 课程分类
    out.append("-- 课程分类")
    for i, c in enumerate(COURSE_CATEGORIES, start=1):
        out.append(
            "INSERT INTO `course_categories` (`id`, `name`, `slug`, `sort_order`, `is_active`) VALUES "
            f"({i}, {_q(c['name'])}, {_q(c['slug'])}, {c['sort_order']}, 1);"
        )
    out.append("")

    # 课程
    ccat_id = {c["slug"]: i for i, c in enumerate(COURSE_CATEGORIES, start=1)}
    out.append("-- 课程")
    for idx, c in enumerate(COURSES):
        out.append(
            "INSERT INTO `courses` (`category_id`, `title`, `subtitle`, `cover`, `video_url`, `duration_min`, "
            "`calories`, `difficulty`, `equipment`, `body_parts`, `description`, `coach_name`, `sort_order`, `is_published`) VALUES "
            f"({ccat_id[c['cat']]}, {_q(c['title'])}, {_q(c['subtitle'])}, {_q('/static/covers/' + c['cat'] + '.jpg')}, "
            f"{_q('https://example.com/videos/' + c['cat'] + '-' + str(idx + 1) + '.mp4')}, {c['duration_min']}, "
            f"{c['calories']}, {c['difficulty']}, {_q(c['equipment'])}, {_q(c['body_parts'])}, {_q(c['description'])}, "
            f"{_q(c['coach_name'])}, {idx}, 1);"
        )
    out.append("")

    # 食物库
    out.append("-- 食物库（每 100g 营养）")
    for f in FOODS:
        out.append(
            "INSERT INTO `foods` (`name`, `category`, `calories`, `protein`, `fat`, `carbohydrate`, `fiber`, `is_common`) VALUES "
            f"({_q(f['name'])}, {_q(f['category'])}, {f['calories']}, {f['protein']}, {f['fat']}, "
            f"{f['carbohydrate']}, {f['fiber']}, 1);"
        )
    out.append("")

    # 计划模板
    import json

    out.append("-- 计划模板")
    for t in PLAN_TEMPLATES:
        out.append(
            "INSERT INTO `plan_templates` (`name`, `category`, `goal`, `difficulty`, `cycle_type`, `cycle_days`, "
            "`description`, `items_json`, `is_official`) VALUES "
            f"({_q(t['name'])}, {_q(t['category'])}, {_q(t['goal'])}, {t['difficulty']}, {_q(t['cycle_type'])}, "
            f"{t['cycle_days']}, {_q(t['description'])}, {_q(json.dumps(t['items'], ensure_ascii=False))}, 1);"
        )
    out.append("")
    return "\n".join(out)


def main() -> int:
    """写出两个 SQL 文件。"""
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    schema_path = SQL_DIR / "schema_mysql.sql"
    seed_path = SQL_DIR / "seed_data.sql"
    schema_path.write_text(gen_schema(), encoding="utf-8")
    seed_path.write_text(gen_seed(), encoding="utf-8")
    print(f"已生成 {schema_path} ({schema_path.stat().st_size} 字节)")
    print(f"已生成 {seed_path} ({seed_path.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
