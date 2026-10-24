"""饮食模块的 Pydantic 数据模型（schema 层）。

食物库的营养数据统一以「每 100 克」为基准存储，
饮食记录里的营养值 = 食物营养 × (amount_g / 100)，换算逻辑放在路由层（diet.py）。
"""
from __future__ import annotations

# 注意：DaySummaryOut / DailyCaloriesOut 里有名为 date 的字段，为避免
# 「字段名与类型名撞车」，日期类型统一用 _dt.date 的写法。
import datetime as _dt
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 餐次枚举：与 models.diet.DietRecord.meal_type 保持一致
MealType = Literal["breakfast", "lunch", "dinner", "snack"]

# 餐次中文名与固定展示顺序（前端按顺序渲染早/午/晚/加餐）
MEAL_LABELS: dict[str, str] = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}
MEAL_ORDER: list[str] = ["breakfast", "lunch", "dinner", "snack"]

# 建议摄入默认值（普通成年女性/轻活动量参考值）。
# 说明：目前是全局固定值，后续可改成「按用户目标计算」——
# 例如从用户体重/目标反推：蛋白质 = 体重 × 1.6g，脂肪 = 体重 × 0.8g，
# 再由目标热量倒推碳水，届时把下面的常量换成按 user_id 查库即可。
DEFAULT_TARGET_CALORIES: float = 2000.0
DEFAULT_TARGET_PROTEIN: float = 100.0      # 2000 千卡 × 20% ÷ 4 千卡/g
DEFAULT_TARGET_FAT: float = 56.0           # 2000 千卡 × 25% ÷ 9 千卡/g
DEFAULT_TARGET_CARBOHYDRATE: float = 275.0  # 2000 千卡 × 55% ÷ 4 千卡/g


def percent_of(value: float, target: float) -> float:
    """计算完成度百分比（保留 2 位小数，目标为 0 时返回 0，避免除零）。"""
    if not target:
        return 0.0
    return round((value or 0) / target * 100, 2)


# ---------------------------------------------------------------- 食物库
class FoodOut(BaseModel):
    """食物出参（每 100 克营养数据）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="食物ID")
    name: str = Field(description="食物名称")
    category: str = Field(default="others", description="分类 主食/肉蛋/蔬菜/水果/乳品/零食")
    unit: str = Field(default="100g", description="计量单位描述")
    calories: float = Field(default=0, description="每100g热量(千卡)")
    protein: float = Field(default=0, description="每100g蛋白质(g)")
    fat: float = Field(default=0, description="每100g脂肪(g)")
    carbohydrate: float = Field(default=0, description="每100g碳水(g)")
    fiber: float = Field(default=0, description="每100g膳食纤维(g)")
    sodium: float = Field(default=0, description="每100g钠(mg)")
    is_common: bool = Field(default=True, description="是否常用食物")
    created_by: int | None = Field(default=None, description="自定义食物创建者，系统食物为 None")
    created_at: datetime | None = Field(default=None, description="创建时间")


class FoodCreateRequest(BaseModel):
    """新增自定义食物的入参（is_common 强制为 False，由后端决定）。"""

    name: str = Field(min_length=1, max_length=100, description="食物名称")
    category: str = Field(default="others", max_length=30, description="分类")
    unit: str = Field(default="100g", max_length=20, description="计量单位描述")
    calories: float = Field(default=0, ge=0, le=10000, description="每100g热量(千卡)")
    protein: float = Field(default=0, ge=0, le=1000, description="每100g蛋白质(g)")
    fat: float = Field(default=0, ge=0, le=1000, description="每100g脂肪(g)")
    carbohydrate: float = Field(default=0, ge=0, le=1000, description="每100g碳水(g)")
    fiber: float = Field(default=0, ge=0, le=1000, description="每100g膳食纤维(g)")
    sodium: float = Field(default=0, ge=0, le=100000, description="每100g钠(mg)")

    @field_validator("name", "category", "unit")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        """去掉首尾空白，名称不允许为空。"""
        text = (value or "").strip()
        if not text:
            raise ValueError("字段不能为空")
        return text


class FoodCategoryOut(BaseModel):
    """食物分类及该分类下的食物数量。"""

    category: str = Field(description="分类名称")
    count: int = Field(default=0, description="该分类食物数量")


# ---------------------------------------------------------------- 饮食记录
class DietRecordCreateRequest(BaseModel):
    """添加饮食记录的入参：food_id 与 food_name 至少传一个。"""

    diet_date: date | None = Field(default=None, description="日期，不传默认今天")
    meal_type: MealType = Field(default="breakfast", description="餐次 breakfast/lunch/dinner/snack")
    food_id: int | None = Field(default=None, ge=1, description="食物库ID，二选一")
    food_name: str | None = Field(default=None, max_length=100, description="自定义食物名称，二选一")
    amount_g: float = Field(default=100, gt=0, le=5000, description="食用量(克)")
    note: str | None = Field(default=None, max_length=200, description="备注")

    @model_validator(mode="after")
    def _check_food_selected(self) -> "DietRecordCreateRequest":
        """校验 food_id 与 food_name 至少提供一项（否则不知道吃了什么）。"""
        if self.food_id is None and not (self.food_name or "").strip():
            raise ValueError("food_id 与 food_name 必须二选一")
        return self

    @field_validator("food_name")
    @classmethod
    def _strip_food_name(cls, value: str | None) -> str | None:
        """自定义食物名去空白，空串转 None。"""
        if value is None:
            return None
        return value.strip() or None


class DietRecordUpdateRequest(BaseModel):
    """修改饮食记录的入参：所有字段可选，只改传入的字段。"""

    diet_date: date | None = Field(default=None, description="日期")
    meal_type: MealType | None = Field(default=None, description="餐次")
    food_name: str | None = Field(default=None, max_length=100, description="食物名称快照")
    amount_g: float | None = Field(default=None, gt=0, le=5000, description="食用量(克)，改这个会重算营养")
    note: str | None = Field(default=None, max_length=200, description="备注")


class DietRecordOut(BaseModel):
    """饮食记录出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="记录ID")
    user_id: int = Field(description="所属用户ID")
    diet_date: date = Field(description="日期")
    meal_type: str = Field(default="breakfast", description="餐次")
    food_id: int | None = Field(default=None, description="食物库ID")
    food_name: str = Field(description="食物名称快照")
    amount_g: float = Field(default=0, description="食用量(克)")
    calories: float = Field(default=0, description="本次摄入热量(千卡)")
    protein: float = Field(default=0, description="本次蛋白质(g)")
    fat: float = Field(default=0, description="本次脂肪(g)")
    carbohydrate: float = Field(default=0, description="本次碳水(g)")
    note: str | None = Field(default=None, description="备注")
    created_at: datetime | None = Field(default=None, description="创建时间")
    food: FoodOut | None = Field(default=None, description="关联的食物库信息（自定义食物时为空）")


