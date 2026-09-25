"""恋爱大师 - 对话接口

对应 Java 版 AiController，提供对话、RAG、Agent、会话管理、恋爱报告接口。
"""
from fastapi import APIRouter, HTTPException

from app.app import LoveApp
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryResponse,
    ReportRequest,
    ReportResponse,
)

router = APIRouter(prefix="/api/chat", tags=["对话"])


def _build_app(session_id: str) -> LoveApp:
    return LoveApp(session_id=session_id or "default")


@router.post("", response_model=ChatResponse, summary="统一对话入口")
async def chat(request: ChatRequest) -> ChatResponse:
    """按 mode 分发：chat 普通对话 / rag 知识库问答 / agent 智能体推理"""
    love_app = _build_app(request.session_id)
    mode = (request.mode or "chat").lower()

    try:
        if mode == "rag":
            content = love_app.chat_with_rag(request.message)
        elif mode == "agent":
            content = love_app.run_agent(request.message)
        elif mode == "chat":
            content = love_app.chat(request.message)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的对话模式：{mode}")
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"对话失败：{exc}") from exc

    return ChatResponse(session_id=request.session_id, mode=mode, content=content)


@router.post("/rag", response_model=ChatResponse, summary="知识库问答（RAG）")
async def chat_rag(request: ChatRequest) -> ChatResponse:
    love_app = _build_app(request.session_id)
    try:
        content = love_app.chat_with_rag(request.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"RAG 问答失败：{exc}") from exc
    return ChatResponse(session_id=request.session_id, mode="rag", content=content)


@router.post("/agent", response_model=ChatResponse, summary="智能体推理（ReAct Agent）")
async def chat_agent(request: ChatRequest) -> ChatResponse:
    love_app = _build_app(request.session_id)
    try:
        content = love_app.run_agent(request.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Agent 推理失败：{exc}") from exc
    return ChatResponse(session_id=request.session_id, mode="agent", content=content)


@router.get("/history", response_model=HistoryResponse, summary="查询会话历史")
async def get_history(session_id: str = "default") -> HistoryResponse:
    love_app = _build_app(session_id)
    return HistoryResponse(session_id=session_id, messages=love_app.get_history())


@router.delete("/history", summary="清空会话历史")
async def clear_history(session_id: str = "default") -> dict:
    _build_app(session_id).clear_history()
    return {"success": True, "message": f"会话 {session_id} 已清空"}


@router.post("/report", response_model=ReportResponse, summary="生成恋爱报告（结构化输出）")
async def generate_report(request: ReportRequest) -> ReportResponse:
    """基于会话历史生成结构化恋爱报告。

    对应 Java 版「结构化输出 - 恋爱报告功能」：把模型自由文本约束为
    LoveReport 强类型对象，可选同时导出中文 PDF。
    """
    love_app = _build_app(request.session_id)
    message_count = len(love_app.get_history())

    try:
        report = love_app.generate_report(use_rag=request.use_rag)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"报告生成失败：{exc}") from exc

    pdf_path: str | None = None
    if request.export_pdf:
        from app.core import render_report_pdf

        try:
            pdf_path = str(render_report_pdf(report))
        except RuntimeError as exc:
            # reportlab 未安装：报告本身已成功，降级为仅返回 JSON
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"PDF 导出失败：{exc}") from exc

    return ReportResponse(
        session_id=request.session_id,
        report=report,
        pdf_path=pdf_path,
        message_count=message_count,
    )
