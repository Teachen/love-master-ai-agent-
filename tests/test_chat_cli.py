"""恋爱大师 - 控制台对话工具（chat_cli.py）端到端测试

全程用假的 ChatModel 打桩，不消耗真实 API，也不需要启动 HTTP 服务。

覆盖：
    - 交互循环：发消息、多轮记忆注入、/history、/mode、/clear、未知命令、EOF
    - 模式切换：/chat /rag /agent
    - 报告链路：/report 生成并渲染、PDF 导出、空会话拒绝
    - 非交互入口：one_shot_report
    - 会话隔离
"""
import io
import sys
import uuid
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

from app.agent import get_chat_memory  # noqa: E402
from app.config import settings  # noqa: E402
from app.schemas import LoveReport  # noqa: E402


class FakeChatModel(BaseChatModel):
    """按调用次数返回可预测回答，并记录每次收到的 messages"""

    captured: list = []

    @property
    def _llm_type(self) -> str:
        return "fake-cli"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        type(self).captured.append(messages)
        reply = f"收到你的第 {len(type(self).captured)} 句话，我建议先稳住心态。"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])


def _fake_structured(self, schema, **kwargs):
    """让 with_structured_output 返回 Runnable（与真实 API 行为一致）"""
    if getattr(schema, "__name__", "") != "LoveReport":
        return RunnableLambda(lambda _: schema())
    return RunnableLambda(lambda _: schema(
        title="恋爱状态分析报告",
        summary="你当前处于单身探索期，心态略有焦虑但方向清晰。",
        stage="单身",
        mood_score=6,
        strengths=["自我觉察力强", "愿意主动寻求帮助"],
        problems=["社交圈偏窄", "对拒绝的恐惧被放大"],
        risks=[{"risk": "长期自我否定", "severity": "中", "advice": "用小事积累正反馈"}],
        suggestions=[
            {"title": "扩大接触面", "detail": "每周参加一次兴趣活动", "priority": "高"},
            {"title": "练习表达", "detail": "从轻量话题开始主动发起对话", "priority": "中"},
        ],
        encouragement="你已经迈出了最重要的一步，剩下的只是重复练习。",
    ))


@pytest.fixture
def session_id() -> str:
    """每个用例独立会话，避免历史互相污染"""
    sid = f"cli_test_{uuid.uuid4().hex[:10]}"
    yield sid
    get_chat_memory(sid).clear()


@pytest.fixture(autouse=True)
def stub_llm():
    FakeChatModel.captured = []
    with patch("app.models.get_chat_model", return_value=FakeChatModel()), \
         patch.object(BaseChatModel, "with_structured_output", _fake_structured):
        yield