class MealGroupOut(BaseModel):
    """某一天里某个餐次的分组结果。"""

    meal_type: str = Field(description="餐次")
    meal_label: str = Field(description="餐次中文名")
    total_calories: float = Field(default=0, description="该餐次热量合计(千卡)")
    items: list[DietRecordOut] = Field(default_factory=list, description="该餐次的记录列表")


class DaySummaryOut(BaseModel):
    """某天饮食汇总：按餐次分组 + 全天合计 + 占建议摄入的百分比。"""

    date: _dt.date = Field(description="统计日期")
    target_calories: float = Field(default=DEFAULT_TARGET_CALORIES, description="建议摄入热量(千卡)")
    target_protein: float = Field(default=DEFAULT_TARGET_PROTEIN, description="建议蛋白质(g)")
    target_fat: float = Field(default=DEFAULT_TARGET_FAT, description="建议脂肪(g)")
    target_carbohydrate: float = Field(default=DEFAULT_TARGET_CARBOHYDRATE, description="建议碳水(g)")
    total_calories: float = Field(default=0, description="当天总热量(千卡)")
    total_protein: float = Field(default=0, description="当天蛋白质合计(g)")
    total_fat: float = Field(default=0, description="当天脂肪合计(g)")
    total_carbohydrate: float = Field(default=0, description="当天碳水合计(g)")
    calorie_percent: float = Field(default=0, description="热量占建议摄入百分比")
    protein_percent: float = Field(default=0, description="蛋白质占建议摄入百分比")
    fat_percent: float = Field(default=0, description="脂肪占建议摄入百分比")
    carbohydrate_percent: float = Field(default=0, description="碳水占建议摄入百分比")
    record_count: int = Field(default=0, description="当天记录条数")
    meals: list[MealGroupOut] = Field(default_factory=list, description="按餐次分组的结果")


class DailyCaloriesOut(BaseModel):
    """统计区间里的一天热量。"""

    date: _dt.date = Field(description="日期")
    calories: float = Field(default=0, description="当天热量(千卡)")


class DietStatsOut(BaseModel):
    """饮食区间统计出参。"""

    start_date: date = Field(description="区间开始日期")
    end_date: date = Field(description="区间结束日期")
    days: list[DailyCaloriesOut] = Field(default_factory=list, description="每日热量数组（缺失日期补 0）")
    total_calories: float = Field(default=0, description="区间总热量(千卡)")
    total_protein: float = Field(default=0, description="区间蛋白质合计(g)")
    total_fat: float = Field(default=0, description="区间脂肪合计(g)")
    total_carbohydrate: float = Field(default=0, description="区间碳水合计(g)")
    avg_daily_calories: float = Field(default=0, description="平均每日热量(千卡)")
    record_count: int = Field(default=0, description="区间内记录条数")


__all__ = [
    "MEAL_LABELS",
    "MEAL_ORDER",
    "DailyCaloriesOut",
    "DaySummaryOut",
    "DietRecordCreateRequest",
    "DietRecordOut",
    "DietRecordUpdateRequest",
    "DietStatsOut",
    "DEFAULT_TARGET_CALORIES",
    "DEFAULT_TARGET_CARBOHYDRATE",
    "DEFAULT_TARGET_FAT",
    "DEFAULT_TARGET_PROTEIN",
    "FoodCategoryOut",
    "FoodCreateRequest",
    "FoodOut",
    "MealGroupOut",
    "MealType",
    "percent_of",
]
