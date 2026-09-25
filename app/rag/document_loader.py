"""恋爱大师 - 恋爱知识文档加载与切分

对应 Java 版 LoveAppDocumentLoader / MyTokenTextSplitter。
"""
import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils import get_logger

logger = get_logger(__name__)

# 恋爱知识库文档目录
DOCUMENT_DIR = Path(__file__).parent / "documents"

# 知识库主题分类，与 Java 版文档一一对应
KNOWLEDGE_TOPICS = ["单身篇", "恋爱篇", "已婚篇"]


def _read_markdown(path: Path) -> str:
    """读取 Markdown 文本（自动兼容 UTF-8 / GBK）"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="ignore")


def load_documents(document_dir: Path | None = None) -> List[Document]:
    """加载恋爱知识库全部 Markdown 文档"""
    target_dir = document_dir or DOCUMENT_DIR
    if not target_dir.exists():
        logger.warning("知识库目录不存在: %s", target_dir)
        return []

    documents: List[Document] = []
    for path in sorted(target_dir.glob("*.md")):
        content = _read_markdown(path)
        if not content.strip():
            continue
        documents.append(
            Document(
                page_content=content,
                metadata={"source": path.name, "file_path": str(path)},
            )
        )
    logger.info("加载知识库文档 %d 篇", len(documents))
    return documents


def split_documents(
    documents: List[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> List[Document]:
    """切分文档为向量库友好的文本块"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    logger.info("文档切分完成，共 %d 个文本块", len(chunks))
    return chunks


def load_and_split(document_dir: Path | None = None) -> List[Document]:
    """加载并切分知识库，返回可直接入库的文本块"""
    return split_documents(load_documents(document_dir))


def ensure_directories() -> None:
    """确保运行时应存在的数据目录"""
    for directory in ("./tmp/files", "./tmp/pdf", "./data"):
        os.makedirs(directory, exist_ok=True)
