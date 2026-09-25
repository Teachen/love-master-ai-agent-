"""恋爱大师 - HTTP 中间件（对应 Java 的拦截器层）

提供两个拦截器：
- ApiKeyMiddleware     前置鉴权：校验 X-API-Key 请求头（对应拦截器 preHandle）
- AccessLogMiddleware  访问日志：记录方法、路径、状态码、耗时（对应 afterCompletion）

注册顺序（add_middleware 后添加的在最外层）：
    ApiKey(内) -> AccessLog(中) -> CORS(外)
请求执行顺序：CORS -> AccessLog -> ApiKey -> 路由
效果：跨域预检由 CORS 最先处理不被鉴权拦截；所有请求（含 401）都会被访问日志记录。
"""
import hmac
import time
from typing import Sequence

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.utils import get_logger

logger = get_logger("app.access")

# 免鉴权路径前缀：文档 / 健康检查 / 静态杂项
_PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/api/health", "/favicon.ico")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """前置鉴权拦截器。

    规则：
    - settings.api_key_enabled=False 时全部放行（本地开发默认）
    - 只保护 /api/* 业务接口；文档、健康检查、OPTIONS 预检、非 /api 路径放行
    - 请求头 X-API-Key 与配置的任一 Key 匹配即通过
    - 未配置任何 Key 时一律拒绝，防止"开了开关忘了配 Key"导致裸奔
    """

    def __init__(self, app, exempt_prefixes: Sequence[str] = _PUBLIC_PREFIXES):
        super().__init__(app)
        self.exempt_prefixes = tuple(exempt_prefixes)

    async def dispatch(self, request: Request, call_next):
        if not settings.api_key_enabled:
            return await call_next(request)

        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/")
            or path.startswith(self.exempt_prefixes)
        ):
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if self._is_valid(provided):
            return await call_next(request)

        logger.warning("鉴权失败 %s %s", request.method, path)
        return JSONResponse(
            status_code=401,
            content={"detail": "无效的 API Key，请在请求头 X-API-Key 中携带"},
        )

    @staticmethod
    def _is_valid(provided: str) -> bool:
        keys = settings.api_key_list
        if not keys:
            return False
        # 恒定时间比较，防时序攻击
        return any(hmac.compare_digest(provided, key) for key in keys)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """访问日志拦截器：一行请求一条，含状态码与耗时。"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            cost = (time.perf_counter() - start) * 1000
            logger.error(
                "请求异常 %s %s (%.0f ms)", request.method, request.url.path, cost
            )
            raise
        cost = (time.perf_counter() - start) * 1000
        logger.info(
            "请求完成 %s %s -> %s (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            cost,
        )
        response.headers["X-Process-Time-Ms"] = f"{cost:.0f}"
        return response


def register_middlewares(app: FastAPI) -> None:
    """统一注册中间件，调用方无需关心顺序。"""
    # 注意顺序：后添加的在最外层。执行顺序 = CORS -> 访问日志 -> 鉴权 -> 路由
    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    mode = "开启" if settings.api_key_enabled else "关闭"
    logger.info(
        "中间件注册完成 | 鉴权: %s | 免鉴权前缀: %s", mode, ", ".join(_PUBLIC_PREFIXES)
    )
