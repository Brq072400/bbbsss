"""动作库模块的请求 / 响应模型（Pydantic v2）。

动作库是只读数据（由后台/种子数据维护），所以这里只有出参，
入参通过 query 参数直接传递（分类、器械、难度、关键词、排序）。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExerciseCategoryOut(BaseModel):
    """动作分类出参（带该分类下的动作数量）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="分类ID")
    name: str = Field(description="分类名称")
    slug: str = Field(description="英文标识")
    body_part: str | None = Field(default=None, description="主要部位")
    sort_order: int = Field(default=0, description="排序")
    exercise_count: int = Field(default=0, description="该分类下的动作数量")


class ExerciseBriefOut(BaseModel):
    """动作列表项：够列表展示的精简字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="动作ID")
    name: str = Field(description="动作名称")
    name_en: str | None = Field(default=None, description="英文名")
    category_id: int = Field(description="分类ID")
    category_name: str | None = Field(default=None, description="分类名称")
    equipment: str | None = Field(default=None, description="器械")
    difficulty: int = Field(default=1, description="难度 1-5")
    image_url: str | None = Field(default=None, description="动作配图")
    gif_url: str | None = Field(default=None, description="动作动图")
    primary_muscles: str | None = Field(default=None, description="主要发力肌群")


class ExerciseOut(ExerciseBriefOut):
    """动作详情出参：讲解、发力要点、易错提醒等全量字段。"""

    category_slug: str | None = Field(default=None, description="分类英文标识")
    secondary_muscles: str | None = Field(default=None, description="协同肌群")
    description: str | None = Field(default=None, description="动作讲解")
    key_points: str | None = Field(default=None, description="发力要点")
    common_mistakes: str | None = Field(default=None, description="易错提醒")
    tips: str | None = Field(default=None, description="呼吸与节奏提示")
    keywords: str | None = Field(default=None, description="搜索关键词，逗号分隔")
    view_count: int = Field(default=0, description="浏览数")
    is_active: bool = Field(default=True, description="是否启用")


class ExerciseSearchItemOut(ExerciseBriefOut):
    """搜索结果项：在摘要基础上多返回匹配度信息。"""

    match_score: int = Field(default=0, description="匹配度分数，越大越匹配")
    match_reason: str = Field(default="", description="匹配度说明，如“名称完全匹配”")


class ExerciseSearchResultOut(BaseModel):
    """搜索结果集合出参。"""

    keyword: str = Field(description="搜索关键词")
    total: int = Field(default=0, description="命中条数（最多 20）")
    items: list[ExerciseSearchItemOut] = Field(default_factory=list, description="按匹配度从高到低排序")


class ExerciseRelatedOut(BaseModel):
    """相似动作推荐出参。"""

    base_id: int = Field(description="当前动作ID")
    items: list[ExerciseBriefOut] = Field(default_factory=list, description="同分类或同器械的动作，最多 6 条")


class ExerciseFilterOptionsOut(BaseModel):
    """动作列表可用的筛选项字典。"""

    categories: list[ExerciseCategoryOut] = Field(default_factory=list, description="全部动作分类")
    equipments: list[str] = Field(default_factory=list, description="全部器械选项")
    difficulties: list[int] = Field(default_factory=list, description="难度选项 1-5")
