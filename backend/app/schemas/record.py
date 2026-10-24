"""运动记录模块的请求 / 响应模型（Pydantic v2）。

约定：
- 入参统一叫 XxxRequest，出参统一叫 XxxOut；
- 所有出参都开启 from_attributes，方便直接用 ORM 对象做校验；
- 日期字段用 datetime.date，与模型里的 Date 列一一对应。
"""
from __future__ import annotations

import datetime as dt  # 日期注解统一写 dt.date：pydantic 2.x 里"字段名叫 date"会和类型 date 撞车
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# 允许的运动类型（与 app/models/record.py 中 workout_type 的注释保持一致）
WORKOUT_TYPES: tuple[str, ...] = ("strength", "cardio", "stretch", "hiit", "yoga")

# 运动类型的中文名，统计接口返回给前端直接展示
WORKOUT_TYPE_NAMES: dict[str, str] = {
    "strength": "力量训练",
    "cardio": "有氧运动",
    "stretch": "拉伸放松",
    "hiit": "HIIT 高强度",
    "yoga": "瑜伽",
}


# ---------------------------------------------------------------- 动作明细
class WorkoutSetRequest(BaseModel):
    """创建/修改训练记录时提交的单组明细。"""

    exercise_id: int | None = Field(default=None, description="动作库ID（可空，自由填写动作名时不传）")
    exercise_name: str | None = Field(default=None, max_length=100, description="动作名称（没有 exercise_id 时必填）")
    set_index: int = Field(default=1, ge=1, le=100, description="第几组")
    weight: float = Field(default=0, ge=0, le=1000, description="重量kg，自重动作填 0")
    reps: int = Field(default=0, ge=0, le=1000, description="次数，有氧动作可填 0")
    duration_sec: int | None = Field(default=None, ge=0, le=86400, description="有氧/静力动作时长(秒)")
    distance_km: float | None = Field(default=None, ge=0, le=1000, description="跑步距离(公里)")
    note: str | None = Field(default=None, max_length=200, description="备注")


class WorkoutSetOut(BaseModel):
    """单组明细（响应）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="明细ID")
    exercise_id: int | None = Field(default=None, description="动作库ID")
    exercise_name: str | None = Field(default=None, description="动作名称快照")
    sort_order: int = Field(default=1, description="动作顺序")
    set_index: int = Field(default=1, description="第几组")
    weight: float = Field(default=0, description="重量kg")
    reps: int = Field(default=0, description="次数")
    duration_sec: int | None = Field(default=None, description="时长(秒)")
    distance_km: float | None = Field(default=None, description="距离(公里)")
    note: str | None = Field(default=None, description="备注")


class WorkoutExerciseGroupOut(BaseModel):
    """详情页里按动作分组后的明细（同一个动作的若干组合并）。"""

    exercise_id: int | None = Field(default=None, description="动作库ID")
    exercise_name: str | None = Field(default=None, description="动作名称快照")
    set_count: int = Field(default=0, description="该动作的组数")
    total_reps: int = Field(default=0, description="该动作总次数")
    total_volume_kg: float = Field(default=0, description="该动作总容量（重量×次数之和）")
    sets: list[WorkoutSetOut] = Field(default_factory=list, description="该动作的每组明细")


# ---------------------------------------------------------------- 训练记录
class WorkoutRecordRequest(BaseModel):
    """创建训练记录的入参。"""

    workout_date: dt.date | None = Field(default=None, description="训练日期，不传默认今天")
    workout_type: str = Field(default="strength", max_length=30, description="类型 strength/cardio/stretch/hiit/yoga")
    title: str | None = Field(default=None, max_length=100, description="本次训练标题")
    duration_min: int = Field(default=0, ge=0, le=1440, description="总时长(分钟)")
    calories: float = Field(default=0, ge=0, le=10000, description="消耗卡路里")
    feeling: int = Field(default=3, ge=1, le=5, description="主观强度 1-5")
    note: str | None = Field(default=None, max_length=1000, description="训练备注")
    plan_id: int | None = Field(default=None, description="关联训练计划ID")
    course_id: int | None = Field(default=None, description="关联课程ID")
    sets: list[WorkoutSetRequest] = Field(
        default_factory=list, max_length=200, description="动作明细列表，可为空（例如只记录有氧时长）"
    )


class WorkoutRecordUpdateRequest(BaseModel):
    """修改训练记录的入参：只改传上来的字段，sets 传了就整体替换。"""

    workout_date: dt.date | None = Field(default=None, description="训练日期")
    workout_type: str | None = Field(default=None, max_length=30, description="类型 strength/cardio/stretch/hiit/yoga")
    title: str | None = Field(default=None, max_length=100, description="本次训练标题")
    duration_min: int | None = Field(default=None, ge=0, le=1440, description="总时长(分钟)")
    calories: float | None = Field(default=None, ge=0, le=10000, description="消耗卡路里")
    feeling: int | None = Field(default=None, ge=1, le=5, description="主观强度 1-5")
    note: str | None = Field(default=None, max_length=1000, description="训练备注")
    plan_id: int | None = Field(default=None, description="关联训练计划ID")
    course_id: int | None = Field(default=None, description="关联课程ID")
    sets: list[WorkoutSetRequest] | None = Field(
        default=None, max_length=200, description="动作明细列表；传了（含空数组）就整体替换，不传表示不改"
    )


class WorkoutRecordBriefOut(BaseModel):
    """列表项：训练记录摘要，不带明细但带动作数量。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="记录ID")
    workout_date: dt.date = Field(description="训练日期")
    workout_type: str = Field(description="类型")
    workout_type_text: str | None = Field(default=None, description="类型中文名")
    title: str | None = Field(default=None, description="标题")
    duration_min: int = Field(default=0, description="总时长(分钟)")
    calories: float = Field(default=0, description="消耗卡路里")
    feeling: int = Field(default=3, description="主观强度 1-5")
    note: str | None = Field(default=None, description="备注")
    plan_id: int | None = Field(default=None, description="关联计划ID")
    course_id: int | None = Field(default=None, description="关联课程ID")
    exercise_count: int = Field(default=0, description="动作数量（去重后）")
    set_count: int = Field(default=0, description="总组数")
    created_at: datetime | None = Field(default=None, description="创建时间")


