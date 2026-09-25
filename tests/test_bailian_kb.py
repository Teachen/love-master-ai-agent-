"""恋爱大师 - 阿里云百炼知识库对接测试

全程打桩 httpx.post，不产生真实网络请求，也不需要百炼账号。

覆盖：
    - 两条检索路径（单库 index / 跨库 agent）的 endpoint 与请求体构造
    - 响应解析：nodes -> LangChain Document
    - 失败处理：success=false、401 鉴权、超时、非 JSON、配置缺失
    - 统一入口路由：RAG_BACKEND=local / bailian 的分流与降级
    - 端到端：bailian 模式下 chat_with_rag 把百炼切片注入 Prompt
"""
import json as _json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.rag.bailian_kb import (  # noqa: E402
    BailianKnowledgeClient,
    BailianKnowledgeError,
    as_bailian_retriever,
    bailian_similarity_search,
    check_bailian_kb,
)
from app.rag.retriever import (  # noqa: E402
    describe_rag_backend,
    similarity_search,
)

WORKSPACE = "llm-test123456"
INDEX_ID = "kb_love_001"
AGENT_ID = "aid-xxxxxxxxxxxxxxxx"


def make_response(status: int, payload) -> httpx.Response:
    """构造 httpx.Response，保证 .json() 可用"""
    content = payload if isinstance(payload, bytes) else _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return httpx.Response(
        status_code=status,
        content=content,
        headers={"Content-Type": "application/json"},
        request=httpx.Request("POST", "https://example.invalid"),
    )


def ok_body(nodes, total=None, cost_time=42):
    return {
        "code": "Success",
        "status_code": 200,
        "status": "SUCCESS",
        "success": True,
        "message": "success",
        "request_id": "req-001",
        "data": {
            "total": total if total is not None else len(nodes),
            "nodes": nodes,
            "cost_time": cost_time,
        },
    }


def node(text="切片正文", score=0.87, **meta):
    metadata = {
        "doc_id": "doc_1",
        "doc_name": "恋爱心理学.md",
        "title": "依恋类型",
        "hier_title": "第一章 > 依恋类型",
        "content": "纯正文内容",
        "pipeline_id": INDEX_ID,
        "page_number": [3],
    }
    metadata.update(meta)
    return {"score": score, "text": text, "metadata": metadata}


@pytest.fixture
def index_client() -> BailianKnowledgeClient:
    """单知识库模式客户端"""
    return BailianKnowledgeClient(
        workspace_id=WORKSPACE,
        api_key="sk-test",
        index_id=INDEX_ID,
        agent_id="",
        region="cn-beijing",
    )


@pytest.fixture
def agent_client() -> BailianKnowledgeClient:
    """跨库检索服务模式客户端"""
    return BailianKnowledgeClient(
        workspace_id=WORKSPACE,
        api_key="sk-test",
        index_id="",
        agent_id=AGENT_ID,
        region="cn-beijing",
    )


# ---------------------------------------------------------------- 路径与请求体

def test_index_mode_endpoint_and_url(index_client):
    assert index_client.use_agent is False
    assert index_client.endpoint == "/api/v1/indices/rag/index/retrieve"
    assert index_client.url == (
        f"https://{WORKSPACE}.cn-beijing.maas.aliyuncs.com/api/v1/indices/rag/index/retrieve"
    )


def test_agent_mode_endpoint_and_url(agent_client):
    assert agent_client.use_agent is True
    assert agent_client.endpoint == "/api/v1/indices/knowledge/search"
    assert agent_client.url == (
        f"https://{WORKSPACE}.cn-beijing.maas.aliyuncs.com/api/v1/indices/knowledge/search"
    )


def test_agent_id_takes_priority_when_both_configured():
    client = BailianKnowledgeClient(
        workspace_id=WORKSPACE, api_key="sk-test",
        index_id=INDEX_ID, agent_id=AGENT_ID,
    )
    assert client.use_agent is True


