"""恋爱大师 - 中间件与 LLM 日志测试

覆盖：
- 免鉴权路径放行（健康检查 / 文档）
- 鉴权关闭时 /api/* 直接放行（默认状态，保证本地开发不受影响）
- 鉴权开启后：无 Key 401 / 有效 Key 200 / 无效 Key 401 / 未配 Key 全拒绝
- LLMLoggingHandler 成对输出请求与响应日志（对应 Java MyLoggerAdvisor）
"""
import logging
import sys
from types import SimpleNamespace

from langchain_core.messages import HumanMessage, SystemMessage


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_public_paths_open():
    """健康检查与文档永远可匿名访问"""
    client = _client()
    assert client.get("/api/health").status_code == 200
    assert client.get("/docs").status_code == 200


def test_api_open_when_auth_disabled():
    """鉴权关闭（默认）时业务接口直接放行"""
    from app.config import settings

    original = settings.api_key_enabled
    try:
        settings.api_key_enabled = False
        resp = _client().get("/api/chat/history?session_id=it_auth")
        assert resp.status_code == 200
    finally:
        settings.api_key_enabled = original


def test_auth_rejects_missing_key():
    """开启鉴权后，无 Key 访问业务接口返回 401"""
    from app.config import settings

    original = (settings.api_key_enabled, settings.api_keys)
    try:
        settings.api_key_enabled = True
        settings.api_keys = "test-key-123"
        resp = _client().get("/api/chat/history?session_id=it_auth")
        assert resp.status_code == 401
        assert "X-API-Key" in resp.json()["detail"]
    finally:
        settings.api_key_enabled, settings.api_keys = original


def test_auth_accepts_valid_key():
    """开启鉴权后，携带有效 Key 放行"""
    from app.config import settings

    original = (settings.api_key_enabled, settings.api_keys)
    try:
        settings.api_key_enabled = True
        settings.api_keys = "test-key-123, another-key"
        resp = _client().get(
            "/api/chat/history?session_id=it_auth",
            headers={"X-API-Key": "test-key-123"},
        )
        assert resp.status_code == 200
    finally:
        settings.api_key_enabled, settings.api_keys = original


def test_auth_rejects_invalid_key():
    """开启鉴权后，错误 Key 返回 401"""
    from app.config import settings

    original = (settings.api_key_enabled, settings.api_keys)
    try:
        settings.api_key_enabled = True
        settings.api_keys = "test-key-123"
        resp = _client().get(
            "/api/chat/history?session_id=it_auth",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401
    finally:
        settings.api_key_enabled, settings.api_keys = original


def test_auth_blocks_when_no_keys_configured():
    """开启鉴权但未配置任何 Key 时一律拒绝（防裸奔）"""
    from app.config import settings

    original = (settings.api_key_enabled, settings.api_keys)
    try:
        settings.api_key_enabled = True
        settings.api_keys = ""
        resp = _client().get(
            "/api/chat/history?session_id=it_auth",
            headers={"X-API-Key": "anything"},
        )
        assert resp.status_code == 401
    finally:
        settings.api_key_enabled, settings.api_keys = original


def test_llm_logging_handler_pairs():
    """LLMLoggingHandler 应成对输出请求与响应日志"""
    from app.config import settings
    from app.core import get_llm_logging_handler

    handler = get_llm_logging_handler()
    capture = _Capture()
    target = logging.getLogger("app.llm_advisor")
    target.addHandler(capture)

    original = (settings.llm_log_enabled, settings.llm_log_max_chars)
    try:
        settings.llm_log_enabled = True
        settings.llm_log_max_chars = 50

        handler.on_chat_model_start(
            None,
            [[SystemMessage(content="你是恋爱大师"), HumanMessage(content="你好")]],
            run_id="abcdef1234567890",
        )
        response = SimpleNamespace(
            generations=[[SimpleNamespace(text="你好呀，很高兴见到你")]]
        )
        handler.on_llm_end(response, run_id="abcdef1234567890")
        handler.on_llm_error(RuntimeError("mock error"), run_id="abcdef1234567890")
    finally:
        settings.llm_log_enabled, settings.llm_log_max_chars = original
        target.removeHandler(capture)

    joined = "\n".join(capture.records)
    assert "[LLM请求 run=abcdef12] system:" in joined
    assert "[LLM请求 run=abcdef12] human: 你好" in joined
    assert "[LLM响应 run=abcdef12] 你好呀" in joined
    assert "[LLM错误 run=abcdef12]" in joined


def test_llm_logging_disabled_is_silent():
    """开关关闭时不产生日志"""
    from app.config import settings
    from app.core import get_llm_logging_handler

    handler = get_llm_logging_handler()
    capture = _Capture()
    target = logging.getLogger("app.llm_advisor")
    target.addHandler(capture)

    original = settings.llm_log_enabled
    try:
        settings.llm_log_enabled = False
        handler.on_chat_model_start(None, [[HumanMessage(content="hi")]], run_id="x")
        handler.on_llm_end(SimpleNamespace(generations=[]), run_id="x")
    finally:
        settings.llm_log_enabled = original
        target.removeHandler(capture)

    assert capture.records == []


def test_factory_injects_callback():
    """模型工厂应把日志处理器注入 ChatOpenAI"""
    from app.config import settings
    from app.core import get_llm_logging_handler

    if not settings.llm_ready:
        print("SKIP: DASHSCOPE_API_KEY 未配置，跳过工厂注入检查")
        return

    from app.models import get_chat_model

    llm = get_chat_model()
    assert get_llm_logging_handler() in (llm.callbacks or [])


class _Capture(logging.Handler):
    """捕获日志消息用"""

    def __init__(self):
        super().__init__()
        self.records: list = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f"[PASS] {name}")
    print("\n全部中间件测试通过")
    sys.exit(0)
