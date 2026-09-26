"""恋爱大师 - 应用配置包

除了 settings 单例，还导出环境解析工具：
- ENV_NAME / SUPPORTED_ENVS  当前环境名与支持的环境列表
- PROJECT_ROOT               项目根目录（.env 定位基准）
- describe_env_files()       候选配置文件及是否存在（排查配置不生效时先看这个）
"""
from app.config.settings import (
    ENV_NAME,
    PROJECT_ROOT,
    SUPPORTED_ENVS,
    Settings,
    describe_env_files,
    get_settings,
    settings,
)

__all__ = [
    "Settings",
    "get_settings",
    "settings",
    "ENV_NAME",
    "SUPPORTED_ENVS",
    "PROJECT_ROOT",
    "describe_env_files",
]
