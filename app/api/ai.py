"""恋爱大师 - SSE 流式对话接口

对应 Java 版 AiController 的两个流式接口：
- GET /api/ai/love_app/chat/sse  恋爱大师流式对话（text/event-stream）
- GET /api/ai/manus/chat         超级智能体流式推理（text/event-stream）

通过 Server-Sent Events 把大模型的增量输出实时推给前端。事件帧格式：

    data: <一段文本>

    data: [DONE]

SSE 规范要点：
- 每个数据帧以 `data: ` 开头，以空行（\n\n）结束；
- 数据内部若含换行，须拆成多条 `data: ` 行（见 _sse_event）；
- 前端用 EventSource 订阅，收到 [DONE] 后主动关闭连接。
"""
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.app import LoveApp
from app.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ai", tags=["SSE 流式对话"])

# SSE 结束标记，前端收到后主动关闭连接
DONE = "[DONE]"

# SSE 响应头：关缓冲，保证逐字实时下发
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # 关键：关掉反向代理（nginx）的响应缓冲，否则前端会收不到实时流
    "X-Accel-Buffering": "no",
}


def _sse_event(text: str) -> str:
    """把一段文本转成符合 SSE 规范的事件帧。

    数据内部含换行时，必须拆成多条 ``data: `` 行，
    否则前端会把换行误当成事件分隔符。
    """
    if not text:
        return ""
    return "".join(f"data: {line}\n" for line in text.split("\n")) + "\n"


def _event_stream(chunks):
    """把增量文本包成 SSE 帧流，出错时把异常也发给前端，最后补结束标记。

    返回生成器（StreamingResponse 会调度到线程池执行，不阻塞事件循环）。
    """

    def gen():
        try:
            for chunk in chunks:
                frame = _sse_event(chunk)
                if frame:
                    yield frame
        except Exception as exc:  # noqa: BLE001
            # 出错也要按协议告诉前端，避免连接悬挂、前端永远等不到 [DONE]
            logger.exception("SSE 流式输出异常")
            yield _sse_event(f"[ERROR] {exc}")
        finally:
            yield _sse_event(DONE)

    return gen()


@router.get("/love_app/chat/sse", summary="恋爱大师流式对话（SSE）")
def love_app_chat_sse(
    message: str = Query(..., description="用户输入"),
    chat_id: str = Query(default="default", alias="chatId", description="会话 ID"),
) -> StreamingResponse:
    """对应 Java 版 doChatWithLoveAppSse。前端用 EventSource 订阅。"""
    love_app = LoveApp(session_id=chat_id or "default")
    return StreamingResponse(
        _event_stream(love_app.chat_stream(message)),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/manus/chat", summary="超级智能体流式推理（SSE）")
def manus_chat_sse(
    message: str = Query(..., description="用户输入"),
    chat_id: str = Query(default="manus", alias="chatId", description="会话 ID"),
) -> StreamingResponse:
    """对应 Java 版 doChatWithManus。前端用 EventSource 订阅。"""
    love_app = LoveApp(session_id=chat_id or "manus")
    return StreamingResponse(
        _event_stream(love_app.agent_stream(message)),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
