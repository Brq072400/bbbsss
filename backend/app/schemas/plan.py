"""运动计划模块的 Pydantic 数据模型（Pydantic v2）。

约定：
- 入参模型统一以 ``Request`` 结尾，出参模型统一以 ``Out`` 结尾；
- 出参模型全部开启 ``from_attributes``，可直接由 ORM 对象 ``model_validate`` 得到；
- 时间字段使用 ``datetime`` / ``date``，由 FastAPI 序列化为 ISO 字符串；
- 提醒时间以 ``"HH:MM"`` 文本对外，避免前端处理 ``time`` 对象的兼容问题。
"""
from __future__ import annotations

from datetime import date, datetime
# 注意：模型里存在名为 date 的字段，为避免「字段名与类型注解同名」冲突，
# 注解侧统一使用下面这个别名 DateType。
from datetime import date as DateType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 周期类型：daily = 每天都一样，weekly = 按周一到周日排
CycleType = Literal["daily", "weekly"]
# 计划状态：active 进行中 / archived 已归档
PlanStatus = Literal["active", "archived"]


# ================================================================ 入参：动作明细
class PlanItemRequest(BaseModel):
    """单条计划动作安排（入参）。

    用于创建计划、整体替换计划明细、以及给计划追加动作。
    """

    day_index: int = Field(default=1, ge=1, le=30, description="周期内第几天，从 1 开始")
    exercise_id: int | None = Field(default=None, ge=1, description="动作库ID，为空表示自定义动作")
    sets: int = Field(default=3, ge=0, le=99, description="组数")
    reps: int = Field(default=12, ge=0, le=999, description="每组次数")
    weight: float | None = Field(default=None, ge=0, le=1000, description="建议重量 kg")
    rest_seconds: int = Field(default=60, ge=0, le=3600, description="组间休息秒数")
    duration_min: int | None = Field(default=None, ge=0, le=600, description="有氧/静力动作时长（分钟）")
    note: str | None = Field(default=None, max_length=200, description="备注")


class PlanItemUpdateRequest(BaseModel):
    """修改单条动作安排（入参）。

    所有字段可选，只更新请求里实际传了的字段（``exclude_unset`` 判断）。
    """

    day_index: int | None = Field(default=None, ge=1, le=30, description="周期内第几天")
    exercise_id: int | None = Field(default=None, ge=1, description="动作库ID")
    sets: int | None = Field(default=None, ge=0, le=99, description="组数")
    reps: int | None = Field(default=None, ge=0, le=999, description="每组次数")
    weight: float | None = Field(default=None, ge=0, le=1000, description="建议重量 kg")
    rest_seconds: int | None = Field(default=None, ge=0, le=3600, description="组间休息秒数")
    duration_min: int | None = Field(default=None, ge=0, le=600, description="时长（分钟）")
    note: str | None = Field(default=None, max_length=200, description="备注")


# ================================================================ 入参：计划本体
class PlanPublishRequest(BaseModel):
    """创建（发布）训练计划（入参）。"""

    name: str = Field(..., min_length=1, max_length=100, description="计划名称")
    description: str | None = Field(default=None, max_length=2000, description="计划说明")
    goal: str = Field(
        default="keep_fit",
        max_length=30,
        description="训练目标：gain_muscle 增肌 / lose_fat 减脂 / shape 塑形 / rehab 康复 / keep_fit 保持",
    )
    cycle_type: CycleType = Field(default="weekly", description="周期类型 daily=每日循环 weekly=按周")
    cycle_days: int = Field(default=7, ge=1, le=30, description="一个周期的天数")
    cover: str | None = Field(default=None, max_length=255, description="封面图地址")
    is_public: bool = Field(default=False, description="是否公开（公开后才允许他人查看/收藏）")
    items: list[PlanItemRequest] = Field(default_factory=list, description="动作明细列表")

    @model_validator(mode="after")
    def _check_items_day_index(self) -> "PlanPublishRequest":
        """校验每条动作的 day_index 不超过周期天数，并归一化每日排序。"""
        for item in self.items:
            if item.day_index > self.cycle_days:
                raise ValueError(f"动作的 day_index({item.day_index}) 不能超过周期天数 {self.cycle_days}")
        return self


