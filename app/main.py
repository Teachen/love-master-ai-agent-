"""恋爱大师 - FastAPI 应用入口

启动：python main.py
或：uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import ai, auth, chat, history, system
from app.config import settings
from app.core import register_middlewares
from app.db.database import init_db
from app.rag.document_loader import ensure_directories
from app.utils import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动初始化 / 关闭清理"""
    ensure_directories()
    # 对话历史库：未启用或连不上时降级，不影响主流程
    init_db()
    _log_startup_banner()
    yield
    logger.info("%s 已关闭", settings.app_name)


def _log_startup_banner() -> None:
    """启动横幅：把「当前是什么环境、配置从哪来、有没有危险项」一次说清。

    排查「我改了配置怎么不生效」时，先看这里的「配置文件」一行 ——
    少了 .env.prod 或者环境名不对，答案通常就写在上面。
    """
    env_files = settings.env_files_loaded
    files_text = " → ".join(env_files) if env_files else "（无，全部来自系统环境变量）"

    logger.info("=" * 60)
    logger.info("%s 启动中...", settings.app_name)
    logger.info("运行环境: %s%s", settings.app_env, "（生产）" if settings.is_production else "")
    logger.info("配置文件: %s", files_text)
    logger.info("监听地址: %s:%s | 调试模式: %s", settings.host, settings.port, settings.debug)
    logger.info("对话模型: %s", settings.dashscope_chat_model)
    logger.info("大模型配置: %s", "已就绪" if settings.llm_ready else "未配置(仅接口可用)")
    logger.info(
        "RAG 数据源: %s（请求 %s）",
        settings.rag_mode,
        settings.rag_backend,
    )
    logger.info(
        "对话历史存储: %s",
        "MySQL" if settings.mysql_enabled else "未启用(由前端本地存储承担)",
    )
    logger.info(
        "账号体系: %s | 短信通道: %s | Token 密钥: %s",
        "开启" if settings.auth_enabled else "关闭",
        settings.sms_provider,
        "内置开发密钥" if settings.jwt_secret_is_default else "已配置",
    )
    logger.info("=" * 60)

    # 生产环境才校验；开发环境这几项本来就是「不安全」的，没必要刷屏
    for warning in settings.config_warnings:
        logger.warning("⚠️  配置告警：%s", warning)
    # 密钥类告警只进日志、不进 HTTP 响应（对外说"你在用默认密钥"等于送人后门）
    if settings.jwt_warning:
        logger.error("🔒 安全告警：%s", settings.jwt_warning)
    if settings.config_warnings or settings.jwt_warning:
        logger.warning("⚠️  以上告警不影响启动，但上线前应逐条确认（见 docs/环境配置说明.md）")


app = FastAPI(
    title=f"{settings.app_name} API",
    description=(
        "恋爱大师 —— AI 情感顾问服务\n\n"
        "技术栈：Python 3.12 + FastAPI + LangChain / LangGraph"
    ),
    version=__version__,
    lifespan=lifespan,
    # 关闭默认文档路由（默认会从 cdn.jsdelivr.net 加载 Swagger UI，
    # 国内网络经常加载失败导致 /docs 白屏），下方用本地静态资源自建
    docs_url=None,
    redoc_url=None,
)

# 中间件（拦截器）：鉴权 -> 访问日志 -> CORS，见 app/core/middleware.py
register_middlewares(app)

# 注册路由
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(history.router)
app.include_router(auth.router)

# ---------- 接口文档（Swagger UI 资源自托管，不走国外 CDN） ----------
_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# 导出文件访问目录：对话记录导出 PDF 后返回 /api/files/<文件名>，
# 前端拼接服务地址即可下载（容器重启会丢失，仅作临时中转）
_PDF_DIR = Path(settings.pdf_save_dir)
_PDF_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/files", StaticFiles(directory=_PDF_DIR), name="files")


@app.get("/docs", include_in_schema=False, summary="Swagger UI 接口文档")
async def swagger_ui():
    """文档页面：JS/CSS 均来自镜像内 /static，国内网络直连可用"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/docs/swagger-ui-bundle.js",
        swagger_css_url="/static/docs/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    """Swagger UI OAuth2 重定向页（框架约定路径，保留默认实现）"""
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/", tags=["系统"], summary="服务根路径")
async def root() -> dict:
    """服务概览"""
    return {
        "app": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/health",
    }
