"""v1 路由汇总。

各模块的 router 在这里统一挂载，main.py 只需 include 这一个 api_router。
"""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    community,
    courses,
    diet,
    exercises,
    plans,
    records,
    stats,
    uploads,
    users,
)

api_router = APIRouter()

# 认证与用户
api_router.include_router(auth.router)
api_router.include_router(users.router)

# 运动计划 / 课程
api_router.include_router(plans.router)
api_router.include_router(courses.router)

# 运动记录 / 动作库 / 数据统计
api_router.include_router(records.router)
api_router.include_router(exercises.router)
api_router.include_router(stats.router)

# 社区 / 饮食 / 上传
api_router.include_router(community.router)
api_router.include_router(diet.router)
api_router.include_router(uploads.router)

# 后台管理
api_router.include_router(admin.router)

__all__ = ["api_router"]
