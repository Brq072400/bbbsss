"""开发自检脚本：建表 + 写入种子数据 + 打印各表条数。

用法（在 backend 目录）：
    python tools/smoke_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许直接 python tools/smoke_db.py 运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal, engine, init_db  # noqa: E402
from app.services.bootstrap import ensure_default_admin, ensure_seed_data  # noqa: E402


def main() -> int:
    """建表、灌数据、统计条数，任何一步失败都返回非零退出码。"""
    print("数据库:", engine.url)
    init_db()
    ensure_default_admin()
    ensure_seed_data()

    import app.models as m  # noqa: E402

    tables = [
        ("用户", m.User), ("管理员", m.Admin), ("签到", m.CheckinRecord), ("通知", m.Notification),
        ("实名认证", m.RealNameAuth), ("验证码", m.SmsCode),
        ("计划", m.Plan), ("计划动作", m.PlanItem), ("计划模板", m.PlanTemplate),
        ("计划分享", m.PlanShare), ("计划收藏", m.PlanFavorite), ("计划打卡", m.PlanCheckin),
        ("计划提醒", m.PlanReminder),
        ("课程分类", m.CourseCategory), ("课程", m.Course), ("课程收藏", m.CourseFavorite),
        ("课程评分", m.CourseRating), ("课程评论", m.CourseComment), ("评论点赞", m.CourseCommentLike),
        ("动作分类", m.ExerciseCategory), ("动作", m.Exercise),
        ("运动记录", m.WorkoutRecord), ("组次明细", m.WorkoutSet),
        ("身体数据", m.BodyMetric),
        ("动态", m.Post), ("动态点赞", m.PostLike), ("动态评论", m.PostComment), ("关注", m.Follow),
        ("食物", m.Food), ("饮食记录", m.DietRecord),
    ]
    with SessionLocal() as db:
        total = 0
        for label, model in tables:
            n = db.scalar(select(func.count()).select_from(model)) or 0
            total += n
            print(f"  {label:<8} {model.__tablename__:<22} {n:>5} 行")
    print(f"共 {len(tables)} 张表，合计 {total} 行数据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