def test_index_mode_payload_contains_index_id_and_top_k(index_client, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured.update({"url": url, "headers": headers, "json": json})
        return make_response(200, ok_body([node()]))

    monkeypatch.setattr(httpx, "post", fake_post)
    index_client.retrieve("怎么处理焦虑", top_k=3)

    assert captured["json"]["index_id"] == INDEX_ID
    assert captured["json"]["query"] == "怎么处理焦虑"
    assert captured["json"]["top_k"] == 3
    assert "agent_id" not in captured["json"]


def test_agent_mode_payload_omits_top_k(agent_client, monkeypatch):
    """knowledge/search 的参数表里没有 top_k，多传可能触发 InvalidParameter"""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured.update({"json": json})
        return make_response(200, ok_body([node()]))

    monkeypatch.setattr(httpx, "post", fake_post)
    agent_client.retrieve("怎么处理焦虑", top_k=3)

    assert captured["json"]["agent_id"] == AGENT_ID
    assert captured["json"]["query"] == "怎么处理焦虑"
    assert "top_k" not in captured["json"]
    assert "index_id" not in captured["json"]


def test_request_headers_use_bearer_token(index_client, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured.update({"headers": headers})
        return make_response(200, ok_body([]))

    monkeypatch.setattr(httpx, "post", fake_post)
    index_client.retrieve("随便问问")

    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_kb_search_configs_passed_through(agent_client, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured.update({"json": json})
        return make_response(200, ok_body([]))

    monkeypatch.setattr(httpx, "post", fake_post)
    filters = [{"id": INDEX_ID, "search_filters": [{"tags": ["单身"]}]}]
    agent_client.retrieve("焦虑", kb_search_configs=filters)

    assert captured["json"]["kb_search_configs"] == filters


# ---------------------------------------------------------------- 响应解析

def test_node_converted_to_document(index_client, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body([node()])))

    docs = index_client.retrieve_documents("依恋类型")

    assert len(docs) == 1
    doc = docs[0]
    assert doc.page_content == "切片正文"
    assert doc.metadata["source"] == "恋爱心理学.md"
    assert doc.metadata["backend"] == "bailian"
    assert doc.metadata["score"] == 0.87
    assert doc.metadata["pipeline_id"] == INDEX_ID
    assert doc.metadata["page_number"] == [3]


def test_document_falls_back_to_metadata_content(index_client, monkeypatch):
    """text 为空时回退到 metadata.content"""
    empty_text_node = node(text="", content="只有正文能用了")
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: make_response(200, ok_body([empty_text_node]))
    )

    docs = index_client.retrieve_documents("测试")

    assert docs[0].page_content == "只有正文能用了"


def test_document_source_falls_back_to_title(index_client, monkeypatch):
    nod = node(doc_name=None, title="依恋类型")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body([nod])))

    docs = index_client.retrieve_documents("测试")

    assert docs[0].metadata["source"] == "依恋类型"


def test_empty_nodes_returns_empty_list(index_client, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body([])))

    assert index_client.retrieve_documents("没结果的问题") == []


def test_agent_mode_truncates_to_k(agent_client, monkeypatch):
    """agent 模式无法在请求中控条数，由客户端侧按 k 截断"""
    many = [node(text=f"切片{i}") for i in range(10)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body(many)))

    docs = agent_client.retrieve_documents("问题", top_k=3)

    assert len(docs) == 3
    assert [d.page_content for d in docs] == ["切片0", "切片1", "切片2"]


def test_index_mode_does_not_truncate(index_client, monkeypatch):
    """index 模式条数由服务端 top_k 保证，客户端不再二次截断"""
    many = [node(text=f"切片{i}") for i in range(5)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body(many)))

    assert len(index_client.retrieve_documents("问题", top_k=2)) == 5


# ---------------------------------------------------------------- 失败处理

