"""恋爱大师 - MCP 模型上下文协议客户端

对应 Java 版 mcp-servers.json，用于接入外部 MCP 工具服务。
需先安装：pip install -r requirements-optional.txt
"""
import json
from pathlib import Path
from typing import Any, Dict, List

from app.utils import get_logger

logger = get_logger(__name__)

# MCP 服务配置文件
MCP_CONFIG_FILE = Path(__file__).parent / "servers.json"


def load_mcp_config() -> Dict[str, Any]:
    """读取 MCP 服务配置"""
    if not MCP_CONFIG_FILE.exists():
        logger.warning("MCP 配置文件不存在: %s", MCP_CONFIG_FILE)
        return {}
    try:
        return json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP 配置解析失败: %s", exc)
        return {}


async def load_mcp_tools() -> List:
    """加载所有已配置 MCP 服务对外暴露的工具

    返回 LangChain Tool 列表，可直接挂到 ReAct Agent 上。
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("MCP 依赖未安装，请执行 pip install -r requirements-optional.txt")
        return []

    servers = load_mcp_config().get("mcpServers", {})
    if not servers:
        logger.info("未配置 MCP 服务，跳过加载")
        return []

    try:
        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
        logger.info("MCP 工具加载完成，共 %d 个", len(tools))
        return tools
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP 工具加载失败: %s", exc)
        return []
