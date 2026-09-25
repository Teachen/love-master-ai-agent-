"""恋爱大师 - LLM 调用日志（对应 Java 版 MyLoggerAdvisor）

以 CallbackHandler 形式注入到所有模型实例，成对打印：
    [LLM请求 run=xxxxxxxx] system: ...
    [LLM请求 run=xxxxxxxx] human: ...
    [LLM响应 run=xxxxxxxx] ...

用途：排查「Prompt 到底长什么样」「多轮记忆是否生效」「响应质量如何」。
消息与响应按 settings.llm_log_max_chars 截断，避免刷屏。
"""
from typing import Any, List, Optional

from langchain_core.callbacks import BaseCallbackHandler

from app.config import settings
from app.utils import get_logger

logger = get_logger("app.llm_advisor")


def _clip(text: str, limit: int) -> str:
    """压缩空白并截断，控制单条日志长度"""
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


class LLMLoggingHandler(BaseCallbackHandler):
    """LLM 请求/响应日志处理器（不阻断执行链路）"""

    raise_error = False

    # ---------- 请求 ----------
    def on_chat_model_start(
        self,
        serialized: Optional[dict],
        messages: List[List[Any]],
        run_id=None,
        **kwargs,
    ) -> None:
        if not settings.llm_log_enabled:
            return
        rid = _run_id(run_id)
        limit = settings.llm_log_max_chars
        for group in messages:
            for message in group:
                role = getattr(message, "type", "message")
                content = getattr(message, "content", message)
                logger.info(
                    "[LLM请求 run=%s] %s: %s", rid, role, _clip(content, limit)
                )

    # ---------- 响应 ----------
    def on_llm_end(self, response: Any, run_id=None, **kwargs) -> None:
        if not settings.llm_log_enabled:
            return
        rid = _run_id(run_id)
        limit = settings.llm_log_max_chars
        for gen_group in getattr(response, "generations", None) or []:
            for gen in gen_group:
                text = getattr(gen, "text", None) or str(gen)
                logger.info("[LLM响应 run=%s] %s", rid, _clip(text, limit))

    # ---------- 异常 ----------
    def on_llm_error(self, error: BaseException, run_id=None, **kwargs) -> None:
        logger.error("[LLM错误 run=%s] %s", _run_id(run_id), error)


def _run_id(run_id) -> str:
    return str(run_id)[:8] if run_id else "-"


_handler: Optional[LLMLoggingHandler] = None


def get_llm_logging_handler() -> LLMLoggingHandler:
    """获取处理器单例（工厂注入用）"""
    global _handler
    if _handler is None:
        _handler = LLMLoggingHandler()
    return _handler