def drive(script, session_id, mode="chat"):
    """把 script 中的行依次喂给 input()，返回 (退出码, 控制台输出)。

    直接调用 interactive_loop 而非 main()——main() 会重新解析 sys.argv，
    拿不到测试传入的 session_id，会退回 cli_default 造成跨用例污染。

    注意：script 用尽后必须抛 EOFError（而非让 mock 抛 StopIteration），
    才能与真实 input() 在管道/重定向结束时的行为一致。
    """
    import chat_cli

    lines = iter(script)

    def fake_input(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    out = io.StringIO()
    with patch("builtins.input", fake_input), patch("sys.stdout", out):
        code = chat_cli.interactive_loop(session_id, mode)
    return code, out.getvalue()


# ---------------------------------------------------------------- 交互循环

def test_interactive_loop_prints_answer_and_exits(session_id):
    code, output = drive(["你好，我最近有点烦恼", "/exit"], session_id)

    assert code == 0
    assert "恋爱大师 · 控制台对话" in output
    assert session_id in output
    assert "收到你的第 1 句话" in output


def test_multi_turn_history_injected_into_second_prompt(session_id):
    """核心：第二轮发给模型的 messages 里必须带上第一轮的用户输入与回答"""
    drive(["第一句话", "第二句话", "/exit"], session_id)

    assert len(FakeChatModel.captured) == 2, "应发生两次模型调用"
    texts = [getattr(m, "content", "") for m in FakeChatModel.captured[1]]

    assert any("第一句话" in t for t in texts), f"第二轮 prompt 缺少第一轮用户输入：{texts}"
    assert any("收到你的第 1 句话" in t for t in texts), "第二轮 prompt 缺少第一轮回答"


def test_history_command_lists_messages(session_id):
    code, output = drive(["今天有点烦", "/history", "/exit"], session_id)

    assert "当前会话共 2 条消息" in output
    assert "[1] 你：今天有点烦" in output
    assert "[2] 恋爱大师：" in output


def test_mode_command_reports_state(session_id):
    code, output = drive(["/mode", "/exit"], session_id)

    assert f"会话 ID  : {session_id}" in output
    assert "当前模式 : chat" in output
    assert "消息条数 : 0" in output


def test_clear_command_empties_history(session_id):
    code, output = drive(["记一句话", "/clear", "/mode", "/exit"], session_id)

    assert "当前会话历史已清空" in output
    assert "消息条数 : 0" in output


def test_unknown_command_shows_hint(session_id):
    code, output = drive(["/nonsense", "/help", "/exit"], session_id)

    assert "未知命令：/nonsense" in output
    assert "可用命令" in output


def test_empty_input_is_ignored(session_id):
    code, output = drive(["", "   ", "/mode", "/exit"], session_id)

    assert code == 0
    assert len(FakeChatModel.captured) == 0, "空输入不应触发模型调用"


def test_eof_exits_cleanly(session_id):
    """input 抛 EOFError 时应优雅退出，而不是崩栈"""
    code, output = drive([], session_id)

    assert code == 0
    assert "再见" in output


# ---------------------------------------------------------------- 模式切换

@pytest.mark.parametrize(
    "cmd,label",
    [("/rag", "知识库问答"), ("/agent", "智能体推理"), ("/chat", "普通对话")],
)
def test_mode_switch(session_id, cmd, label):
    code, output = drive([cmd, "/mode", "/exit"], session_id)

    assert f"已切换到「{label}」模式" in output
    assert f"当前模式 : {cmd[1:]}" in output


def test_initial_mode_from_argument(session_id):
    code, output = drive(["/mode", "/exit"], session_id, mode="rag")

    assert "当前模式 : rag" in output


# ---------------------------------------------------------------- 报告链路

def test_report_renders_all_sections(session_id):
    code, output = drive(["我单身三年了，很焦虑", "/report", "n", "n", "/exit"], session_id)

    assert "恋爱状态分析报告" in output
    assert "情感阶段：单身" in output
    assert "情绪评分：6/10" in output
    assert "【整体摘要】" in output
    assert "【优势与积极因素】" in output
    assert "【主要问题】" in output
    assert "【潜在风险】" in output
    assert "【行动建议】" in output
    assert "【写在最后】" in output
    assert "扩大接触面" in output
    assert "长期自我否定" in output


def test_report_pdf_render_works(tmp_path):
    """底层 PDF 渲染函数可用（chat_cli 的 /report 导出即调用它）"""
    from app.core import render_report_pdf

    report = LoveReport(
        title="PDF 测试报告",
        summary="测试摘要",
        stage="单身",
        mood_score=5,
        strengths=["优势一"],
        problems=["问题一"],
        suggestions=[{"title": "建议一", "detail": "细节一", "priority": "高"}],
        encouragement="加油",
    )
    target = render_report_pdf(report, tmp_path / "out.pdf")

    assert target.exists()
    assert target.stat().st_size > 0


def test_report_on_empty_history_asks_confirmation(session_id):
    """空会话下用户拒绝，应不生成报告也不调用模型"""
    code, output = drive(["/report", "n", "/exit"], session_id)

    assert "还没有对话内容" in output
    assert len(FakeChatModel.captured) == 0


def test_one_shot_report_rejects_empty_session(session_id):
    import chat_cli

    assert chat_cli.one_shot_report(session_id, export_pdf=False) == 1


def test_one_shot_report_after_conversation(session_id):
    """先对话垫历史，再走非交互报告入口"""
    import chat_cli

    drive(["我很迷茫", "/exit"], session_id)

    assert chat_cli.one_shot_report(session_id, export_pdf=False) == 0


# ---------------------------------------------------------------- RAG 数据源命令

def test_kb_command_reports_local_backend(session_id, monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "local")
    monkeypatch.setattr(settings, "bailian_workspace_id", "")
    monkeypatch.setattr(settings, "bailian_index_id", "")

    code, output = drive(["/kb", "/exit"], session_id)

    assert "RAG_BACKEND=local" in output
    assert "本地向量库" in output
    assert "接口地址" not in output


def test_kb_command_reports_bailian_backend(session_id, monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", "llm-abc123")
    monkeypatch.setattr(settings, "bailian_index_id", "kb_love_001")
    monkeypatch.setattr(settings, "bailian_agent_id", "")

    code, output = drive(["/kb", "/exit"], session_id)

    assert "RAG_BACKEND=bailian" in output
    assert "阿里云百炼知识库" in output
    assert "单库底层检索" in output
    assert "llm-abc123" in output
    assert "kb_love_001" in output


def test_kb_command_warns_on_incomplete_bailian_config(session_id, monkeypatch):
    """配了 bailian 但参数不全，应提示已回退本地"""
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", "")
    monkeypatch.setattr(settings, "bailian_index_id", "")

    code, output = drive(["/kb", "/exit"], session_id)

    assert "自动回退本地向量库" in output


def test_kb_check_runs_connectivity_probe(session_id, monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", "llm-abc123")
    monkeypatch.setattr(settings, "bailian_index_id", "kb_love_001")
    monkeypatch.setattr(settings, "bailian_agent_id", "")

    body = {
        "success": True,
        "data": {"total": 1, "cost_time": 8, "nodes": [
            {"score": 0.9, "text": "自检命中的切片内容", "metadata": {"doc_name": "测试.md"}}
        ]},
    }
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(
            status_code=200,
            content=__import__("json").dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            request=httpx.Request("POST", "https://example.invalid"),
        ),
    )

    code, output = drive(["/kb check", "/exit"], session_id)

    assert "连通性自检" in output
    assert "检索成功" in output
    assert "自检命中的切片内容" in output


def test_kb_check_reports_failure_without_crashing(session_id, monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", "llm-abc123")
    monkeypatch.setattr(settings, "bailian_index_id", "kb_love_001")
    monkeypatch.setattr(settings, "bailian_agent_id", "")

    body = {"success": False, "code": "InvalidApiKey", "message": "invalid key", "request_id": "r1"}
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(
            status_code=401,
            content=__import__("json").dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            request=httpx.Request("POST", "https://example.invalid"),
        ),
    )

    code, output = drive(["/kb check", "/exit"], session_id)

    assert code == 0, "自检失败不应导致进程异常退出"
    assert "检索失败" in output
    assert "鉴权失败" in output


def test_banner_shows_rag_backend(session_id, monkeypatch):
    monkeypatch.setattr(settings, "rag_backend", "bailian")
    monkeypatch.setattr(settings, "bailian_workspace_id", "llm-abc123")
    monkeypatch.setattr(settings, "bailian_index_id", "kb_love_001")

    code, output = drive(["/exit"], session_id)

    assert "RAG 数据源: 百炼知识库" in output


# ---------------------------------------------------------------- 会话隔离

def test_sessions_are_isolated(session_id):
    drive(["只有我说过这句话", "/exit"], session_id)

    other = get_chat_memory(f"{session_id}_other")
    assert other.get_messages() == []
    assert len(get_chat_memory(session_id).get_messages()) == 2
