"""恋爱大师 - 控制台交互对话工具

在终端里直接与「恋爱大师」对话，无需启动 HTTP 服务和前端页面。

用法：
    python chat_cli.py                          # 默认 chat 模式，自动生成会话 ID
    python chat_cli.py -s user_001              # 指定会话 ID（可恢复历史）
    python chat_cli.py -m rag                   # 指定模式：chat / rag / agent
    python chat_cli.py -s user_001 -m agent     # 组合使用

    python chat_cli.py --report                 # 非交互：直接对已有会话生成报告

会话内命令（行首输入）：
    /chat  /rag  /agent   切换对话模式
    /report               生成结构化恋爱报告（可再选导出 PDF）
    /history              查看当前会话历史
    /clear                清空当前会话历史
    /mode                 查看当前模式与会话信息
    /help                 查看帮助
    /exit  或  Ctrl+C     退出
"""
import argparse
import sys
from pathlib import Path

# 允许从项目根目录直接运行（也支持 python -m）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agent import get_chat_memory  # noqa: E402
from app.app import LoveApp  # noqa: E402
from app.config import settings  # noqa: E402
from app.schemas import LoveReport  # noqa: E402
from app.utils import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)

# 显示用元数据
_MODES = {
    "chat": ("普通对话", "闲聊与情感咨询，带多轮记忆"),
    "rag": ("知识库问答", "检索恋爱知识库后作答，答案更专业"),
    "agent": ("智能体推理", "可自主调用工具（搜索 / 写文件 / 生成 PDF）"),
}

_HELP = """
────────────────── 可用命令 ──────────────────
  /chat       切换到普通对话模式
  /rag        切换到知识库问答模式
  /agent      切换到智能体推理模式
  /report     生成结构化恋爱报告（可导出 PDF）
  /kb         查看 RAG 数据源（/kb check 做连通性自检）
  /history    查看当前会话历史
  /clear      清空当前会话历史
  /mode       查看当前模式与会话信息
  /help       显示本帮助
  /exit       退出（Ctrl+C 亦可）
─────────────────────────────────────────────
直接输入文字即可对话。
"""


def _indent(text: str, prefix: str = "  ") -> str:
    """给多行文本统一加缩进，保持回答区块整齐"""
    return "\n".join(prefix + line if line.strip() else line for line in text.splitlines())


def _print_rag_backend(check: bool) -> None:
    """展示 RAG 数据源配置；（可选）发起真实检索做连通性自检"""
    from app.rag import check_bailian_kb, describe_rag_backend

    info = describe_rag_backend()
    active = info["active_backend"]
    label = "阿里云百炼知识库" if active == "bailian" else "本地向量库"
    print(f"  配置项    : RAG_BACKEND={info['configured_backend']}")
    print(f"  实际生效  : {active}（{label}）")
    if info["configured_backend"] != active:
        print("  ⚠ 已配置 bailian 但参数不全，已自动回退本地向量库")

    if active == "bailian":
        mode = "跨库联合检索" if info["bailian_mode"] == "agent" else "单库底层检索"
        print(f"  检索方式  : {mode}")
        print(f"  业务空间  : {info['bailian_workspace_id']}")
        print(f"  检索目标  : {info['bailian_target']}")
        print(f"  地域      : {info['bailian_region']}")
        print(f"  接口地址  : {info['bailian_url']}")
        print(f"  失败降级  : {'开启' if info['fallback_to_local_on_error'] else '关闭（直接报错）'}")

    if check:
        print("\n  正在做连通性自检...")
        result = check_bailian_kb() if active == "bailian" else None
        if result is None:
            print("  当前为本地向量库，无需自检（bailian 模式下才会请求百炼）")
        elif result.get("ok"):
            print(f"  ✓ 检索成功，命中 {result.get('hits')} 条")
            if result.get("sample"):
                print(f"    样例：{result['sample']}")
        else:
            print(f"  ✗ 检索失败：{result.get('error')}")
    print()


