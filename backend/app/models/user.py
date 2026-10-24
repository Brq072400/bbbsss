"""用户相关模型：用户、管理员、签到、消息通知、实名认证、验证码。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """用户表：账号、资料、等级、状态。"""

    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")
    nickname: Mapped[str | None] = mapped_column(String(50), comment="昵称")
    avatar: Mapped[str | None] = mapped_column(String(255), comment="头像URL")
    gender: Mapped[int] = mapped_column(Integer, default=0, comment="性别 0未知 1男 2女")
    birthday: Mapped[date | None] = mapped_column(Date, comment="生日")
    height: Mapped[float | None] = mapped_column(comment="身高cm")
    target_weight: Mapped[float | None] = mapped_column(comment="目标体重kg")
    signature: Mapped[str | None] = mapped_column(String(200), comment="个性签名")
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, comment="手机号")
    email: Mapped[str | None] = mapped_column(String(120), unique=True, index=True, comment="邮箱")
    city: Mapped[str | None] = mapped_column(String(50), comment="城市")

    points: Mapped[int] = mapped_column(Integer, default=0, comment="总积分（决定等级）")
    level: Mapped[int] = mapped_column(Integer, default=1, comment="用户等级 1-10")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已实名认证")
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否被封禁")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后登录时间")

    # 关系
    checkins: Mapped[list["CheckinRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    real_name_auth: Mapped["RealNameAuth | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    @property
    def display_name(self) -> str:
        """展示名：优先昵称，其次用户名。"""
        return self.nickname or self.username


class Admin(Base, TimestampMixin):
    """后台管理员表。"""

    __tablename__ = "admins"
    __table_args__ = {"comment": "后台管理员表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="管理员ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="登录名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")
    real_name: Mapped[str | None] = mapped_column(String(50), comment="真实姓名")
    role: Mapped[str] = mapped_column(String(20), default="admin", comment="角色 super/admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后登录时间")


class CheckinRecord(Base, TimestampMixin):
    """签到记录：每人每天最多一条。"""

    __tablename__ = "checkin_records"
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_checkin_user_date"),
        {"comment": "每日签到记录"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="用户ID")
    checkin_date: Mapped[date] = mapped_column(Date, index=True, nullable=False, comment="签到日期")
    streak: Mapped[int] = mapped_column(Integer, default=1, comment="签到时连续天数")
    points_awarded: Mapped[int] = mapped_column(Integer, default=0, comment="本次获得积分")

    user: Mapped[User] = relationship(back_populates="checkins")


class Notification(Base, TimestampMixin):
    """站内消息通知。"""

    __tablename__ = "notifications"
    __table_args__ = {"comment": "消息通知表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="接收人")
    title: Mapped[str] = mapped_column(String(120), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="正文")
    notify_type: Mapped[str] = mapped_column(String(30), default="system", comment="类型 system/plan/course/comment")
    biz_id: Mapped[int | None] = mapped_column(Integer, comment="关联业务ID")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, comment="是否已读")

    user: Mapped[User] = relationship(back_populates="notifications")


class RealNameAuth(Base, TimestampMixin):
    """实名认证申请（一人一条，可重复提交覆盖）。"""

    __tablename__ = "real_name_auths"
    __table_args__ = (UniqueConstraint("user_id", name="uq_realname_user"), {"comment": "实名认证表"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    real_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="真实姓名")
    id_card: Mapped[str] = mapped_column(String(30), nullable=False, comment="身份证号（存储时脱敏）")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, comment="pending/approved/rejected")
    reject_reason: Mapped[str | None] = mapped_column(String(200), comment="驳回原因")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="审核时间")

    user: Mapped[User] = relationship(back_populates="real_name_auth")


class SmsCode(Base, TimestampMixin):
    """短信/邮件验证码（绑定手机号、重置密码共用）。"""

    __tablename__ = "sms_codes"
    __table_args__ = {"comment": "验证码表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(120), index=True, nullable=False, comment="手机号或邮箱")
    code: Mapped[str] = mapped_column(String(10), nullable=False, comment="验证码")
    scene: Mapped[str] = mapped_column(String(30), nullable=False, comment="用途 bind_phone/reset_password")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
    used: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已使用")
