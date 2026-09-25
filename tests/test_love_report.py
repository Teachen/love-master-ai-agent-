"""恋爱大师 - 恋爱报告（结构化输出）单元测试

无需 API Key，不发起真实网络请求。

打桩策略：
- FakeStructuredLLM 顶替 get_chat_model 返回的模型，其 with_structured_output
  直接返回预设的 LoveReport，并记录收到的 messages，
  以此断言「会话历史确实被送进了报告生成的提示词」。
- 通过 method_should_fail 参数模拟 json_schema 不受支持，
  验证 method 回退到 function_calling 的逻辑。
"""
import json

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from app.schemas import LoveReport, LoveSuggestion, RiskItem


def _sample_report(**overrides) -> LoveReport:
    data = {
        "title": "单身三年情感状态分析报告",
        "summary": "用户长期单身并伴随焦虑，但自我觉察能力较强。",
        "stage": "单身",
        "mood_score": 4,
        "strengths": ["自我觉察清晰", "有改变意愿"],
        "problems": ["社交圈狭窄", "过度焦虑"],
        "risks": [
            RiskItem(risk="焦虑引发自我否定", severity="中", advice="规律作息与运动"),
            RiskItem(risk="回避社交减少机会", severity="高", advice="低压场景逐步社交"),
        ],
        "suggestions": [
            LoveSuggestion(title="扩大低压社交", detail="每周参加一次兴趣活动", priority="高"),
            LoveSuggestion(title="记录情绪日记", detail="每日记录焦虑触发点", priority="中"),
        ],
        "encouragement": "单身不等于不完整，你已迈出重要一步。",
    }
    data.update(overrides)
    return LoveReport(**data)


class FakeStructuredLLM:
    """假模型：with_structured_output 返回预设报告并记录入参。

    注意：真实的 with_structured_output 返回 Runnable（具备 .invoke），
    所以这里必须返回 RunnableLambda 而不是裸函数，否则打桩失真。
    """

    def __init__(self, report: LoveReport | None = None, method_should_fail=None):
        self.report = report or _sample_report()
        self.method_should_fail = method_should_fail or set()
        self.calls: list[list[BaseMessage]] = []
        self.methods_tried: list[str] = []

    def with_structured_output(self, schema, method=None, **kwargs):
        self.methods_tried.append(method)

        if method in self.method_should_fail:

            def _raise(_messages):
                raise ValueError(f"模型不支持 method={method}")

            return RunnableLambda(_raise)

        def _invoke(messages):
            self.calls.append(list(messages))
            return self.report

        return RunnableLambda(_invoke)


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """隔离记忆目录，避免污染项目 tmp/memory"""
    from app.agent import memory as memory_module

    monkeypatch.setattr(memory_module, "MEMORY_DIR", tmp_path)
    memory_module._memory_pool.clear()
    yield tmp_path
    memory_module._memory_pool.clear()


@pytest.fixture
def stub_llm(monkeypatch):
    """默认打桩：结构化输出可用"""
    fake = FakeStructuredLLM()
    monkeypatch.setattr("app.models.get_chat_model", lambda *a, **k: fake)
    return fake


# ---------- 核心：结构化输出 ----------


def test_generate_report_returns_typed_object(stub_llm):
    """报告应返回 LoveReport 实例，而非字符串"""
    from app.app import LoveApp

    report = LoveApp(session_id="report_basic").generate_report(use_rag=False)

    assert isinstance(report, LoveReport)
    assert report.stage == "单身"
    assert report.mood_score == 4
    assert len(report.suggestions) == 2
    assert report.suggestions[0].priority == "高"


def test_report_prompt_contains_conversation_history(stub_llm):
    """报告生成的提示词中必须包含此前的对话内容"""
    from app.app import LoveApp

    app = LoveApp(session_id="report_hist")
    # 先造两轮对话
    monkeypatch_llm = stub_llm
    app.memory.add_user_message("我单身三年了，很焦虑")
    app.memory.add_ai_message("能感受到你的压力")
    app.memory.add_user_message("我该怎么开始社交")

    app.generate_report(use_rag=False)

    sent = stub_llm.calls[0]
    contents = [str(getattr(m, "content", m)) for m in sent]
    joined = "\n".join(contents)

    assert "我单身三年了，很焦虑" in joined
    assert "我该怎么开始社交" in joined
    assert "能感受到你的压力" in joined
    # 第一条必须是 system
    assert type(sent[0]).__name__ == "SystemMessage"


