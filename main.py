"""恋爱大师 - 启动脚本

用法：
    python main.py                  # 常规启动（debug 模式下开热重载）
    RELOAD=false python main.py     # 断点调试启动（必须关热重载，否则断点不生效）

可用环境变量：
    RELOAD     覆盖热重载开关，优先级高于 .env 中的 DEBUG
    LLM_DEBUG  true 时打印发送给大模型的完整 Prompt / 响应
"""
import os

import uvicorn

from app.config import settings
from app.utils import setup_logging


def _reload_enabled() -> bool:
    """是否开启热重载。

    断点调试时必须关闭：reload 会额外拉起一个子进程，调试器默认只附着
    主进程，断点永远不会命中。显式设置 RELOAD 时以其为准，否则沿用 DEBUG。
    """
    override = os.getenv("RELOAD")
    if override is None:
        return settings.debug
    return override.strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    setup_logging()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=_reload_enabled(),
        log_level="debug" if settings.debug else "info",
    )
