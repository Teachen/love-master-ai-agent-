"""恋爱大师 - 核心组件包

存放横切关注点：HTTP 中间件（拦截器）、登录态签发校验、LLM 调用日志、报告 PDF 渲染等。
"""
from app.core.auth import (
    create_token,
    decode_token,
    get_current_user_id,
    get_optional_user_id,
    is_valid_phone,
    mask_phone,
    normalize_phone,
)
from app.core.llm_logging import LLMLoggingHandler, get_llm_logging_handler
from app.core.middleware import AccessLogMiddleware, ApiKeyMiddleware, register_middlewares
from app.core.report_pdf import render_report_pdf

__all__ = [
    "LLMLoggingHandler",
    "get_llm_logging_handler",
    "AccessLogMiddleware",
    "ApiKeyMiddleware",
    "register_middlewares",
    "render_report_pdf",
    "create_token",
    "decode_token",
    "get_current_user_id",
    "get_optional_user_id",
    "is_valid_phone",
    "mask_phone",
    "normalize_phone",
]
