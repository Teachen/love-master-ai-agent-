"""恋爱大师 - 报告 PDF 渲染

把结构化的 LoveReport 渲染为中文 PDF。

与 tools/love_tools.py 的 generate_pdf 的区别：
- generate_pdf 是 ReAct Agent 自主调用的通用工具，接收模型拼好的纯文本
- 本模块专为 LoveReport 设计，按结构分节排版，标题 / 评分 / 列表层级清晰

依赖 reportlab，未安装时抛出 RuntimeError，由调用方决定是否降级。
"""
import textwrap
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.rag.prompts import REPORT_PDF_TITLE_PREFIX
from app.schemas import LoveReport, LoveSuggestion, RiskItem
from app.utils import get_logger

logger = get_logger(__name__)

_FONT = "STSong-Light"

# 排版常量
_MARGIN = 50
_BODY_SIZE = 10.5
_HEAD_SIZE = 13
_TITLE_SIZE = 18
_LEADING = 16
_WRAP_CHARS = 42  # 每行大致字符数（中文按全角计）


def _wrap(text: str) -> list[str]:
    """按显示宽度折行，兼容中英混排"""
    lines: list[str] = []
    for raw in str(text).split("\n"):
        raw = raw.rstrip()
        if not raw:
            lines.append("")
            continue
        lines.extend(
            textwrap.wrap(raw, width=_WRAP_CHARS, break_long_words=True) or [""]
        )
    return lines


class _Writer:
    """带分页与光标的极简 PDF 写入器"""

    def __init__(self, pdf, width: float, height: float):
        self.pdf = pdf
        self.width = width
        self.height = height
        self.y = height - _MARGIN

    def _new_page_if_needed(self, needed: float = _LEADING) -> None:
        if self.y - needed < _MARGIN:
            self.pdf.showPage()
            self.y = self.height - _MARGIN

    def title(self, text: str) -> None:
        self._new_page_if_needed(_TITLE_SIZE * 2)
        self.pdf.setFont(_FONT, _TITLE_SIZE)
        self.pdf.drawString(_MARGIN, self.y, text[:_WRAP_CHARS])
        self.y -= _TITLE_SIZE * 1.8

    def subtitle(self, text: str) -> None:
        self._new_page_if_needed(_LEADING)
        self.pdf.setFont(_FONT, 9)
        self.pdf.drawString(_MARGIN, self.y, text)
        self.y -= _LEADING * 1.2

    def heading(self, text: str) -> None:
        self._new_page_if_needed(_HEAD_SIZE * 2)
        self.y -= 6
        self.pdf.setFont(_FONT, _HEAD_SIZE)
        self.pdf.drawString(_MARGIN, self.y, text)
        self.y -= _LEADING
        # 分隔线
        self.pdf.setLineWidth(0.5)
        self.pdf.line(_MARGIN, self.y + 4, self.width - _MARGIN, self.y + 4)
        self.y -= 6

    def body(self, text: str, indent: float = 0, bold: bool = False) -> None:
        self.pdf.setFont(_FONT, _BODY_SIZE)
        for line in _wrap(text):
            self._new_page_if_needed()
            self.pdf.drawString(_MARGIN + indent, self.y, line)
            self.y -= _LEADING

    def bullet(self, text: str, marker: str = "·") -> None:
        """带符号的列表项，悬挂缩进"""
        self.pdf.setFont(_FONT, _BODY_SIZE)
        lines = _wrap(text)
        for i, line in enumerate(lines):
            self._new_page_if_needed()
            if i == 0:
                self.pdf.drawString(_MARGIN + 6, self.y, marker)
            self.pdf.drawString(_MARGIN + 20, self.y, line)
            self.y -= _LEADING

    def gap(self, size: float = 6) -> None:
        self.y -= size


def render_report_pdf(report: LoveReport, target: Path | None = None) -> Path:
    """把 LoveReport 渲染为 PDF，返回文件路径。

    Raises:
        RuntimeError: reportlab 未安装
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "PDF 导出需要 reportlab，请执行：pip install reportlab"
        ) from exc

    pdfmetrics.registerFont(UnicodeCIDFont(_FONT))

    if target is None:
        directory = Path(settings.pdf_save_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = directory / f"love_report_{stamp}.pdf"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    width, height = A4
    pdf = canvas.Canvas(str(target), pagesize=A4)
    w = _Writer(pdf, width, height)

    # ---------- 封面标题 ----------
    w.title(report.title or REPORT_PDF_TITLE_PREFIX)
    w.subtitle(
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        f"　|　情感阶段：{report.stage}"
        f"　|　情绪评分：{report.mood_score}/10"
        + ("　|　已参考知识库" if report.used_knowledge_base else "")
    )

    # ---------- 摘要 ----------
    w.heading("一、整体摘要")
    w.body(report.summary)

    # ---------- 优势 ----------
    w.heading("二、优势与积极因素")
    for item in report.strengths:
        w.bullet(item, "✓")

    # ---------- 问题 ----------
    w.heading("三、主要问题")
    for item in report.problems:
        w.bullet(item, "!")

    # ---------- 风险 ----------
    w.heading("四、潜在风险")
    if report.risks:
        for risk in report.risks:
            w.bullet(f"【{risk.severity}】{risk.risk}", "▲")
            w.body(f"应对：{risk.advice}", indent=20)
    else:
        w.body("暂未发现明显风险。")

    # ---------- 建议 ----------
    w.heading("五、行动建议")
    for idx, sug in enumerate(report.suggestions, 1):
        w.bullet(f"{idx}. [{sug.priority}] {sug.title}", "")
        w.body(sug.detail, indent=20)

    # ---------- 鼓励 ----------
    w.heading("六、写在最后")
    w.body(report.encouragement)

    pdf.save()
    logger.info("恋爱报告 PDF 已生成: %s", target)
    return target