class PlanUpdateRequest(BaseModel):
    """编辑训练计划（入参）。

    只更新传入的字段；``items`` 一旦传入就整体替换原有动作明细。
    """

    name: str | None = Field(default=None, min_length=1, max_length=100, description="计划名称")
    description: str | None = Field(default=None, max_length=2000, description="计划说明")
    goal: str | None = Field(default=None, max_length=30, description="训练目标")
    cycle_type: CycleType | None = Field(default=None, description="周期类型")
    cycle_days: int | None = Field(default=None, ge=1, le=30, description="一个周期的天数")
    cover: str | None = Field(default=None, max_length=255, description="封面图地址")
    is_public: bool | None = Field(default=None, description="是否公开")
    status: PlanStatus | None = Field(default=None, description="计划状态 active/archived")
    items: list[PlanItemRequest] | None = Field(default=None, description="动作明细，传了即整体替换")


# ================================================================ 入参：分享 / 打卡 / 提醒
class ShareCreateRequest(BaseModel):
    """生成计划分享码（入参）。"""

    expires_hours: int | None = Field(
        default=None, ge=1, le=24 * 365, description="有效小时数，不传表示永久有效"
    )


class PlanCheckinRequest(BaseModel):
    """计划打卡（入参）。"""

    day_index: int = Field(default=1, ge=1, le=30, description="本次完成的是周期内第几天")
    note: str | None = Field(default=None, max_length=200, description="打卡备注")


class PlanReminderRequest(BaseModel):
    """设置计划提醒（入参）。"""

    remind_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="提醒时间 HH:MM")
    weekdays: str = Field(default="1,2,3,4,5,6,7", max_length=20, description="周几提醒，逗号分隔 1-7")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: str) -> str:
        """校验 weekdays 只能是 1-7 的逗号分隔整数，并去重排序后归一化。"""
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if not parts:
            raise ValueError("weekdays 不能为空，例如 1,2,3")
        days: list[int] = []
        for part in parts:
            if not part.isdigit() or not 1 <= int(part) <= 7:
                raise ValueError("weekdays 只能是 1-7 之间的整数，用逗号分隔")
            days.append(int(part))
        return ",".join(str(d) for d in sorted(set(days)))


# ================================================================ 出参：动作明细
class ExerciseBriefOut(BaseModel):
    """动作简要信息（计划明细里展示名称与配图）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="动作ID")
    name: str = Field(description="动作名称")
    name_en: str | None = Field(default=None, description="英文名")
    equipment: str | None = Field(default=None, description="所需器械")
    difficulty: int | None = Field(default=None, description="难度 1-5")
    image_url: str | None = Field(default=None, description="动作配图")
    gif_url: str | None = Field(default=None, description="动作动图")


class PlanItemOut(BaseModel):
    """计划里的一条动作安排（出参）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="明细ID")
    plan_id: int = Field(description="所属计划ID")
    day_index: int = Field(description="周期内第几天")
    sort_order: int = Field(description="当天排序")
    exercise_id: int | None = Field(default=None, description="动作ID")
    sets: int = Field(description="组数")
    reps: int = Field(description="每组次数")
    weight: float | None = Field(default=None, description="建议重量 kg")
    rest_seconds: int = Field(description="组间休息秒数")
    duration_min: int | None = Field(default=None, description="时长（分钟）")
    note: str | None = Field(default=None, description="备注（模板动作未匹配到动作库时保存动作名）")
    exercise: ExerciseBriefOut | None = Field(default=None, description="关联的动作详情，用于展示名称与配图")


