"""恋爱大师 - 请求/响应模型"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: str = Field(default="default", max_length=64, description="会话 ID")
    mode: str = Field(
        default="chat",
        description="对话模式：chat 普通对话 / rag 知识库问答 / agent 智能体",
    )


class ChatResponse(BaseModel):
    """对话响应"""

    session_id: str = Field(..., description="会话 ID")
    mode: str = Field(..., description="对话模式")
    content: str = Field(..., description="回复内容")


class HistoryMessage(BaseModel):
    """历史消息"""

    role: str = Field(..., description="角色：user / assistant")
    content: str = Field(..., description="消息内容")


class HistoryResponse(BaseModel):
    """历史记录响应"""

    session_id: str
    messages: List[HistoryMessage]


class BuildKbRequest(BaseModel):
    """知识库构建请求"""

    force_rebuild: bool = Field(default=False, description="是否清空后重建")


class BuildKbResponse(BaseModel):
    """知识库构建响应"""

    success: bool
    chunk_count: int
    message: str


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    app_name: str
    version: str
    llm_ready: bool
    env: str
    detail: Optional[str] = None
