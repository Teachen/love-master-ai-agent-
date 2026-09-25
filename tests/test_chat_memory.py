"""恋爱大师 - 多轮对话会话记忆单元测试

无需 API Key，不发起真实网络请求。

做法：用 RecordingFakeChatModel 顶替 app.models.get_chat_model。
它既能按脚本顺序返回固定回答，又会记录每一轮实际送入模型的完整消息列表，
因此可以断言「上一轮的对话内容确实进入了下一轮的 Prompt」——
这正是「多轮对话」成立与否的判定依据。
"""
import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class RecordingFakeChatModel(BaseChatModel):
    """假模型：记录每次收到的消息，按脚本顺序返回回答"""

    responses: list[str] = Field(default_factory=lambda: ["默认回答"])
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> ChatResult:
        self.calls.append(list(messages))
        # 脚本用完后一直复用最后一条回答
        idx = min(len(self.calls) - 1, len(self.responses) - 1)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.responses[idx]))]
        )


# ---------- 测试夹具 ----------


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """把所有用例的记忆目录指向临时目录，并清空会话池，避免污染项目 tmp/memory"""
    from app.agent import memory as memory_module

    monkeypatch.setattr(memory_module, "MEMORY_DIR", tmp_path)
    memory_module._memory_pool.clear()
    yield tmp_path
    memory_module._memory_pool.clear()


@pytest.fixture
def fake_llm(monkeypatch):
    """用假模型顶掉真实大模型工厂"""
    model = RecordingFakeChatModel(
        responses=["我记住了。", "你刚才说的是单身三年。", "好的，我继续记着。"]
    )
    monkeypatch.setattr("app.models.get_chat_model", lambda *args, **kwargs: model)
    return model


# ---------- 核心：多轮对话记忆 ----------


def test_multi_turn_history_injected_into_prompt(fake_llm):
    """第二轮请求的 Prompt 中必须包含第一轮的用户消息与 AI 回答"""
    from app.app import LoveApp

    chat = LoveApp(session_id="multi_turn")
    r1 = chat.chat("我单身三年了")
    r2 = chat.chat("刚才我说了几年？")

    assert r1 == "我记住了。"
    assert r2 == "你刚才说的是单身三年。"

    assert len(fake_llm.calls) == 2

    # 第一轮：只有 system + 本轮输入
    first_roles = [type(m).__name__ for m in fake_llm.calls[0]]
    assert first_roles == ["SystemMessage", "HumanMessage"]

    # 第二轮：system + 第一轮 user + 第一轮 ai + 第二轮 user
    second = fake_llm.calls[1]
    assert [type(m).__name__ for m in second] == [
        "SystemMessage",
        "HumanMessage",
        "AIMessage",
        "HumanMessage",
    ]
    assert second[1].content == "我单身三年了"
    assert second[2].content == "我记住了。"
    assert second[3].content == "刚才我说了几年？"


def test_multi_turn_history_grows_linearly(fake_llm):
    """连续 3 轮后，第 3 轮 Prompt 里应累计前两轮共 4 条历史消息"""
    from app.app import LoveApp

    chat = LoveApp(session_id="grow")
    for text in ["第一轮", "第二轮", "第三轮"]:
        chat.chat(text)

    third = fake_llm.calls[2]
    # system + 2 轮历史 × 2 条 + 本轮输入 = 6
    assert len(third) == 6
    contents = [m.content for m in third]
    assert contents[1:5] == ["第一轮", "我记住了。", "第二轮", "你刚才说的是单身三年。"]
    assert contents[5] == "第三轮"


def test_session_isolation(fake_llm):
    """不同 session_id 的记忆互不可见"""
    from app.app import LoveApp

    alice = LoveApp(session_id="alice")
    bob = LoveApp(session_id="bob")

    alice.chat("我是爱丽丝")
    bob.chat("我是鲍勃")
    bob.chat("我是谁")

    bob_second_call = [m.content for m in fake_llm.calls[2]]
    assert "我是爱丽丝" not in bob_second_call
    assert "我是鲍勃" in bob_second_call


def test_memory_persists_across_process_restart(fake_llm):
    """模拟进程重启：清空会话池后，历史应能从文件恢复"""
    from app.agent import memory as memory_module
    from app.app import LoveApp

    LoveApp(session_id="persist").chat("记住：我喜欢猫")

    # 清空进程内缓存，强制下次从磁盘重建
    memory_module._memory_pool.clear()

    restored = LoveApp(session_id="persist").get_history()
    assert restored == [
        {"role": "user", "content": "记住：我喜欢猫"},
        {"role": "assistant", "content": "我记住了。"},
    ]


# ---------- 记忆机制本身 ----------


def test_memory_pool_returns_same_instance():
    """同一 session 在进程内复用同一个记忆对象"""
    from app.agent import get_chat_memory

    assert get_chat_memory("pool_test") is get_chat_memory("pool_test")


def test_sliding_window_trims_oldest():
    """超出 max_messages 时丢弃最早的消息"""
    from app.agent.memory import FileChatMemory

    mem = FileChatMemory("trim_test", max_messages=4)
    for i in range(5):
        mem.add_user_message(f"问题{i}")
        mem.add_ai_message(f"回答{i}")

    messages = mem.get_messages()
    assert len(messages) == 4
    assert [m.content for m in messages] == ["问题3", "回答3", "问题4", "回答4"]


def test_clear_history_empties_memory(fake_llm):
    """清空后历史为空，且落盘文件同步为空数组"""
    import json

    from app.app import LoveApp

    chat = LoveApp(session_id="clear_me")
    chat.chat("你好")
    assert len(chat.get_history()) == 2

    chat.clear_history()
    assert chat.get_history() == []
    assert json.loads(chat.memory.file_path.read_text(encoding="utf-8")) == []


def test_corrupted_memory_file_falls_back_to_empty(tmp_path):
    """记忆文件损坏时应降级为空历史，而不是抛异常"""
    from app.agent.memory import FileChatMemory

    broken = tmp_path / "broken_session.json"
    broken.write_text("{ 这不是合法 JSON", encoding="utf-8")

    mem = FileChatMemory("broken_session")
    assert mem.get_messages() == []


# ---------- 端到端：HTTP 接口多轮对话 ----------


def test_api_multi_turn_conversation(fake_llm):
    """通过 /api/chat 连发两轮，再查 /api/chat/history 应看到完整 4 条"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    session = "api_multi_turn"

    first = client.post(
        "/api/chat",
        json={"message": "第一句", "session_id": session, "mode": "chat"},
    )
    assert first.status_code == 200
    assert first.json()["content"] == "我记住了。"

    second = client.post(
        "/api/chat",
        json={"message": "第二句", "session_id": session, "mode": "chat"},
    )
    assert second.status_code == 200
    assert second.json()["content"] == "你刚才说的是单身三年。"

    history = client.get("/api/chat/history", params={"session_id": session})
    assert history.status_code == 200
    assert [m["role"] for m in history.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    cleared = client.delete("/api/chat/history", params={"session_id": session})
    assert cleared.status_code == 200
    assert client.get("/api/chat/history", params={"session_id": session}).json()[
        "messages"
    ] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
