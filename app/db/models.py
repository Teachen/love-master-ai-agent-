"""恋爱大师 - 数据表结构

账号体系（三张）：
- app_user           ：业务用户（一个用户可绑定多种登录方式）
- app_user_identity  ：登录身份（手机号 / 小程序 openid / App 微信 openid ……）
                       同一用户的多个身份通过 user_id 归拢 —— 这就是"账号绑定"
- app_sms_code       ：短信验证码（限频与校验）

对话历史（两张）：
- chat_session：一个会话一行（标题、主题、时间）
- chat_message：一条消息一行（所属会话、角色、内容、顺序）

字符集统一 utf8mb4，支持 emoji（用户消息里很常见）。
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# 登录方式标识
PROVIDER_PHONE = "phone"  # 手机号 + 短信验证码
PROVIDER_WECHAT_MINIAPP = "wechat_miniapp"  # 微信小程序 wx.login
PROVIDER_WECHAT_APP = "wechat_app"  # 微信开放平台移动应用（需企业认证）
PROVIDER_WECHAT_MP = "wechat_mp"  # 微信公众号网页授权


class User(Base):
    """业务用户。

    id 直接作为 chat_session.user_id 使用，因此统一字符串类型。
    手机号冗余存一份（可空）：方便后台检索，登录身份仍以 app_user_identity 为准。
    """

    __tablename__ = "app_user"
    __table_args__ = ({"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},)

    # 32 位 uuid hex
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 昵称/头像：手机号注册时默认「用户1234」，微信登录可带过来
    nickname: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # 头像：存内置头像标识（emoji，如 "❤️"）或图片 URL。
    # 之所以默认用 emoji 而不是要求上传图片：三端都不依赖图床/对象存储，
    # 换设备也能同步；将来接了文件上传，这里换成 URL 即可，字段无需改。
    avatar: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    # ---------- 资料扩展（「我的 → 编辑资料」可改） ----------
    # 统一用空串表示「未填写」，避免 NULL 在各处判断分叉
    gender: Mapped[str] = mapped_column(
        String(8), default="", nullable=False
    )  # male / female / secret / ""
    # 生日存 YYYY-MM-DD 字符串：只用来算星座/年龄提示，不需要时区与 Date 语义
    birthday: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    bio: Mapped[str] = mapped_column(String(200), default="", nullable=False)  # 个性签名
    emotion_status: Mapped[str] = mapped_column(
        String(16), default="", nullable=False
    )  # single / in_love / married / secret / ""
    # 手机号（可空：纯微信登录用户可能没绑手机号）
    phone: Mapped[str] = mapped_column(
        String(20), default="", index=True, nullable=False
    )
    # active / disabled
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    # 数据来源标记：方便区分「游客转正」与「直接注册」
    register_from: Mapped[str] = mapped_column(
        String(24), default="phone", nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class UserIdentity(Base):
    """登录身份 —— 账号绑定的核心表。

    设计要点：
    1. 唯一键是 (provider, app_id, open_id)：微信 openid 只在**单个应用内**唯一，
       不同小程序的 openid 可能撞车，必须带上 app_id 才能全局唯一。
    2. 手机号身份用 provider='phone'、app_id=''、open_id=<手机号>，
       这样"手机号登录"和"微信登录"共用同一套查号逻辑。
    3. union_id 冗余存一份：绑定微信开放平台后可用于跨端（小程序 ↔ App）识别同一人。
    """

    __tablename__ = "app_user_identity"
    __table_args__ = (
        UniqueConstraint("provider", "app_id", "open_id", name="uq_identity"),
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("app_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # phone / wechat_miniapp / wechat_app / wechat_mp
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    # 微信侧应用标识（小程序 AppID / 移动应用 AppID）；手机号身份为空串
    app_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # 手机号 or 微信 openid
    open_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # 微信 unionid（跨应用唯一，需绑定开放平台才有；手机号身份为空）
    union_id: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    # 最近一次登录的 session_key（用于解密手机号/加密数据；仅微信身份有）
    session_key: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class SmsCode(Base):
    """短信验证码。落库是为了做校验、限频与审计。"""

    __tablename__ = "app_sms_code"
    __table_args__ = ({"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    phone: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    # login=登录 / bind=绑定手机号
    scene: Mapped[str] = mapped_column(String(16), default="login", nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class ChatSession(Base):
    """会话"""

    __tablename__ = "chat_session"
    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},
    )

    # 会话 ID（前端生成，形如 love-20260925-xxxx）
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 预留：多用户时按 user_id 隔离，当前统一 "default"
    user_id: Mapped[str] = mapped_column(
        String(64), default="default", index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), default="新对话", nullable=False)
    theme: Mapped[str] = mapped_column(String(16), default="love", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, index=True, nullable=False
    )


class ChatMessage(Base):
    """会话中的一条消息"""

    __tablename__ = "chat_message"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_session_seq"),
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB"},
    )

    # sqlite 只有 INTEGER PRIMARY KEY 才自增，BIGINT 会被当成普通非空列导致插入失败；
    # 用 with_variant 让 MySQL 用 BIGINT、sqlite 用 INTEGER，两种库都正确
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_session.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 消息在会话内的顺序（1 起）
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 展示用的时间标签（HH:MM），后端生成 PDF 时直接输出
    time_label: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
