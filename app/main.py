"""恋爱大师 - FastAPI 应用入口

启动：python main.py
或：uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import ai, chat, system
from app.config import settings
from app.core import register_middlewares
from app.rag.document_loader import ensure_directories
from app.utils import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动初始化 / 关闭清理"""
    ensure_directories()
    logger.info("=" * 56)
    logger.info("%s 启动中...", settings.app_name)
    logger.info("环境: %s | 端口: %s", settings.app_env, settings.port)
    logger.info("对话模型: %s", settings.dashscope_chat_model)
    logger.info("大模型配置: %s", "已就绪" if settings.llm_ready else "未配置(仅接口可用)")
    logger.info("=" * 56)
    yield
    logger.info("%s 已关闭", settings.app_name)


app = FastAPI(
    title=f"{settings.app_name} API",
    description=(
        "恋爱大师 —— AI 情感顾问服务\n\n"
        "技术栈：Python 3.12 + FastAPI + LangChain / LangGraph"
    ),
    version=__version__,
    lifespan=lifespan,
)

# 中间件（拦截器）：鉴权 -> 访问日志 -> CORS，见 app/core/middleware.py
register_middlewares(app)

# 注册路由
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(ai.router)


@app.get("/", tags=["系统"], summary="服务根路径")
async def root() -> dict:
    """服务概览"""
    return {
        "app": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/api/health",
    }