def _print_banner(session_id: str, mode: str) -> None:
    llm_status = "已就绪" if settings.llm_ready else "未配置（仅接口可用，实际调用会报错）"
    rag_label = "百炼知识库" if settings.rag_mode == "bailian" else "本地向量库"
    print("=" * 58)
    print("  恋爱大师 · 控制台对话")
    print("=" * 58)
    print(f"  会话 ID  : {session_id}")
    print(f"  当前模式 : {mode} —— {_MODES[mode][0]}")
    print(f"  对话模型 : {settings.dashscope_chat_model}")
    print(f"  大模型   : {llm_status}")
    print(f"  RAG 数据源: {rag_label}")
    print("=" * 58)
    print("  输入 /help 查看命令，/exit 退出")
    print()


def _print_history(love_app: LoveApp) -> None:
    history = love_app.get_history()
    if not history:
        print("  （当前会话暂无历史）\n")
        return
    print(f"  当前会话共 {len(history)} 条消息：\n")
    for i, msg in enumerate(history, 1):
        who = "你" if msg["role"] == "user" else "恋爱大师"
        text = msg["content"].replace("\n", "\n" + " " * 10)
        print(f"  [{i}] {who}：{text}")
    print()


def _render_report(report: LoveReport) -> None:
    """把结构化报告打印到控制台"""
    line = "─" * 58
    print(f"\n{line}")
    print(f"  {report.title}")
    print(line)
    print(f"  情感阶段：{report.stage}    情绪评分：{report.mood_score}/10")
    if report.used_knowledge_base:
        print("  （已参考恋爱知识库）")
    print(f"\n【整体摘要】\n  {report.summary}")

    print("\n【优势与积极因素】")
    for item in report.strengths:
        print(f"  ✓ {item}")

    print("\n【主要问题】")
    for item in report.problems:
        print(f"  ! {item}")

    print("\n【潜在风险】")
    if report.risks:
        for risk in report.risks:
            print(f"  ▲ [{risk.severity}] {risk.risk}")
            print(f"      应对：{risk.advice}")
    else:
        print("  暂未发现明显风险。")

    print("\n【行动建议】")
    for idx, sug in enumerate(report.suggestions, 1):
        print(f"  {idx}. [{sug.priority}] {sug.title}")
        print(f"     {sug.detail}")

    print(f"\n【写在最后】\n  {report.encouragement}")
    print(f"{line}\n")


