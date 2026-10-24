"""数据统计模块的请求 / 响应模型（Pydantic v2）。

覆盖：身体数据（体重/体脂/围度）、BMI、体重/体脂趋势、
卡路里收支、训练频率、个人数据看板。
"""
from __future__ import annotations

import datetime as dt  # 日期注解统一写 dt.date：pydantic 2.x 里"字段名叫 date"会和类型 date 撞车
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- 身体数据
class BodyMetricRequest(BaseModel):
    """记录身体数据的入参（同一用户同一天只保留一条，已存在则更新）。"""

    metric_date: dt.date | None = Field(default=None, description="记录日期，不传默认今天")
    weight: float | None = Field(default=None, gt=0, le=500, description="体重kg")
    body_fat: float | None = Field(default=None, gt=0, le=80, description="体脂率%")
    muscle_mass: float | None = Field(default=None, gt=0, le=200, description="肌肉量kg")
    waist: float | None = Field(default=None, gt=0, le=300, description="腰围cm")
    chest: float | None = Field(default=None, gt=0, le=300, description="胸围cm")
    hip: float | None = Field(default=None, gt=0, le=300, description="臀围cm")
    note: str | None = Field(default=None, max_length=200, description="备注")


class BodyMetricOut(BaseModel):
    """身体数据出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="记录ID")
    metric_date: dt.date = Field(description="记录日期")
    weight: float | None = Field(default=None, description="体重kg")
    body_fat: float | None = Field(default=None, description="体脂率%")
    muscle_mass: float | None = Field(default=None, description="肌肉量kg")
    waist: float | None = Field(default=None, description="腰围cm")
    chest: float | None = Field(default=None, description="胸围cm")
    hip: float | None = Field(default=None, description="臀围cm")
    note: str | None = Field(default=None, description="备注")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


# ---------------------------------------------------------------- BMI
class BmiOut(BaseModel):
    """BMI 计算结果出参。"""

    weight: float = Field(description="体重kg")
    height: float = Field(description="身高cm")
    bmi: float = Field(description="BMI 值，保留 1 位小数")
    level: str = Field(description="分级：偏瘦 / 正常 / 偏胖 / 肥胖")
    advice: str = Field(description="建议文案")
    target_weight: float | None = Field(default=None, description="用户资料里的目标体重kg")
    diff_to_target: float | None = Field(
        default=None, description="距离目标体重的差值(kg)：正数表示还需减重，负数表示还可以增重"
    )
    ideal_weight_min: float | None = Field(default=None, description="该身高对应的理想体重下限kg（BMI 18.5）")
    ideal_weight_max: float | None = Field(default=None, description="该身高对应的理想体重上限kg（BMI 23.9）")


class BmiRecordItemOut(BaseModel):
    """BMI 历史中的一天。"""

    date: dt.date = Field(description="记录日期")
    weight: float = Field(description="体重kg")
    bmi: float = Field(description="BMI 值")


class BmiRecordsOut(BaseModel):
    """BMI 历史出参（按日期升序）。"""

    height: float = Field(description="计算用的身高cm")
    count: int = Field(default=0, description="条数")
    items: list[BmiRecordItemOut] = Field(default_factory=list, description="日期 / 体重 / BMI 数组")


# ---------------------------------------------------------------- 趋势
class WeightTrendPointOut(BaseModel):
    """体重趋势点。"""

    date: dt.date = Field(description="日期")
    weight: float = Field(description="体重kg")


class WeightTrendOut(BaseModel):
    """体重趋势出参（缺失日期不补点）。"""

    days: int = Field(description="统计天数")
    start_date: dt.date = Field(description="起始日期")
    count: int = Field(default=0, description="有效数据点数")
    change: float = Field(default=0, description="区间内体重变化kg（末值-首值，正数为增重）")
    points: list[WeightTrendPointOut] = Field(default_factory=list, description="按日期升序")


class BodyFatTrendPointOut(BaseModel):
    """体脂趋势点。"""

    date: dt.date = Field(description="日期")
    body_fat: float = Field(description="体脂率%")


class BodyFatTrendOut(BaseModel):
    """体脂趋势出参（缺失日期不补点）。"""

    days: int = Field(description="统计天数")
    start_date: dt.date = Field(description="起始日期")
    count: int = Field(default=0, description="有效数据点数")
    change: float = Field(default=0, description="区间内体脂率变化百分点（末值-首值）")
    points: list[BodyFatTrendPointOut] = Field(default_factory=list, description="按日期升序")


# ---------------------------------------------------------------- 卡路里收支
class CaloriesBalanceOut(BaseModel):
    """单日卡路里收支出参。"""

    date: dt.date = Field(description="统计日期")
    intake: float = Field(default=0, description="摄入热量（饮食记录合计，千卡）")
    workout_calories: float = Field(default=0, description="运动消耗（训练记录合计，千卡）")
    basal_metabolism: float = Field(default=0, description="基础代谢估算值（千卡）")
    total_burn: float = Field(default=0, description="总消耗 = 运动消耗 + 基础代谢")
    balance: float = Field(default=0, description="收支差值 = 摄入 - 总消耗，正数为盈余")
    status: str = Field(default="balanced", description="状态码：surplus 盈余 / balanced 均衡 / deficit 赤字")
    status_text: str = Field(default="收支均衡", description="状态中文说明")
    advice: str = Field(default="", description="建议文案")
    estimated: bool = Field(default=False, description="基础代谢是否用了 1800 兜底估算")
    estimate_note: str = Field(default="", description="估算说明：用了哪些数据、缺了什么")


class CaloriesBalanceDayOut(BaseModel):
    """月度收支中的一天。"""

    date: dt.date = Field(description="日期")
    intake: float = Field(default=0, description="摄入热量(千卡)")
    workout_calories: float = Field(default=0, description="运动消耗(千卡)")
    basal_metabolism: float = Field(default=0, description="基础代谢估算(千卡)")
    total_burn: float = Field(default=0, description="总消耗(千卡)")
    balance: float = Field(default=0, description="收支差值(千卡)")


class CaloriesBalanceMonthOut(BaseModel):
    """月度卡路里收支出参（每天一条，无数据补 0）。"""

    year: int = Field(description="年份")
    month: int = Field(description="月份 1-12")
    days_in_month: int = Field(description="当月天数")
    total_intake: float = Field(default=0, description="当月总摄入(千卡)")
    total_burn: float = Field(default=0, description="当月总消耗(千卡)")
    estimated: bool = Field(default=False, description="基础代谢是否用了 1800 兜底估算")
    estimate_note: str = Field(default="", description="估算说明")
    items: list[CaloriesBalanceDayOut] = Field(default_factory=list, description="按日期升序的每日收支")


# ---------------------------------------------------------------- 训练频率
class FrequencyWeekItemOut(BaseModel):
    """单个 ISO 周的训练频率。"""

    week_label: str = Field(description="周标签，如 2025-W07")
    year: int = Field(description="ISO 年份")
    week: int = Field(description="ISO 周序号")
    start_date: dt.date = Field(description="周一日期")
    end_date: dt.date = Field(description="周日日期")
    workout_days: int = Field(default=0, description="训练天数（去重日期）")
    total_count: int = Field(default=0, description="训练总次数")
    total_duration_min: int = Field(default=0, description="累计时长(分钟)")
    avg_duration_min: float = Field(default=0, description="平均每次时长(分钟)")


class FrequencyOut(BaseModel):
    """训练频率出参。"""

    weeks: int = Field(description="统计周数")
    items: list[FrequencyWeekItemOut] = Field(default_factory=list, description="按周从早到晚排列")


# ---------------------------------------------------------------- 数据看板
class DashboardOut(BaseModel):
    """个人数据看板：一次请求聚合所有首页要用的数据。"""

    nickname: str | None = Field(default=None, description="昵称")
    level: int = Field(default=1, description="用户等级")
    points: int = Field(default=0, description="总积分")
    height: float | None = Field(default=None, description="身高cm")
    target_weight: float | None = Field(default=None, description="目标体重kg")

    latest_metric_date: dt.date | None = Field(default=None, description="最新身体数据日期")
    weight: float | None = Field(default=None, description="最新体重kg")
    body_fat: float | None = Field(default=None, description="最新体脂率%")
    muscle_mass: float | None = Field(default=None, description="最新肌肉量kg")
    bmi: float | None = Field(default=None, description="最新 BMI")
    bmi_level: str | None = Field(default=None, description="BMI 分级")

    month_workout_count: int = Field(default=0, description="本月训练次数")
    month_workout_duration_min: int = Field(default=0, description="本月训练时长(分钟)")
    month_workout_calories: float = Field(default=0, description="本月训练消耗(千卡)")
    week_workout_count: int = Field(default=0, description="本周训练次数")
    streak_days: int = Field(default=0, description="连续训练天数")

    week_diet_calories: float = Field(default=0, description="本周饮食摄入(千卡)")
    today_diet_calories: float = Field(default=0, description="今天饮食摄入(千卡)")

    checked_in_today: bool = Field(default=False, description="今天是否已签到")
    checkin_streak: int = Field(default=0, description="最近一次签到时的连续天数")
