"""用户模块的 Pydantic 数据模型（Pydantic v2）。

约定：
- 入参统一命名为 XxxRequest，出参统一命名为 XxxOut；
- 出参需要从 ORM 对象直接转换时，使用 ``model_config = ConfigDict(from_attributes=True)``；
- 时间字段沿用模型里的无时区 ``datetime``，日期字段用 ``date``；
- 密码长度等强业务规则在路由层用 ``BadRequestError`` 抛出（返回 400），
  这里只做基本的类型与长度约束。
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.core.security import mask_phone

# 类型别名：CalendarDayOut 里存在名为 date 的字段，
# 直接写 ``date: date`` 会让注解与字段名同名冲突，这里用别名规避。
DateType = date

# 性别取值：0 未知 / 1 男 / 2 女
GENDER_UNKNOWN = 0
GENDER_MALE = 1
GENDER_FEMALE = 2

# 实名认证状态
REALNAME_NONE = "none"
REALNAME_PENDING = "pending"
REALNAME_APPROVED = "approved"
REALNAME_REJECTED = "rejected"


# ==================================================================== 用户出参
class UserOut(BaseModel):
    """用户基础信息出参（不含密码哈希等敏感字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    nickname: str | None = Field(default=None, description="昵称")
    display_name: str = Field(default="", description="展示名（昵称优先）")
    avatar: str | None = Field(default=None, description="头像URL")
    gender: int = Field(default=GENDER_UNKNOWN, description="性别 0未知 1男 2女")
    birthday: date | None = Field(default=None, description="生日")
    height: float | None = Field(default=None, description="身高cm")
    target_weight: float | None = Field(default=None, description="目标体重kg")
    signature: str | None = Field(default=None, description="个性签名")
    phone: str | None = Field(default=None, description="手机号（本人可见完整值）")
    phone_masked: str = Field(default="", description="脱敏手机号")
    email: str | None = Field(default=None, description="邮箱")
    city: str | None = Field(default=None, description="城市")
    points: int = Field(default=0, description="总积分")
    level: int = Field(default=1, description="等级")
    is_verified: bool = Field(default=False, description="是否已实名认证")
    is_disabled: bool = Field(default=False, description="是否被封禁")
    last_login_at: datetime | None = Field(default=None, description="最后登录时间")
    created_at: datetime | None = Field(default=None, description="注册时间")

    @model_validator(mode="after")
    def _fill_derived(self) -> "UserOut":
        """补齐派生字段：脱敏手机号与展示名（ORM 上没有 phone_masked 属性）。"""
        if not self.phone_masked and self.phone:
            self.phone_masked = mask_phone(self.phone)
        if not self.display_name:
            self.display_name = self.nickname or self.username
        return self


class ProfileOut(UserOut):
    """我的资料出参：在基础信息上追加等级进度与签到统计。"""

    next_level_points: int | None = Field(default=None, description="下一等级所需积分，已满级为 null")
    points_to_next_level: int = Field(default=0, description="距离下一等级还差多少积分")
    max_level: int = Field(default=1, description="系统最高等级")
    checkin_total: int = Field(default=0, description="累计签到天数")
    checkin_streak: int = Field(default=0, description="当前连续签到天数")
    checkin_month: int = Field(default=0, description="本月签到天数")
    today_checked: bool = Field(default=False, description="今天是否已签到")


# ==================================================================== 认证入参/出参
class RegisterRequest(BaseModel):
    """注册入参。"""

    username: str = Field(min_length=3, max_length=50, description="用户名，3-50 个字符")
    password: str = Field(min_length=1, max_length=64, description="密码，至少 6 位")
    nickname: str | None = Field(default=None, max_length=50, description="昵称，可选")
    phone: str | None = Field(default=None, max_length=20, description="手机号，可选")
    email: str | None = Field(default=None, max_length=120, description="邮箱，可选")


class LoginRequest(BaseModel):
    """登录入参：账号可以是用户名，也可以是手机号。

    字段名 account / username / phone 都接受，方便不同前端调用。
    """

    account: str = Field(
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("account", "username", "phone"),
        description="用户名或手机号",
    )
    password: str = Field(min_length=1, max_length=64, description="密码")


