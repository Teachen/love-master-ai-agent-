"""恋爱大师 - 大模型工厂

统一产出对话模型 / 向量模型 / Ollama 本地模型实例。
"""
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import settings
from app.core.llm_logging import get_llm_logging_handler
from app.utils import get_logger

logger = get_logger(__name__)

# 阿里云百炼兼容 OpenAI 协议的接入点
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def get_chat_model(
    model: Optional[str] = None,
    temperature: float = 0.7,
    streaming: bool = False,
    **kwargs,
) -> ChatOpenAI:
    """获取对话模型（默认阿里云百炼 Qwen）

    自动注入 LLM 调用日志处理器（对应 Java MyLoggerAdvisor），
    可通过 LLM_LOG_ENABLED=false 关闭。
    """
    if not settings.llm_ready:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未配置，请在 .env 中填写后再调用大模型能力"
        )
    model_name = model or settings.dashscope_chat_model
    logger.info("初始化对话模型: %s", model_name)
    if settings.llm_log_enabled:
        kwargs.setdefault("callbacks", [get_llm_logging_handler()])
    return ChatOpenAI(
        model=model_name,
        api_key=settings.dashscope_api_key,
        base_url=DASHSCOPE_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        **kwargs,
    )


def get_embedding_model(model: Optional[str] = None) -> OpenAIEmbeddings:
    """获取向量模型"""
    if not settings.llm_ready:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未配置，请在 .env 中填写后再调用向量化能力"
        )
    model_name = model or settings.dashscope_embedding_model
    logger.info("初始化向量模型: %s", model_name)
    return OpenAIEmbeddings(
        model=model_name,
        api_key=settings.dashscope_api_key,
        base_url=DASHSCOPE_BASE_URL,
        check_embedding_ctx_length=False,
    )


def get_ollama_chat_model(model: Optional[str] = None, temperature: float = 0.7):
    """获取 Ollama 本地对话模型（需本地已部署 Ollama）"""
    from langchain_community.chat_models import ChatOllama

    model_name = model or settings.ollama_chat_model
    logger.info("初始化 Ollama 模型: %s", model_name)
    return ChatOllama(
        model=model_name,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )
