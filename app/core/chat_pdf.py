"""恋爱大师 - 对话记录 PDF 导出

把一次会话的多轮对话渲染成中文 PDF，供前端「历史记录 → 导出 PDF」使用。

实现要点：
- 复用 report_pdf 的排版思路：reportlab + 内置 CID 中文字体（STSong-Light），
  不依赖任何外部字体文件，云上镜像零额外资源即可生成中文 PDF
- 用户 / AI 消息用不同缩进与标记区分，保留原始换行（对话里常有分点建议）
- 长内容自动分页

依赖 reportlab，未安装时抛 RuntimeError，由接口层转成 500 提示。
"""
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

_FONT = "STSong-Light"

_MARGIN = 50
_BODY_SIZE = 10.5
_HEAD_SIZE = 14
_TITLE_SIZE = 17
_LEADING = 16
_WRAP_CHARS = 40  # 每行大致字符数（中文按全角计）

# 角色显示名与标记
_ROLE_LABEL = {"user": "我", "ai": "AI", "assistant": "AI", "system": "系统"}


def _wrap(text: str) -> list[str]:
    """按显示宽度折行：全角字符按 2 列计算，兼容中英混排"""
    lines: list[str] = []
    for raw in str(text).split("\n"):
        raw = raw.rstrip()
        if not raw:
            lines.append("")
            continue
        buf, width = "", 0
        for ch in raw:
            w = 2 if ord(ch) > 127 else 1
            if width + w > _WRAP_CHARS:
                lines.append(buf)
                buf, width = "", 0
            buf += ch
            width += w
        lines.append(buf)
    return lines


def render_chat_pdf(
    messages: list[dict],
    title: str = "对话记录",
    chat_id: str = "",
    target: Path | None = None,
) -> Path:
    """把对话记录渲染为 PDF，返回文件路径。

    Args:
        messages: [{"role": "user"|"ai", "content": str, "time": str}, ...]
        title: PDF 标题
        chat_id: 会话 ID（展示用）
        target: 输出路径，None 时落到 settings.pdf_save_dir

    Raises:
        RuntimeError: reportlab 未安装
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PDF 导出需要 reportlab，请执行：pip install reportlab"
        ) from exc

    pdfmetrics.registerFont(UnicodeCIDFont(_FONT))

    if target is None:
        directory = Path(settings.pdf_save_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{chat_id}" if chat_id else ""
        target = directory / f"chat{suffix}_{stamp}.pdf"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    width, height = A4
    pdf = canvas.Canvas(str(target), pagesize=A4)
    y = height - _MARGIN

    def new_page_if_needed(needed: float = _LEADING) -> None:
        nonlocal y
        if y - needed < _MARGIN:
            pdf.showPage()
            y = height - _MARGIN

    # ---------- 标题区 ----------
    pdf.setFont(_FONT, _TITLE_SIZE)
    pdf.drawString(_MARGIN, y, str(title)[:30])
    y -= _TITLE_SIZE * 1.6

    pdf.setFont(_FONT, 9)
    meta = f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if chat_id:
        meta += f"　|　会话 ID：{chat_id}"
    meta += f"　|　共 {len([m for m in messages if m.get('role') == 'user'])} 轮对话"
    pdf.drawString(_MARGIN, y, meta)
    y -= _LEADING * 1.2

    # 分隔线
    pdf.setLineWidth(0.6)
    pdf.line(_MARGIN, y + 6, width - _MARGIN, y + 6)
    y -= 12

    # ---------- 正文：逐条消息 ----------
    for msg in messages:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", "") or "")
        if not content.strip():
            continue
        label = _ROLE_LABEL.get(role, role or "未知")
        stamp = str(msg.get("time", "") or "")

        # 消息头：角色 + 时间
        new_page_if_needed(_LEADING * 2)
        pdf.setFont(_FONT, 11)
        head = f"{label}："
        if stamp:
            head += f"（{stamp}）"
        pdf.drawString(_MARGIN, y, head)
        y -= _LEADING

        # 消息体：缩进排版，保留换行
        pdf.setFont(_FONT, _BODY_SIZE)
        for line in _wrap(content):
            new_page_if_needed()
            pdf.drawString(_MARGIN + 16, y, line)
            y -= _LEADING

        y -= 10  # 消息间距

        # 每轮对话后画一条浅分隔线
        if y > _MARGIN:
            pdf.setLineWidth(0.3)
            pdf.line(_MARGIN + 16, y + 6, width - _MARGIN, y + 6)
        y -= 6

    pdf.save()
    logger.info("对话记录 PDF 已生成: %s", target)
    return target