def test_report_without_history_still_works(stub_llm):
    """无对话历史时应走兜底提示，而不是报错"""
    from app.app import LoveApp

    report = LoveApp(session_id="report_empty").generate_report(use_rag=False)

    assert isinstance(report, LoveReport)
    joined = "\n".join(str(getattr(m, "content", m)) for m in stub_llm.calls[0])
    assert "尚未进行实质性对话" in joined


def test_method_fallback_on_unsupported_schema(monkeypatch):
    """json_schema 不受支持时应回退到 function_calling"""
    fake = FakeStructuredLLM(method_should_fail={"json_schema"})
    monkeypatch.setattr("app.models.get_chat_model", lambda *a, **k: fake)

    from app.app import LoveApp

    report = LoveApp(session_id="report_fallback").generate_report(use_rag=False)

    assert isinstance(report, LoveReport)
    assert fake.methods_tried == ["json_schema", "function_calling"]


def test_all_methods_fail_raises_runtime_error(monkeypatch):
    """两种 method 都失败时应抛出 RuntimeError 并带上原因"""
    fake = FakeStructuredLLM(method_should_fail={"json_schema", "function_calling"})
    monkeypatch.setattr("app.models.get_chat_model", lambda *a, **k: fake)

    from app.app import LoveApp

    with pytest.raises(RuntimeError, match="结构化输出失败"):
        LoveApp(session_id="report_fail").generate_report(use_rag=False)


def test_rag_context_injected_when_enabled(monkeypatch, stub_llm):
    """use_rag=True 时应把知识库内容注入提示词，并标记 used_knowledge_base"""
    from langchain_core.documents import Document

    monkeypatch.setattr(
        "app.rag.similarity_search",
        lambda q, k=4: [Document(page_content="单身焦虑的应对方法", metadata={"source": "单身篇"})],
    )

    from app.app import LoveApp

    app = LoveApp(session_id="report_rag")
    # 检索 query 来自会话中的用户消息，必须先有对话
    app.memory.add_user_message("我单身三年了，很焦虑")

    report = app.generate_report(use_rag=True)

    joined = "\n".join(str(getattr(m, "content", m)) for m in stub_llm.calls[0])
    assert "单身焦虑的应对方法" in joined
    assert report.used_knowledge_base is True


def test_rag_failure_degrades_gracefully(monkeypatch, stub_llm):
    """知识库检索失败时应降级为无参考生成，不影响报告产出"""

    def _boom(q, k=4):
        raise RuntimeError("PGVector 连接失败")

    monkeypatch.setattr("app.rag.similarity_search", _boom)

    from app.app import LoveApp

    report = LoveApp(session_id="report_rag_fail").generate_report(use_rag=True)
    assert isinstance(report, LoveReport)


# ---------- 模型定义校验 ----------


def test_report_model_rejects_out_of_range_score():
    """mood_score 超出 1-10 应被 pydantic 拒绝"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _sample_report(mood_score=11)


def test_report_model_rejects_empty_suggestions():
    """suggestions 为空应被拒绝（min_length=1）"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _sample_report(suggestions=[])


def test_report_model_rejects_invalid_stage():
    """stage 非枚举值应被拒绝"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _sample_report(stage="不明")


# ---------- HTTP 接口 ----------


def test_api_report_endpoint(stub_llm):
    """POST /api/chat/report 应返回结构化 JSON"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/chat/report",
        json={"session_id": "api_report", "use_rag": False, "export_pdf": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "api_report"
    assert body["report"]["stage"] == "单身"
    assert body["report"]["mood_score"] == 4
    assert body["pdf_path"] is None
    assert len(body["report"]["suggestions"]) == 2


def test_api_report_error_maps_to_400(monkeypatch):
    """结构化输出全部失败时接口应返回 400 而非 500"""
    fake = FakeStructuredLLM(method_should_fail={"json_schema", "function_calling"})
    monkeypatch.setattr("app.models.get_chat_model", lambda *a, **k: fake)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/chat/report",
        json={"session_id": "api_report_err", "use_rag": False},
    )
    assert resp.status_code == 400
    assert "结构化输出失败" in resp.json()["detail"]


def test_api_report_export_pdf(stub_llm, tmp_path, monkeypatch):
    """export_pdf=True 时应落地 PDF 文件"""
    from app.config import settings

    monkeypatch.setattr(settings, "pdf_save_dir", str(tmp_path))

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/chat/report",
        json={"session_id": "api_report_pdf", "use_rag": False, "export_pdf": True},
    )
    assert resp.status_code == 200
    pdf_path = resp.json()["pdf_path"]
    assert pdf_path and pdf_path.endswith(".pdf")

    import os

    assert os.path.exists(pdf_path)
    with open(pdf_path, "rb") as fh:
        assert fh.read(4) == b"%PDF"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
