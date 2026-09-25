"""恋爱大师 - 核心组件包

存放横切关注点：HTTP 中间件（拦截器）、LLM 调用日志、报告 PDF 渲染等。
"""
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
]
