"""恋爱大师 - SSE 流式对话接口测试

全程打桩模型，不消耗真实 API，也不需要启动服务。

覆盖：
    - chat_stream / agent_stream 生成器逐块产出并写入记忆
    - SSE 事件帧格式（data: 行、空行分隔、[DONE] 结束标记）
    - 内部换行被正确拆分（符合 SSE 规范）
    - HTTP 接口的 media_type、chatId 别名、换行拆分
"""
import sys
import uuid
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import get_chat_memory  # noqa: E402
from app.api.ai import _sse_event  # noqa: E402
from app.app import LoveApp  # noqa: E402


class StreamingChatModel(BaseChatModel):
    """支持流式的假模型：按预定 token 序列逐块产出

    注意 tokens 必须是 ClassVar：BaseChatModel 是 pydantic 模型，
    普通字段会在实例化时把默认值复制成实例属性，导致
    「测试里改类属性」对已创建实例不生效。
    """

    tokens: ClassVar[list] = ["你好", "，我是", "恋爱大师", "。"]

    @property
    def _llm_type(self) -> str:
        return "streaming-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="".join(self.tokens)))]
        )

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for tok in self.tokens:
            yield ChatGenerationChunk(message=AIMessageChunk(content=tok))


@pytest.fixture
def session_id() -> str:
    sid = f"sse_test_{uuid.uuid4().hex[:10]}"
    yield sid
    get_chat_memory(sid).clear()


@pytest.fixture(autouse=True)
def stub_chat_model():
    model = StreamingChatModel()
    with patch("app.models.get_chat_model", return_value=model):
        yield model


# ---------------------------------------------------------------- 生成器层

def test_chat_stream_yields_tokens_in_order(session_id):
    app = LoveApp(session_id=session_id)
    chunks = list(app.chat_stream("你好"))

    assert chunks == ["你好", "，我是", "恋爱大师", "。"]


def test_chat_stream_writes_full_answer_to_memory(session_id):
    app = LoveApp(session_id=session_id)
    list(app.chat_stream("你好"))

    history = app.get_history()
    assert history[-1]["role"] == "assistant"
    assert history[-1]["content"] == "你好，我是恋爱大师。"


def test_agent_stream_yields_and_writes_memory(session_id, monkeypatch):
    class FakeGraph:
        def stream(self, *a, **k):
            yield (AIMessageChunk(content="智能体"), {})
            yield (AIMessageChunk(content="推理"), {})
            yield (AIMessageChunk(content="完成"), {})

    class FakeAgent:
        max_iterations = 8
        graph = FakeGraph()

    monkeypatch.setattr("app.app.love_app.get_react_agent", lambda: FakeAgent())

    app = LoveApp(session_id=session_id)
    chunks = list(app.agent_stream("帮我分析"))

    assert chunks == ["智能体", "推理", "完成"]
    assert app.get_history()[-1]["content"] == "智能体推理完成"


# ---------------------------------------------------------------- SSE 帧格式

def test_sse_event_single_line():
    assert _sse_event("你好") == "data: 你好\n\n"


def test_sse_event_splits_internal_newlines():
    """内部换行必须拆成多条 data: 行，否则前端会误判事件边界"""
    assert _sse_event("a\nb\nc") == "data: a\ndata: b\ndata: c\n\n"


def test_sse_event_empty_returns_empty():
    assert _sse_event("") == ""


# ---------------------------------------------------------------- HTTP 接口

@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_love_app_sse_endpoint(client, session_id):
    resp = client.get(
        "/api/ai/love_app/chat/sse",
        params={"message": "你好", "chatId": session_id},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"

    body = resp.text
    assert "data: 你好\n\n" in body
    assert "data: 恋爱大师\n\n" in body
    assert body.rstrip().endswith("data: [DONE]")


def test_manus_sse_endpoint(client, session_id, monkeypatch):
    class FakeGraph:
        def stream(self, *a, **k):
            yield (AIMessageChunk(content="马努斯"), {})
            yield (AIMessageChunk(content="在思考"), {})

    class FakeAgent:
        max_iterations = 8
        graph = FakeGraph()

    monkeypatch.setattr("app.app.love_app.get_react_agent", lambda: FakeAgent())

    resp = client.get(
        "/api/ai/manus/chat",
        params={"message": "分析一下", "chatId": session_id},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "data: 马努斯\n\n" in resp.text
    assert "data: [DONE]" in resp.text


def test_sse_event_frames_split_on_multiline_token(client, session_id):
    """模型一次吐出带换行的 token 时，SSE 帧仍须规范"""
    StreamingChatModel.tokens = ["第一行\n第二行"]

    resp = client.get(
        "/api/ai/love_app/chat/sse",
        params={"message": "换行测试", "chatId": session_id},
    )

    body = resp.text
    assert "data: 第一行\ndata: 第二行\n\n" in body

    StreamingChatModel.tokens = ["你好", "，我是", "恋爱大师", "。"]  # 复位
