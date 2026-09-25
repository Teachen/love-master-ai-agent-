"""恋爱大师 - 会话记忆管理

对应 Java 版 FileBasedChatMemory，用文件持久化多轮对话历史。
"""
import json
import os
import threading
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.utils import get_logger

logger = get_logger(__name__)

_DEFAULT_MEMORY_DIR = Path("./tmp/memory")


def _resolve_memory_dir() -> Path:
    """解析记忆存储目录。

    支持 MEMORY_DIR 环境变量覆盖，便于测试把数据写到临时目录，
    避免污染真实的 ./tmp/memory/。
    """
    override = os.getenv("MEMORY_DIR")
    return Path(override) if override else _DEFAULT_MEMORY_DIR


MEMORY_DIR = _resolve_memory_dir()


class FileChatMemory:
    """基于文件的会话记忆（按 session_id 隔离）"""

    def __init__(self, session_id: str, max_messages: int = 20, save_dir: Path | None = None):
        self.session_id = session_id
        self.max_messages = max_messages
        self.save_dir = Path(save_dir) if save_dir else _resolve_memory_dir()
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.save_dir / f"{_safe_session_id(session_id)}.json"
        self._messages: List[BaseMessage] = self._load()

    # ---------- 持久化 ----------
    def _load(self) -> List[BaseMessage]:
        if not self.file_path.exists():
            return []
        try:
            raw = json.loads(self.file_path.read_text(encoding="utf-8"))
            return [_to_message(item) for item in raw]
        except Exception as exc:  # noqa: BLE001
            logger.warning("会话记忆读取失败(%s)，已重置", exc)
            return []

    def _save(self) -> None:
        data = [
            {
                "type": "human" if isinstance(m, HumanMessage) else "ai",
                "content": m.content,
            }
            for m in self._messages
        ]
        self.file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------- 读写接口 ----------
    def add_user_message(self, content: str) -> None:
        self._messages.append(HumanMessage(content=content))
        self._trim()
        self._save()

    def add_ai_message(self, content: str) -> None:
        self._messages.append(AIMessage(content=content))
        self._trim()
        self._save()

    def get_messages(self) -> List[BaseMessage]:
        return list(self._messages)

    def get_history_text(self) -> str:
        """把历史拼成纯文本，注入提示词使用"""
        if not self._messages:
            return "（暂无历史对话）"
        role_map = {HumanMessage: "用户", AIMessage: "恋爱大师"}
        return "\n".join(
            f"{role_map.get(type(m), '未知')}：{m.content}" for m in self._messages
        )

    def clear(self) -> None:
        self._messages = []
        self._save()

    def _trim(self) -> None:
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]


def _safe_session_id(session_id: str) -> str:
    return "".join(c for c in session_id if c.isalnum() or c in "-_") or "default"


def _to_message(item: dict) -> BaseMessage:
    if item.get("type") == "human":
        return HumanMessage(content=item.get("content", ""))
    return AIMessage(content=item.get("content", ""))


# ---------- 会话记忆池 ----------
_memory_pool: Dict[str, FileChatMemory] = {}
_pool_lock = threading.Lock()


def get_chat_memory(session_id: str) -> FileChatMemory:
    """获取（或创建）指定会话的记忆对象"""
    with _pool_lock:
        if session_id not in _memory_pool:
            _memory_pool[session_id] = FileChatMemory(session_id)
        return _memory_pool[session_id]


def clear_chat_memory(session_id: str) -> None:
    """清空指定会话的记忆，并从池中移除"""
    memory = get_chat_memory(session_id)
    memory.clear()
    with _pool_lock:
        _memory_pool.pop(session_id, None)


def reset_memory_pool() -> None:
    """清空整个记忆池（仅测试与调试使用）。

    改了 MEMORY_DIR 之后必须调用它，否则池中旧实例仍指向旧目录。
    """
    with _pool_lock:
        _memory_pool.clear()