def test_success_false_raises_with_diagnostics(index_client, monkeypatch):
    body = {
        "code": "Index.InvalidParameter",
        "status_code": 400,
        "success": False,
        "message": "agent_id is required",
        "request_id": "req-bad-1",
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(400, body))

    with pytest.raises(BailianKnowledgeError) as ei:
        index_client.retrieve("问题")

    text = str(ei.value)
    assert "Index.InvalidParameter" in text
    assert "agent_id is required" in text
    assert "req-bad-1" in text


def test_http_200_but_success_false_still_raises(index_client, monkeypatch):
    """HTTP 200 但业务失败 —— 必须以 success 字段判定"""
    body = {"success": False, "code": "Index.NotFound", "message": "index not found", "request_id": "r2"}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, body))

    with pytest.raises(BailianKnowledgeError, match="Index.NotFound"):
        index_client.retrieve("问题")


def test_401_reports_auth_error(index_client, monkeypatch):
    body = {"success": False, "code": "InvalidApiKey", "message": "invalid key", "request_id": "r3"}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(401, body))

    with pytest.raises(BailianKnowledgeError, match="鉴权失败"):
        index_client.retrieve("问题")


def test_timeout_raises_friendly_error(index_client, monkeypatch):
    def fake_post(*a, **k):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(BailianKnowledgeError, match="超时"):
        index_client.retrieve("问题")


def test_network_error_raises_friendly_error(index_client, monkeypatch):
    def fake_post(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(BailianKnowledgeError, match="网络异常"):
        index_client.retrieve("问题")


def test_non_json_response_raises(index_client, monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: make_response(502, b"<html>bad gateway</html>")
    )

    with pytest.raises(BailianKnowledgeError, match="非 JSON"):
        index_client.retrieve("问题")


def test_empty_query_rejected_without_network(index_client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("不应该发起网络请求")

    monkeypatch.setattr(httpx, "post", boom)

    with pytest.raises(BailianKnowledgeError, match="不能为空"):
        index_client.retrieve("   ")


@pytest.mark.parametrize(
    "kwargs,expect",
    [
        ({"workspace_id": "", "api_key": "sk-x", "index_id": INDEX_ID}, "BAILIAN_WORKSPACE_ID"),
        ({"workspace_id": WORKSPACE, "api_key": "", "index_id": INDEX_ID}, "DASHSCOPE_API_KEY"),
        ({"workspace_id": WORKSPACE, "api_key": "sk-x", "index_id": "", "agent_id": ""}, "BAILIAN_INDEX_ID"),
    ],
)
def test_validate_reports_missing_config(kwargs, expect):
    client = BailianKnowledgeClient(**kwargs)

    with pytest.raises(BailianKnowledgeError, match=expect):
        client.retrieve("问题")


# ---------------------------------------------------------------- 统一入口路由

def test_router_uses_local_by_default(monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "local")
    called = {}

    def fake_local(query, k=4, **kwargs):
        called["local"] = (query, k)
        return []

    monkeypatch.setattr("app.rag.vector_store.similarity_search", fake_local)
    similarity_search("问题", k=2)

    assert called["local"] == ("问题", 2)


def test_router_uses_bailian_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", WORKSPACE)
    monkeypatch.setattr(settings, "bailian_index_id", INDEX_ID)
    monkeypatch.setattr(settings, "bailian_agent_id", "")

    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body([node()])))
    docs = similarity_search("问题", k=1)

    assert len(docs) == 1
    assert docs[0].metadata["backend"] == "bailian"


def test_router_falls_back_to_local_when_config_incomplete(monkeypatch):
    """配了 bailian 但缺少 workspace_id，应自动回退 local 而不是报错"""
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", "")
    monkeypatch.setattr(settings, "bailian_index_id", "")

    assert settings.rag_mode == "local"

    monkeypatch.setattr("app.rag.vector_store.similarity_search", lambda q, k=4, **kw: [])
    assert similarity_search("问题") == []


def test_router_raises_when_bailian_fails_and_no_fallback(monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", WORKSPACE)
    monkeypatch.setattr(settings, "bailian_index_id", INDEX_ID)
    monkeypatch.setattr(settings, "bailian_agent_id", "")
    monkeypatch.setattr(settings, "bailian_kb_fallback_local", False)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, {"success": False, "code": "Index.Error", "message": "boom"}))

    with pytest.raises(BailianKnowledgeError):
        similarity_search("问题")