class AuthOut(BaseModel):
    """登录/注册/刷新令牌出参：令牌 + 当前用户信息。"""

    token: str = Field(description="JWT 访问令牌")
    access_token: str = Field(description="JWT 访问令牌（同 token，兼容 OAuth2 命名）")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="有效期（秒）")
    user: UserOut | None = Field(default=None, description="当前用户信息")


class PasswordResetRequest(BaseModel):
    """请求重置密码入参：手机号与邮箱至少填一个。"""

    phone: str | None = Field(default=None, max_length=20, description="注册手机号")
    email: str | None = Field(default=None, max_length=120, description="注册邮箱")


class PasswordResetConfirmRequest(BaseModel):
    """用验证码重置密码入参。"""

    code: str = Field(min_length=4, max_length=10, description="6 位验证码")
    new_password: str = Field(min_length=1, max_length=64, description="新密码，至少 6 位")
    phone: str | None = Field(default=None, max_length=20, description="注册手机号")
    email: str | None = Field(default=None, max_length=120, description="注册邮箱")


class PhoneBindRequest(BaseModel):
    """绑定手机号第一步（发送验证码）入参。"""

    phone: str = Field(min_length=6, max_length=20, description="要绑定的手机号")


class PhoneBindConfirmRequest(BaseModel):
    """绑定手机号第二步（校验验证码）入参。"""

    phone: str = Field(min_length=6, max_length=20, description="要绑定的手机号")
    code: str = Field(min_length=4, max_length=10, description="6 位验证码")


class PasswordChangeRequest(BaseModel):
    """修改密码入参。"""

    old_password: str = Field(min_length=1, max_length=64, description="原密码")
    new_password: str = Field(min_length=1, max_length=64, description="新密码，至少 6 位")


class SmsCodeOut(BaseModel):
    """验证码发送结果出参。"""

    target: str = Field(description="接收方（手机号会脱敏）")
    scene: str = Field(description="用途 bind_phone / reset_password")
    code: str = Field(description="验证码；生产环境应改为通过短信/邮件网关下发，不返回给前端")
    expires_in: int = Field(description="有效期（秒）")


# ==================================================================== 资料修改
class ProfileUpdateRequest(BaseModel):
    """修改个人资料入参：所有字段可选，只更新传入的字段。"""

    nickname: str | None = Field(default=None, max_length=50, description="昵称")
    gender: int | None = Field(default=None, ge=0, le=2, description="性别 0未知 1男 2女")
    birthday: date | None = Field(default=None, description="生日，格式 YYYY-MM-DD")
    height: float | None = Field(default=None, ge=0, le=300, description="身高cm")
    target_weight: float | None = Field(default=None, ge=0, le=500, description="目标体重kg")
    signature: str | None = Field(default=None, max_length=200, description="个性签名")
    city: str | None = Field(default=None, max_length=50, description="城市")
    email: str | None = Field(default=None, max_length=120, description="邮箱")


class AvatarOut(BaseModel):
    """头像上传出参。"""

    url: str = Field(description="可访问的头像地址")
    avatar: str = Field(description="写入用户资料的头像地址（同 url）")
    filename: str = Field(description="保存在 uploads/avatars 下的文件名")
    size: int = Field(description="文件大小（字节）")


# ==================================================================== 等级
class LevelOut(BaseModel):
    """我的等级信息出参。"""

    level: int = Field(description="当前等级")
    title: str = Field(description="等级称号")
    points: int = Field(description="总积分")
    level_min_points: int = Field(description="当前等级的积分起点")
    next_level_points: int | None = Field(default=None, description="下一等级门槛，已满级为 null")
    points_to_next_level: int = Field(description="距离下一等级还差多少积分，已满级为 0")
    is_max_level: bool = Field(default=False, description="是否已满级")
    progress: float = Field(default=0.0, description="当前等级内的进度百分比 0-100")
    max_level: int = Field(description="系统最高等级")


class LevelRuleOut(BaseModel):
    """单个等级的规则区间。"""

    level: int = Field(description="等级")
    title: str = Field(description="等级称号")
    min_points: int = Field(description="该等级所需最低积分")
    max_points: int | None = Field(default=None, description="该等级积分上限，最高级为 null")
    description: str = Field(default="", description="区间说明")