class WorkoutRecordOut(WorkoutRecordBriefOut):
    """训练记录出参（含全部明细，列表/创建/修改都用它）。"""

    sets: list[WorkoutSetOut] = Field(default_factory=list, description="动作明细")


class WorkoutRecordDetailOut(WorkoutRecordOut):
    """训练记录详情：在明细之外再提供按动作分组的数据。"""

    groups: list[WorkoutExerciseGroupOut] = Field(default_factory=list, description="按动作分组的明细")


# ---------------------------------------------------------------- 统计出参
class WorkoutTypeStatOut(BaseModel):
    """按运动类型统计的一组数据。"""

    workout_type: str = Field(description="运动类型")
    workout_type_text: str | None = Field(default=None, description="类型中文名")
    count: int = Field(default=0, description="训练次数")
    duration_min: int = Field(default=0, description="累计时长(分钟)")
    calories: float = Field(default=0, description="累计消耗")


class DailyWorkoutStatOut(BaseModel):
    """按天统计的训练数据（无记录的日期补 0）。"""

    date: dt.date = Field(description="日期")
    count: int = Field(default=0, description="当天训练次数")
    duration_min: int = Field(default=0, description="当天时长(分钟)")
    calories: float = Field(default=0, description="当天消耗")


class MonthlyStatisticsOut(BaseModel):
    """月度训练统计出参。"""

    year: int = Field(description="年份")
    month: int = Field(description="月份 1-12")
    days_in_month: int = Field(description="当月天数")
    total_count: int = Field(default=0, description="总训练次数")
    total_duration_min: int = Field(default=0, description="总时长(分钟)")
    total_calories: float = Field(default=0, description="总消耗(千卡)")
    avg_duration_min: float = Field(default=0, description="平均每次时长(分钟)")
    workout_types: list[WorkoutTypeStatOut] = Field(default_factory=list, description="按运动类型分组统计")
    daily: list[DailyWorkoutStatOut] = Field(default_factory=list, description="按天分布（长度=当月天数）")


class WeeklyStatItemOut(BaseModel):
    """单个 ISO 周的训练统计。"""

    week_label: str = Field(description="周标签，如 2025-W07")
    year: int = Field(description="ISO 年份")
    week: int = Field(description="ISO 周序号 1-53")
    start_date: dt.date = Field(description="周一日期")
    end_date: dt.date = Field(description="周日日期")
    count: int = Field(default=0, description="训练次数")
    duration_min: int = Field(default=0, description="累计时长(分钟)")
    calories: float = Field(default=0, description="累计消耗")
    workout_days: int = Field(default=0, description="有训练的天数")


class WeeklyStatisticsOut(BaseModel):
    """最近 N 周的训练统计出参。"""

    weeks: int = Field(description="统计周数")
    items: list[WeeklyStatItemOut] = Field(default_factory=list, description="按周从早到晚排列")


class SummaryStatisticsOut(BaseModel):
    """训练总览出参。"""

    total_count: int = Field(default=0, description="累计训练次数")
    total_duration_min: int = Field(default=0, description="累计时长(分钟)")
    total_calories: float = Field(default=0, description="累计消耗(千卡)")
    streak_days: int = Field(default=0, description="连续训练天数")
    month_count: int = Field(default=0, description="本月训练次数")
    week_count: int = Field(default=0, description="本周训练次数")
    last_workout_date: dt.date | None = Field(default=None, description="最近一次训练日期")


class TrendPointOut(BaseModel):
    """每日趋势中的一个点。"""

    date: dt.date = Field(description="日期")
    count: int = Field(default=0, description="当天训练次数")
    duration_min: int = Field(default=0, description="当天时长(分钟)")
    calories: float = Field(default=0, description="当天消耗(千卡)")


class TrendStatisticsOut(BaseModel):
    """最近 N 天每日趋势出参。"""

    days: int = Field(description="统计天数")
    start_date: dt.date = Field(description="起始日期")
    end_date: dt.date = Field(description="结束日期（今天）")
    points: list[TrendPointOut] = Field(default_factory=list, description="按日期升序，无记录的日期补 0")