def test_router_degrades_to_local_when_fallback_enabled(monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", WORKSPACE)
    monkeypatch.setattr(settings, "bailian_index_id", INDEX_ID)
    monkeypatch.setattr(settings, "bailian_agent_id", "")
    monkeypatch.setattr(settings, "bailian_kb_fallback_local", True)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(500, {"success": False, "code": "Err", "message": "boom"}))

    fallback = []
    monkeypatch.setattr("app.rag.vector_store.similarity_search", lambda q, k=4, **kw: fallback)

    assert similarity_search("问题") == fallback


def test_describe_rag_backend_reports_bailian_details(monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", WORKSPACE)
    monkeypatch.setattr(settings, "bailian_index_id", INDEX_ID)
    monkeypatch.setattr(settings, "bailian_agent_id", "")

    info = describe_rag_backend()

    assert info["active_backend"] == "bailian"
    assert info["bailian_mode"] == "index"
    assert info["bailian_target"] == INDEX_ID
    assert WORKSPACE in info["bailian_url"]


def test_retriever_returns_documents(index_client, monkeypatch):
    monkeypatch.setattr(
        "app.rag.bailian_kb.get_bailian_client", lambda: index_client
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body([node()])))

    retriever = as_bailian_retriever(k=1)
    docs = retriever.invoke("依恋类型")

    assert len(docs) == 1
    assert docs[0].page_content == "切片正文"


def test_check_bailian_kb_reports_success(index_client, monkeypatch):
    monkeypatch.setattr("app.rag.bailian_kb.get_bailian_client", lambda: index_client)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: make_response(200, ok_body([node()])))

    info = check_bailian_kb("依恋")

    assert info["ok"] is True
    assert info["hits"] == 1
    assert info["mode"] == "index"
    assert "切片正文" in info["sample"]


def test_check_bailian_kb_reports_failure_without_raising(index_client, monkeypatch):
    monkeypatch.setattr("app.rag.bailian_kb.get_bailian_client", lambda: index_client)
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: make_response(200, {"success": False, "code": "X", "message": "挂了"})
    )

    info = check_bailian_kb("依恋")

    assert info["ok"] is False
    assert "挂了" in info["error"]


# ---------------------------------------------------------------- 端到端

class RecordingChatModel(BaseChatModel):
    """记录收到的 messages，便于断言知识库内容是否注入了 Prompt"""

    captured: list = []

    @property
    def _llm_type(self) -> str:
        return "recording"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        type(self).captured.append(list(messages))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="这是基于知识库的回答。"))]
        )


def test_chat_with_rag_injects_bailian_slices(monkeypatch):
    """端到端：bailian 模式下 chat_with_rag 应把百炼切片放进 Prompt"""
    from app.app import LoveApp
    from app.agent import get_chat_memory

    sid = "cli_test_bailian_e2e"
    get_chat_memory(sid).clear()

    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", WORKSPACE)
    monkeypatch.setattr(settings, "bailian_index_id", INDEX_ID)
    monkeypatch.setattr(settings, "bailian_agent_id", "")

    RecordingChatModel.captured = []
    monkeypatch.setattr("app.models.get_chat_model", lambda **kw: RecordingChatModel())
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: make_response(
            200, ok_body([node(text="回避型依恋的人需要稳定的安全信号。")])
        ),
    )

    answer = LoveApp(session_id=sid).chat_with_rag("我是回避型依恋吗")

    assert answer == "这是基于知识库的回答。"
    assert RecordingChatModel.captured, "模型未被调用"
    prompt_text = "\n".join(str(getattr(m, "content", "")) for m in RecordingChatModel.captured[0])
    assert "回避型依恋的人需要稳定的安全信号" in prompt_text, "百炼切片未注入 Prompt"

    get_chat_memory(sid).clear()