# ================================================================ 出参：计划
class PlanBriefOut(BaseModel):
    """计划简要信息（列表用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int = Field(description="所属用户ID")
    name: str = Field(description="计划名称")
    description: str | None = Field(default=None, description="计划说明")
    goal: str = Field(description="训练目标")
    cycle_type: str = Field(description="周期类型 daily/weekly")
    cycle_days: int = Field(description="周期天数")
    cover: str | None = Field(default=None, description="封面图")
    is_public: bool = Field(description="是否公开")
    is_template: bool = Field(default=False, description="是否另存为模板")
    favorite_count: int = Field(default=0, description="被收藏次数")
    status: str = Field(description="active/archived")
    items_count: int = Field(default=0, description="动作明细条数")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class PlanDetailOut(PlanBriefOut):
    """计划详情（含动作明细与当前查看者的附加状态）。"""

    is_owner: bool = Field(default=False, description="当前查看者是否本人")
    is_favorited: bool = Field(default=False, description="当前用户是否已收藏")
    items: list[PlanItemOut] = Field(default_factory=list, description="动作明细，按 day_index + sort_order 排序")


class PlanFavoriteOut(PlanBriefOut):
    """我收藏的计划（在计划信息上附加收藏时间）。"""

    favorited_at: datetime | None = Field(default=None, description="收藏时间")


# ================================================================ 出参：模板库
class TemplateItemOut(BaseModel):
    """模板里的一条动作（由 items_json 解析而来）。"""

    model_config = ConfigDict(from_attributes=True)

    exercise: str = Field(default="", description="动作名称（模板按名称存储，使用时再匹配动作库）")
    sets: int = Field(default=3, description="组数")
    reps: int = Field(default=12, description="每组次数")
    weight: float | None = Field(default=None, description="建议重量 kg")
    rest_seconds: int = Field(default=60, description="组间休息秒数")
    duration_min: int | None = Field(default=None, description="时长（分钟）")
    note: str | None = Field(default=None, description="备注")


class TemplateDayOut(BaseModel):
    """模板里某一天的动作集合。"""

    model_config = ConfigDict(from_attributes=True)

    day_index: int = Field(default=1, description="周期内第几天")
    items: list[TemplateItemOut] = Field(default_factory=list, description="当天的动作列表")


class PlanTemplateOut(BaseModel):
    """计划模板（出参）。

    ``items_json`` 会被解析成结构化的 ``items``，同时给出动作总条数。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = Field(description="模板名称")
    category: str = Field(description="分类：新手/减脂/增肌……")
    goal: str = Field(description="训练目标")
    difficulty: int = Field(description="难度 1-5")
    cycle_type: str = Field(description="daily/weekly")
    cycle_days: int = Field(description="周期天数")
    cover: str | None = Field(default=None, description="封面")
    description: str | None = Field(default=None, description="模板说明")
    use_count: int = Field(default=0, description="被使用次数")
    is_official: bool = Field(default=True, description="是否官方模板")
    items: list[TemplateDayOut] = Field(default_factory=list, description="按天分组的动作明细")
    items_count: int = Field(default=0, description="动作总条数")


# ================================================================ 出参：分享
class PlanShareOut(BaseModel):
    """计划分享信息（出参）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int = Field(description="计划ID")
    share_code: str = Field(description="分享码")
    expires_at: datetime | None = Field(default=None, description="过期时间，空表示永久")
    view_count: int = Field(default=0, description="被查看次数")
    created_at: datetime | None = Field(default=None, description="生成时间")


# ================================================================ 出参：打卡
class PlanCheckinOut(BaseModel):
    """计划打卡记录（出参）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int = Field(description="计划ID")
    user_id: int = Field(description="用户ID")
    checkin_date: date = Field(description="打卡日期")
    day_index: int = Field(description="完成的周期第几天")
    completed: bool = Field(description="是否完成")
    note: str | None = Field(default=None, description="打卡备注")
    created_at: datetime | None = Field(default=None, description="打卡时间")


class PlanCheckinResultOut(BaseModel):
    """打卡结果：记录 + 本次获得积分 + 账号总积分。"""

    checkin: PlanCheckinOut = Field(description="打卡记录")
    points_awarded: int = Field(default=0, description="本次获得积分")
    total_points: int = Field(default=0, description="账号当前总积分")


class CheckinCalendarDayOut(BaseModel):
    """打卡日历中的一天。"""

    date: DateType = Field(description="日期")
    checked: bool = Field(default=False, description="是否已打卡")
    day_index: int | None = Field(default=None, description="该天打卡对应的周期第几天")


