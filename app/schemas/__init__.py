"""恋爱大师 - 数据模型包"""
from app.schemas.chat import (
    BuildKbRequest,
    BuildKbResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    HistoryMessage,
    HistoryResponse,
)
from app.schemas.report import (
    LoveReport,
    LoveSuggestion,
    ReportRequest,
    ReportResponse,
    RiskItem,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "HistoryMessage",
    "HistoryResponse",
    "BuildKbRequest",
    "BuildKbResponse",
    "HealthResponse",
    "LoveReport",
    "LoveSuggestion",
    "RiskItem",
    "ReportRequest",
    "ReportResponse",
]
