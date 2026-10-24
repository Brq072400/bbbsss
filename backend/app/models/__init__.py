"""模型汇总导出。

统一在这里 import 所有模型，确保 Base.metadata 注册完整
（建表、关系解析、外键指向都依赖这一点）。
"""
from app.models.community import Follow, Post, PostComment, PostLike
from app.models.course import (
    Course,
    CourseCategory,
    CourseComment,
    CourseCommentLike,
    CourseFavorite,
    CourseRating,
)
from app.models.diet import DietRecord, Food
from app.models.exercise import Exercise, ExerciseCategory
from app.models.plan import (
    Plan,
    PlanCheckin,
    PlanFavorite,
    PlanItem,
    PlanReminder,
    PlanShare,
    PlanTemplate,
)
from app.models.record import WorkoutRecord, WorkoutSet
from app.models.stats import BodyMetric
from app.models.user import Admin, CheckinRecord, Notification, RealNameAuth, SmsCode, User

__all__ = [
    # user
    "User", "Admin", "CheckinRecord", "Notification", "RealNameAuth", "SmsCode",
    # plan
    "Plan", "PlanItem", "PlanTemplate", "PlanShare", "PlanFavorite", "PlanCheckin", "PlanReminder",
    # course
    "CourseCategory", "Course", "CourseFavorite", "CourseRating", "CourseComment", "CourseCommentLike",
    # exercise
    "ExerciseCategory", "Exercise",
    # record
    "WorkoutRecord", "WorkoutSet",
    # stats
    "BodyMetric",
    # community
    "Post", "PostLike", "PostComment", "Follow",
    # diet
    "Food", "DietRecord",
]