class PlanStatsOut(BaseModel):
    """计划完成统计（出参）。"""

    plan_id: int
    plan_name: str
    cycle_type: str = Field(description="daily/weekly")
    cycle_days: int = Field(description="周期天数")
    total_checkins: int = Field(default=0, description="总打卡次数")
    week_checkins: int = Field(default=0, description="本周（周一起算）打卡次数")
    streak_days: int = Field(default=0, description="连续打卡天数")
    checked_days: int = Field(default=0, description="累计打卡天数（按日期去重）")
    expected_days: int = Field(default=0, description="计划执行天数（以 cycle_days 为基准推算）")
    complete_rate: float = Field(default=0.0, description="完成率 0~1 = 打卡天数 / 计划执行天数")
    complete_percent: float = Field(default=0.0, description="完成率百分比 0~100")
    calendar: list[CheckinCalendarDayOut] = Field(default_factory=list, description="最近 30 天打卡日历")


# ================================================================ 出参：今日任务
class TodayPlanOut(BaseModel):
    """今天该做的动作（/plans/checkin/today 的单项）。"""

    plan_id: int
    plan_name: str
    cycle_type: str = Field(description="daily/weekly")
    cycle_days: int = Field(description="周期天数")
    day_index: int = Field(description="今天对应周期内第几天")
    date: DateType = Field(description="今天的日期")
    is_rest_day: bool = Field(default=False, description="今天是否休息日（当天没有动作）")
    checked_in: bool = Field(default=False, description="今天是否已打卡")
    items: list[PlanItemOut] = Field(default_factory=list, description="今天的动作列表")


# ================================================================ 出参：提醒
class PlanReminderOut(BaseModel):
    """计划提醒设置（出参）。

    ``remind_time`` 统一输出 ``"HH:MM"`` 文本，因此用 ``from_model`` 手工构造。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int = Field(description="计划ID")
    user_id: int = Field(description="用户ID")
    remind_time: str = Field(description="提醒时间 HH:MM")
    weekdays: str = Field(description="周几提醒，逗号分隔 1-7")
    enabled: bool = Field(description="是否启用")
    last_fired_at: datetime | None = Field(default=None, description="上次触发时间")
    created_at: datetime | None = Field(default=None, description="创建时间")

    @classmethod
    def from_model(cls, obj: Any) -> "PlanReminderOut":
        """把 ``PlanReminder`` ORM 对象转成出参（时间格式化为 HH:MM）。"""
        remind_time = obj.remind_time
        text = remind_time.strftime("%H:%M") if remind_time is not None else ""
        return cls(
            id=obj.id,
            plan_id=obj.plan_id,
            user_id=obj.user_id,
            remind_time=text,
            weekdays=obj.weekdays or "",
            enabled=bool(obj.enabled),
            last_fired_at=obj.last_fired_at,
            created_at=obj.created_at,
        )


# ================================================================ 出参：通用结果
class PlanFavoriteResultOut(BaseModel):
    """计划收藏/取消收藏的结果。"""

    plan_id: int
    is_favorited: bool = Field(description="操作后是否处于已收藏状态")
    favorite_count: int = Field(default=0, description="计划当前被收藏数")


__all__ = [
    "CycleType",
    "PlanStatus",
    "PlanItemRequest",
    "PlanItemUpdateRequest",
    "PlanPublishRequest",
    "PlanUpdateRequest",
    "ShareCreateRequest",
    "PlanCheckinRequest",
    "PlanReminderRequest",
    "ExerciseBriefOut",
    "PlanItemOut",
    "PlanBriefOut",
    "PlanDetailOut",
    "PlanFavoriteOut",
    "TemplateItemOut",
    "TemplateDayOut",
    "PlanTemplateOut",
    "PlanShareOut",
    "PlanCheckinOut",
    "PlanCheckinResultOut",
    "CheckinCalendarDayOut",
    "PlanStatsOut",
    "TodayPlanOut",
    "PlanReminderOut",
    "PlanFavoriteResultOut",
]
