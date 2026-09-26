"""恋爱大师 - 对话历史接口（MySQL 持久化）

接口一览（前缀 /api/history）：
- GET    /                     列表（可按 theme 过滤）
- GET    /{session_id}         详情（含消息）
- PUT    /{session_id}         整段保存（upsert，幂等）
- DELETE /{session_id}         删除
- DELETE /                     清空
- POST   /{session_id}/export-pdf  按库里的数据导出 PDF

用户归属规则（配合账号体系）：
- 带有效登录态 → user_id 一律取 token 里的真实用户，忽略请求参数（防越权）
- 未登录（游客）→ 取请求里的 user_id，缺省 "default"，仅本机可见
- 已存在的会话只能被其归属者读写，跨用户访问返回 404（不泄露存在性）

数据库不可用时（MYSQL_ENABLED=false 或连不上）：
- 写操作返回 503 + `{"detail": "..."}`，前端据此回退本地存储
- 读操作返回 `{"available": false, "items": []}`
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.core.auth import get_optional_user_id, is_guest_id
from app.core.chat_pdf import render_chat_pdf
from app.db import ChatMessage, ChatSession, db_ready, session_scope
from app.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/history", tags=["对话历史"])

# 列表默认条数上限
_MAX_LIMIT = 100

# 游客空间默认 ID（前端未生成游客标识时使用，兼容历史数据）
DEFAULT_GUEST_ID = "default"


# ----------------------------- Schemas ----------------------------- #
class HistoryMessageIn(BaseModel):
    role: Literal["user", "ai", "assistant", "system"] = "user"
    content: str = ""
    time: str = ""


class SessionIn(BaseModel):
    """整段保存的请求体：幂等 upsert（先删旧消息再插入）"""

    title: str = Field(default="新对话")
    theme: str = Field(default="love")
    user_id: str = Field(default="default")
    # 前端传来的本地时间戳字符串（可选），缺省用服务端时间
    updated_at: str = Field(default="")
    messages: list[HistoryMessageIn] = Field(default_factory=list)


class MessageOut(BaseModel):
    role: str
    content: str
    time: str


class SessionOut(BaseModel):
    id: str
    title: str
    theme: str
    created_at: str
    updated_at: str
    preview: str = ""
    msg_count: int = 0
    messages: list[MessageOut] = Field(default_factory=list)


# ----------------------------- 工具 ----------------------------- #
def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _parse_time(text: str, fallback: datetime) -> datetime:
    """解析前端传入的时间字符串，失败则用服务端时间"""
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return fallback


def _preview(messages: list[ChatMessage]) -> str:
    if not messages:
        return ""
    last = messages[-1]
    prefix = "我：" if last.role == "user" else "AI："
    text = (last.content or "").replace("\n", " ").strip()
    return prefix + (text[:40] + "…" if len(text) > 40 else text)


def _require_db() -> None:
    if not db_ready():
        raise HTTPException(status_code=503, detail="对话历史存储未启用（MySQL 不可用）")


def _owner(current: str, fallback: str) -> str:
    """确定本次请求的数据归属者。

    - 已登录：一律以 token 里的用户为准，忽略请求参数（防越权写别人账号）
    - 未登录：只允许落在「游客空间」（default / guest-xxx）。
      否则任何人只要把 user_id 改成别人的账号 ID，就能读写他人对话历史。
    """
    if current:
        return current
    fb = (fallback or "").strip()
    if fb and not is_guest_id(fb):
        logger.warning("游客尝试访问账号空间 user_id=%s，已拒绝", fb)
        raise HTTPException(status_code=403, detail="未登录状态只能访问本机游客数据")
    return fb or DEFAULT_GUEST_ID


def _assert_owner(session: ChatSession, owner: str) -> None:
    """会话只能被归属者访问；跨用户一律按不存在处理。"""
    if session.user_id != owner:
        raise HTTPException(status_code=404, detail="会话不存在")


# ----------------------------- 接口 ----------------------------- #
@router.get("", summary="历史会话列表")
def list_sessions(
    theme: str = Query(default="", description="按主题过滤：love / manus"),
    user_id: str = Query(default=DEFAULT_GUEST_ID, description="游客空间 ID（已登录时忽略）"),
    limit: int = Query(default=50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    current: str = Depends(get_optional_user_id),
) -> dict:
    if not db_ready():
        return {"available": False, "items": [], "detail": "MySQL 未启用，请用本地存储"}

    owner = _owner(current, user_id)
    with session_scope() as db:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == owner)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if theme:
            stmt = stmt.where(ChatSession.theme == theme)
        sessions = list(db.scalars(stmt))

        items = []
        for s in sessions:
            msgs = list(
                db.scalars(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == s.id)
                    .order_by(ChatMessage.seq)
                )
            )
            items.append(
                {
                    "id": s.id,
                    "title": s.title,
                    "theme": s.theme,
                    "updatedAt": _fmt(s.updated_at),
                    "preview": _preview(msgs),
                    "msgCount": sum(1 for m in msgs if m.role == "user"),
                }
            )
    return {"available": True, "items": items, "owner": owner}


@router.get("/{session_id}", summary="历史会话详情")
def get_session(
    session_id: str,
    user_id: str = Query(default=DEFAULT_GUEST_ID, description="游客空间 ID（已登录时忽略）"),
    current: str = Depends(get_optional_user_id),
) -> dict:
    if not db_ready():
        return {"available": False, "detail": "MySQL 未启用，请用本地存储"}
    owner = _owner(current, user_id)
    with session_scope() as db:
        s = db.get(ChatSession, session_id)
        if not s:
            raise HTTPException(status_code=404, detail="会话不存在")
        _assert_owner(s, owner)
        msgs = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == s.id)
                .order_by(ChatMessage.seq)
            )
        )
        return {
            "available": True,
            "id": s.id,
            "title": s.title,
            "theme": s.theme,
            "createdAt": _fmt(s.created_at),
            "updatedAt": _fmt(s.updated_at),
            "preview": _preview(msgs),
            "msgCount": sum(1 for m in msgs if m.role == "user"),
            "messages": [
                {"role": m.role, "content": m.content, "time": m.time_label}
                for m in msgs
            ],
        }


@router.put("/{session_id}", summary="保存整段会话（upsert）")
def save_session(
    session_id: str,
    payload: SessionIn,
    current: str = Depends(get_optional_user_id),
) -> dict:
    _require_db()
    now = datetime.now()
    # 归属者以登录态为准：防止前端伪造 user_id 把数据写进别人账号
    owner = _owner(current, payload.user_id)
    with session_scope() as db:
        s = db.get(ChatSession, session_id)
        if s is None:
            s = ChatSession(
                id=session_id,
                user_id=owner,
                title=payload.title,
                theme=payload.theme,
                created_at=now,
            )
            db.add(s)
        else:
            _assert_owner(s, owner)
            s.title = payload.title or s.title
            s.theme = payload.theme or s.theme
        s.updated_at = _parse_time(payload.updated_at, now)

        # 幂等：先清空该会话旧消息，再按序插入
        db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        for idx, m in enumerate(payload.messages, start=1):
            if not m.content:
                continue
            db.add(
                ChatMessage(
                    session_id=session_id,
                    seq=idx,
                    role=m.role,
                    content=m.content,
                    time_label=m.time,
                )
            )
    return {"ok": True, "id": session_id, "saved": len(payload.messages), "owner": owner}


@router.delete("/{session_id}", summary="删除会话")
def delete_session(
    session_id: str,
    user_id: str = Query(default=DEFAULT_GUEST_ID, description="游客空间 ID（已登录时忽略）"),
    current: str = Depends(get_optional_user_id),
) -> dict:
    _require_db()
    owner = _owner(current, user_id)
    with session_scope() as db:
        s = db.get(ChatSession, session_id)
        if s is not None:
            _assert_owner(s, owner)
            db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
            db.delete(s)
    return {"ok": True, "id": session_id}


@router.delete("", summary="清空全部会话")
def clear_sessions(
    user_id: str = Query(default=DEFAULT_GUEST_ID, description="游客空间 ID（已登录时忽略）"),
    current: str = Depends(get_optional_user_id),
) -> dict:
    _require_db()
    owner = _owner(current, user_id)
    with session_scope() as db:
        ids = list(
            db.scalars(select(ChatSession.id).where(ChatSession.user_id == owner))
        )
        if ids:
            db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(ids)))
            db.execute(delete(ChatSession).where(ChatSession.user_id == owner))
    return {"ok": True, "deleted": len(ids)}


@router.post("/{session_id}/export-pdf", summary="按库里的记录导出 PDF")
def export_session_pdf(
    session_id: str,
    user_id: str = Query(default=DEFAULT_GUEST_ID, description="游客空间 ID（已登录时忽略）"),
    current: str = Depends(get_optional_user_id),
) -> dict:
    """与 POST /api/ai/chat/export-pdf 的区别：本接口直接从数据库取消息，
    前端无需把整段对话回传（省流量，且以服务端数据为准）。"""
    _require_db()
    owner = _owner(current, user_id)
    with session_scope() as db:
        s = db.get(ChatSession, session_id)
        if not s:
            raise HTTPException(status_code=404, detail="会话不存在")
        _assert_owner(s, owner)
        msgs = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == s.id)
                .order_by(ChatMessage.seq)
            )
        )
        if not msgs:
            return {"ok": False, "detail": "该会话没有可导出的内容"}
        payload = [
            {"role": m.role, "content": m.content, "time": m.time_label} for m in msgs
        ]
        title = s.title

    path = render_chat_pdf(messages=payload, title=title, chat_id=session_id)
    return {"ok": True, "url": f"/api/files/{path.name}", "filename": path.name}
