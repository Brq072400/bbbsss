"""FitTrack 全局配置。

所有配置项均可通过环境变量或 backend/.env 覆盖，命名规则：字段名大写。
例如 DATABASE_URL、JWT_SECRET、UPLOAD_DIR。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置（pydantic-settings 会自动读取 .env 与环境变量）。"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 基础信息 ----------
    APP_NAME: str = "FitTrack 健身系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api"

    # ---------- 数据库 ----------
    # 生产环境示例：mysql+pymysql://root:123456@127.0.0.1:3306/fittrack?charset=utf8mb4
    # 本地零依赖演示：sqlite:///./fittrack.db
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'fittrack.db').as_posix()}"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ---------- JWT ----------
    JWT_SECRET: str = "fittrack-dev-secret-please-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7          # 普通用户令牌有效期：7 天
    ADMIN_JWT_EXPIRE_MINUTES: int = 60 * 12        # 管理员令牌有效期：12 小时

    # ---------- 密码哈希（PBKDF2-HMAC-SHA256，标准库实现，无需额外依赖） ----------
    PBKDF2_ITERATIONS: int = 200_000

    # ---------- 上传 ----------
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    UPLOAD_URL_PREFIX: str = "/static/uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024         # 单文件 5MB
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp,image/gif"

    # ---------- 业务参数 ----------
    CHECKIN_POINTS: int = 10                       # 每日签到基础积分
    CHECKIN_STREAK_BONUS: int = 5                  # 连续签到每天额外奖励积分
    CHECKIN_STREAK_BONUS_CAP: int = 30             # 连续奖励上限
    # 等级门槛：积分达到阈值即升级
    LEVEL_THRESHOLDS: list[int] = [0, 100, 300, 600, 1000, 1600, 2400, 3500, 5000, 7000, 10000]

    # ---------- 默认管理员（首次启动自动创建） ----------
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123456"

    @property
    def is_sqlite(self) -> bool:
        """是否使用 SQLite（决定连接池参数是否可用）。"""
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def allowed_image_types(self) -> set[str]:
        """允许上传的图片 MIME 集合。"""
        return {t.strip() for t in self.ALLOWED_IMAGE_TYPES.split(",") if t.strip()}


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一配置实例（带缓存，避免重复解析 .env）。"""
    return Settings()


settings = get_settings()
