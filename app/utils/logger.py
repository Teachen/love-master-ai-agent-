"""恋爱大师 - 统一日志配置

环境变量：
    LLM_DEBUG  true/1/yes 时开启 LangChain 详细日志，
               会打印每次大模型调用实际发送的完整 messages。
"""
import logging
import os
import sys

from app.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

# DEBUG 级别下噪音过大的第三方库，默认降噪到 WARNING。
# openai._base_client 会逐条打印请求 URL / headers，必须压掉，
# 否则控制台对话会被日志淹没，完全看不到回答。
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "asyncio",
    "dashscope",
    "openai",
    "openai._base_client",
    "langsmith",
    "sqlalchemy.engine",
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def setup_logging() -> None:
    """初始化全局日志

    日志级别策略：
      - 应用自身 logger 按 settings.debug 决定（DEBUG / INFO）
      - 第三方库统一降到 WARNING，避免请求细节刷屏
      - 需要看 HTTP 层细节时用 LLM_DEBUG=1 单独放开
    """
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=logging.WARNING,  # 根 logger 保守起步，逐个放开
        format=_LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # 应用自身的包按实际级别输出
    logging.getLogger("app").setLevel(level)
    logging.getLogger("__main__").setLevel(level)

    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if _truthy(os.getenv("LLM_DEBUG")):
        enable_llm_debug()


def enable_llm_debug() -> None:
    """开启 LangChain 详细日志。

    会打印每次 LLM 调用实际发送的完整 messages（含 system / 历史 / 本轮输入），
    是排查「多轮对话记忆是否生效」「Prompt 到底长什么样」最直接的手段。

    注意：langchain-core 0.3.x 的 globals 不读环境变量，只能走代码 API，
    所以这里显式调用 set_verbose，而不是依赖 LANGCHAIN_VERBOSE。
    """
    from langchain_core.globals import set_verbose

    set_verbose(True)

    # 放开 HTTP 层噪音，便于观察请求细节
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.INFO)

    logging.getLogger(__name__).warning("LLM 详细日志已开启，将打印完整 Prompt")


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger"""
    return logging.getLogger(name)