def _handle_report(love_app: LoveApp, session_id: str) -> None:
    """生成报告，询问是否导出 PDF"""
    if not love_app.get_history():
        print("  ⚠ 当前会话还没有对话内容，建议先聊几句再生成报告。")
        answer = input("  仍要生成初步报告吗？(y/N) ").strip().lower()
        if answer not in ("y", "yes"):
            print()
            return

    try:
        use_rag = input("  是否参考知识库？(Y/n) ").strip().lower() not in ("n", "no")
    except (EOFError, KeyboardInterrupt):
        use_rag = False

    if use_rag:
        print("  ℹ 参考知识库需调用向量检索（未配 PGVector 时会降级为内存库）")

    print("  正在生成报告，请稍候...\n")
    try:
        report = love_app.generate_report(use_rag=use_rag)
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ 报告生成失败：{exc}\n")
        logger.exception("报告生成失败")
        return

    _render_report(report)

    try:
        export = input("  是否导出 PDF？(y/N) ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        export = False

    if export:
        from app.core import render_report_pdf

        try:
            path = render_report_pdf(report)
            print(f"  ✓ PDF 已导出：{path}\n")
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ PDF 导出失败：{exc}\n")


def _handle_command(raw: str, love_app: LoveApp, state: dict) -> bool:
    """处理命令。返回 False 表示应退出。"""
    cmd = raw.strip().lower()

    if cmd in ("/exit", "/quit", "/q"):
        return False

    if cmd == "/help":
        print(_HELP)
        return True

    if cmd == "/mode":
        mode = state["mode"]
        print(f"  会话 ID  : {state['session_id']}")
        print(f"  当前模式 : {mode} —— {_MODES[mode][0]}（{_MODES[mode][1]}）")
        print(f"  消息条数 : {len(love_app.get_history())}\n")
        return True

    if cmd == "/history":
        _print_history(love_app)
        return True

    if cmd == "/clear":
        love_app.clear_history()
        print("  ✓ 当前会话历史已清空\n")
        return True

    if cmd == "/report":
        _handle_report(love_app, state["session_id"])
        return True

    if cmd == "/kb" or cmd.startswith("/kb "):
        # /kb check 额外做一次真实检索自检
        _print_rag_backend(check=cmd.endswith("check"))
        return True

    if cmd in ("/chat", "/rag", "/agent"):
        state["mode"] = cmd[1:]
        print(f"  ✓ 已切换到「{_MODES[state['mode']][0]}」模式\n")
        return True

    print(f"  未知命令：{raw}\n  输入 /help 查看可用命令\n")
    return True


def _send(message: str, love_app: LoveApp, mode: str) -> None:
    """按模式发送消息并打印回答"""
    print("\n  恋爱大师：")
    try:
        if mode == "rag":
            answer = love_app.chat_with_rag(message)
        elif mode == "agent":
            answer = love_app.run_agent(message)
        else:
            answer = love_app.chat(message)
    except KeyboardInterrupt:
        print("  （已取消本轮）\n")
        return
    except RuntimeError as exc:
        print(f"  ✗ {exc}\n")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ 对话失败：{exc}\n")
        logger.exception("对话失败")
        return

    # agent 模式内部会自行打印，其余两种在这里补打
    if mode != "agent":
        # 缩进两格输出回答，与上方「恋爱大师：」形成视觉分区；
        # 业务日志（如「对话完成」）会插在标签与回答之间，不再挤在同一行。
        print(_indent(answer))
    print()


def interactive_loop(session_id: str, mode: str) -> int:
    """交互式对话主循环"""
    love_app = LoveApp(session_id=session_id)
    state = {"mode": mode, "session_id": session_id}

    _print_banner(session_id, mode)

    existing = len(love_app.get_history())
    if existing:
        print(f"  ℹ 已载入该会话的 {existing} 条历史消息（输入 /history 查看）\n")

    while True:
        try:
            raw = input(f"[{_MODES[state['mode']][0]}] 你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  再见！\n")
            return 0

        if not raw:
            continue

        if raw.startswith("/"):
            if not _handle_command(raw, love_app, state):
                print("  再见！\n")
                return 0
            continue

        _send(raw, love_app, state["mode"])


def one_shot_report(session_id: str, export_pdf: bool) -> int:
    """非交互模式：直接为指定会话生成报告"""
    love_app = LoveApp(session_id=session_id)
    count = len(love_app.get_history())
    if not count:
        print(f"✗ 会话 {session_id} 没有任何对话历史，无法生成报告。")
        print("  请先运行 python chat_cli.py -s "
              f"{session_id} 进行对话。")
        return 1

    print(f"正在为会话 {session_id}（{count} 条消息）生成报告...\n")
    try:
        report = love_app.generate_report(use_rag=True)
    except Exception as exc:  # noqa: BLE001
        print(f"✗ 报告生成失败：{exc}")
        return 1

    _render_report(report)

    if export_pdf:
        from app.core import render_report_pdf

        try:
            print(f"✓ PDF 已导出：{render_report_pdf(report)}")
        except Exception as exc:  # noqa: BLE001
            print(f"✗ PDF 导出失败：{exc}")
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="恋爱大师控制台对话工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python chat_cli.py                      # 默认 chat 模式\n"
            "  python chat_cli.py -s user_001 -m rag   # 指定会话与模式\n"
            "  python chat_cli.py --report -s user_001 # 直接生成报告\n"
        ),
    )
    parser.add_argument(
        "-s", "--session-id", default="cli_default", help="会话 ID（默认 cli_default）"
    )
    parser.add_argument(
        "-m", "--mode", default="chat", choices=list(_MODES), help="对话模式（默认 chat）"
    )
    parser.add_argument(
        "--report", action="store_true", help="非交互：直接为已有会话生成报告"
    )
    parser.add_argument("--pdf", action="store_true", help="配合 --report 导出 PDF")
    args = parser.parse_args()

    setup_logging()

    if args.report:
        return one_shot_report(args.session_id, args.pdf)
    return interactive_loop(args.session_id, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
