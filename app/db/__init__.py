"""恋爱大师 - 数据库层

对外只暴露 init_db / db_ready / session_scope 与 ORM 模型，
调用方（接口层）无需关心连接细节。
"""
from app.db.database import Base, db_ready, init_db, session_scope
from app.db.models import (
    PROVIDER_PHONE,
    PROVIDER_WECHAT_APP,
    PROVIDER_WECHAT_MINIAPP,
    PROVIDER_WECHAT_MP,
    ChatMessage,
    ChatSession,
    SmsCode,
    User,
    UserIdentity,
)

__all__ = [
    "Base",
    "init_db",
    "db_ready",
    "session_scope",
    "ChatSession",
    "ChatMessage",
    "User",
    "UserIdentity",
    "SmsCode",
    "PROVIDER_PHONE",
    "PROVIDER_WECHAT_MINIAPP",
    "PROVIDER_WECHAT_APP",
    "PROVIDER_WECHAT_MP",
]