class LevelRulesOut(BaseModel):
    """等级规则说明出参。"""

    max_level: int = Field(description="系统最高等级")
    checkin_points: int = Field(description="每日签到基础积分")
    checkin_streak_bonus: int = Field(description="连续签到每天额外奖励积分")
    checkin_streak_bonus_cap: int = Field(description="连续签到额外奖励上限")
    rules: list[LevelRuleOut] = Field(default_factory=list, description="各等级区间")


# ==================================================================== 签到
class CheckinOut(BaseModel):
    """签到结果出参。"""

    checkin_date: date = Field(description="签到日期")
    streak: int = Field(description="连续签到天数")
    points_awarded: int = Field(description="本次获得积分")
    bonus: int = Field(default=0, description="其中连续签到额外奖励积分")
    points: int = Field(description="累计总积分")
    level: int = Field(description="签到后的等级")


class CalendarDayOut(BaseModel):
    """签到日历中的一天。"""

    date: DateType = Field(description="日期")
    day: int = Field(description="几号")
    checked: bool = Field(default=False, description="是否已签到")
    streak: int = Field(default=0, description="签到时的连续天数")
    points_awarded: int = Field(default=0, description="当天获得积分")
    is_today: bool = Field(default=False, description="是否是今天")


class CheckinCalendarOut(BaseModel):
    """签到日历出参。"""

    year: int = Field(description="年份")
    month: int = Field(description="月份")
    days: list[CalendarDayOut] = Field(default_factory=list, description="当月每一天的签到情况")
    streak_list: list[int] = Field(default_factory=list, description="当月每次签到时的连续天数序列")
    checked_days: int = Field(default=0, description="当月签到天数")
    today_checked: bool = Field(default=False, description="今天是否已签到")


class CheckinStatsOut(BaseModel):
    """签到统计出参。"""

    current_streak: int = Field(default=0, description="当前连续签到天数")
    total_days: int = Field(default=0, description="累计签到天数")
    month_days: int = Field(default=0, description="本月签到天数")
    last_checkin_date: date | None = Field(default=None, description="最近一次签到日期")
    today_checked: bool = Field(default=False, description="今天是否已签到")


# ==================================================================== 消息通知
class NotificationOut(BaseModel):
    """站内通知出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="通知ID")
    title: str = Field(description="标题")
    content: str = Field(description="正文")
    notify_type: str = Field(default="system", description="类型 system/plan/course/comment")
    biz_id: int | None = Field(default=None, description="关联业务ID")
    is_read: bool = Field(default=False, description="是否已读")
    created_at: datetime | None = Field(default=None, description="创建时间")


class UnreadCountOut(BaseModel):
    """未读消息数出参。"""

    unread: int = Field(default=0, description="未读通知条数")


# ==================================================================== 实名认证
class RealNameRequest(BaseModel):
    """提交实名认证入参。"""

    real_name: str = Field(min_length=2, max_length=50, description="真实姓名")
    id_card: str = Field(min_length=15, max_length=18, description="身份证号（入库前会脱敏）")


class RealNameOut(BaseModel):
    """实名认证状态出参（身份证号已脱敏）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="认证记录ID")
    status: str = Field(default=REALNAME_NONE, description="none/pending/approved/rejected")
    real_name: str | None = Field(default=None, description="真实姓名")
    id_card: str | None = Field(default=None, description="身份证号（脱敏）")
    reject_reason: str | None = Field(default=None, description="驳回原因")
    reviewed_at: datetime | None = Field(default=None, description="审核时间")
    created_at: datetime | None = Field(default=None, description="提交时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


__all__ = [
    # 用户
    "UserOut", "ProfileOut", "ProfileUpdateRequest", "AvatarOut",
    # 认证
    "RegisterRequest", "LoginRequest", "AuthOut", "PasswordResetRequest", "PasswordResetConfirmRequest",
    "PhoneBindRequest", "PasswordChangeRequest", "PhoneBindConfirmRequest", "SmsCodeOut",
    # 等级
    "LevelOut", "LevelRuleOut", "LevelRulesOut",
    # 签到
    "CheckinOut", "CalendarDayOut", "CheckinCalendarOut", "CheckinStatsOut",
    # 通知
    "NotificationOut", "UnreadCountOut",
    # 实名
    "RealNameRequest", "RealNameOut",
    # 常量
    "GENDER_UNKNOWN", "GENDER_MALE", "GENDER_FEMALE",
    "REALNAME_NONE", "REALNAME_PENDING", "REALNAME_APPROVED", "REALNAME_REJECTED",
]
