"""恋爱大师 - 工具函数集

对应 Java 版 tools 包：FileOperationTool / PDFGenerationTool /
ResourceDownloadTool / WebScrapingTool / WebSearchTool / TerminateTool。
"""
import os
import re
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# 危险字符，防止路径穿越
_UNSAFE_CHARS = re.compile(r"[\\/:*?\"<>|]")


def _safe_name(name: str) -> str:
    """清洗文件名，防止路径穿越"""
    cleaned = _UNSAFE_CHARS.sub("_", name).strip(". ")
    return cleaned or "unnamed"


# ============================================================
# 1. 文件写入
# ============================================================
@tool
def write_file(filename: str, content: str) -> str:
    """把文本内容写入文件。参数 filename 为文件名，content 为文件内容。"""
    directory = Path(settings.file_save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / _safe_name(filename)
    target.write_text(content, encoding="utf-8")
    logger.info("文件已写入: %s", target)
    return f"文件写入成功：{target}"


# ============================================================
# 2. 文件读取
# ============================================================
@tool
def read_file(filename: str) -> str:
    """读取指定文件的内容。参数 filename 为文件名。"""
    target = Path(settings.file_save_dir) / _safe_name(filename)
    if not target.exists():
        return f"文件不存在：{target}"
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return target.read_text(encoding="gbk", errors="ignore")


# ============================================================
# 3. 资源下载
# ============================================================
@tool
def download_resource(url: str, filename: Optional[str] = None) -> str:
    """下载网络资源到本地。参数 url 为资源地址，filename 为可选保存文件名。"""
    if not url.startswith(("http://", "https://")):
        return "下载失败：URL 必须以 http:// 或 https:// 开头"

    directory = Path(settings.file_save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    save_name = _safe_name(filename or url.split("/")[-1] or "download.bin")
    target = directory / save_name

    try:
        with requests.get(url, timeout=30, stream=True) as resp:
            resp.raise_for_status()
            with open(target, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
    except Exception as exc:  # noqa: BLE001
        logger.warning("资源下载失败: %s", exc)
        return f"下载失败：{exc}"

    logger.info("资源已下载: %s", target)
    return f"下载成功：{target}（{target.stat().st_size} 字节）"


# ============================================================
# 4. 网页抓取
# ============================================================
@tool
def scrape_webpage(url: str, max_chars: int = 3000) -> str:
    """抓取网页正文内容。参数 url 为网页地址，max_chars 为最大返回字数。"""
    if not url.startswith(("http://", "https://")):
        return "抓取失败：URL 必须以 http:// 或 https:// 开头"
    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LoveMaster/1.0)"},
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = re.sub(r"\n{2,}", "\n", soup.get_text(separator="\n", strip=True))
        return text[:max_chars]
    except Exception as exc:  # noqa: BLE001
        logger.warning("网页抓取失败: %s", exc)
        return f"抓取失败：{exc}"


# ============================================================
# 5. 联网搜索（需配置 SEARCH_API_KEY）
# ============================================================
@tool
def web_search(query: str, num_results: int = 5) -> str:
    """联网搜索实时信息。参数 query 为搜索关键词，num_results 为返回条数。"""
    if not settings.search_api_key:
        return "搜索功能未启用：请在 .env 中配置 SEARCH_API_KEY"

    try:
        from serpapi import GoogleSearch  # type: ignore

        result = GoogleSearch(
            {"q": query, "num": num_results, "api_key": settings.search_api_key}
        ).get_dict()
        items = result.get("organic_results", [])[:num_results]
        if not items:
            return "未搜索到相关结果"
        return "\n\n".join(
            f"{i + 1}. {it.get('title', '')}\n{it.get('snippet', '')}\n{it.get('link', '')}"
            for i, it in enumerate(items)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("搜索失败: %s", exc)
        return f"搜索失败：{exc}"


# ============================================================
# 6. PDF 报告生成（需安装 reportlab）
# ============================================================
@tool
def generate_pdf(title: str, content: str) -> str:
    """把内容生成为 PDF 报告。参数 title 为标题，content 为正文内容。"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError:
        return "PDF 生成功能未启用：请执行 pip install reportlab"

    directory = Path(settings.pdf_save_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{_safe_name(title)}.pdf"

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        pdf = canvas.Canvas(str(target), pagesize=A4)
        width, height = A4
        pdf.setFont("STSong-Light", 16)
        pdf.drawString(50, height - 60, title)
        pdf.setFont("STSong-Light", 11)
        y = height - 100
        for line in content.split("\n"):
            if y < 60:
                pdf.showPage()
                pdf.setFont("STSong-Light", 11)
                y = height - 60
            pdf.drawString(50, y, line[:70])
            y -= 18
        pdf.save()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF 生成失败: %s", exc)
        return f"PDF 生成失败：{exc}"

    logger.info("PDF 已生成: %s", target)
    return f"PDF 生成成功：{target}"


# ============================================================
# 7. 终止工具（ReAct 循环显式结束）
# ============================================================
@tool
def terminate(reason: str = "任务完成") -> str:
    """当任务已完成时调用此工具结束流程。参数 reason 为结束原因。"""
    return f"任务已终止：{reason}"


# ============================================================
# 8. 知识库检索工具
# ============================================================
@tool
def search_love_knowledge(query: str) -> str:
    """从恋爱知识库中检索相关资料。参数 query 为检索关键词或问题。"""
    from app.rag import similarity_search

    try:
        docs = similarity_search(query, k=4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("知识库检索失败: %s", exc)
        return f"知识库检索失败：{exc}"

    if not docs:
        return "知识库中未找到相关资料"
    return "\n\n---\n\n".join(
        f"[来源: {d.metadata.get('source', '未知')}]\n{d.page_content}" for d in docs
    )


# ---------- 工具注册表 ----------
ALL_TOOLS = [
    search_love_knowledge,
    write_file,
    read_file,
    download_resource,
    scrape_webpage,
    web_search,
    generate_pdf,
    terminate,
]
