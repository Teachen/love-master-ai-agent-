"""恋爱大师 - RAG 检索统一入口

按配置把检索请求路由到「本地向量库」或「阿里云百炼知识库」，
上层（chat_with_rag / 恋爱报告 / Agent 工具）无需感知数据源差异。

路由规则由 ``settings.rag_mode`` 决定：
    RAG_BACKEND=local    -> 本地 PGVector / 内存向量库（默认）
    RAG_BACKEND=bailian  -> 百炼控制台中已配置好的知识库

百炼参数不全时 ``rag_mode`` 会自动回退 local，避免配置疏漏导致 RAG 整体不可用。
"""
from typing import Any, Dict, List

from langchain_core.documents import Document

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)


def similarity_search(query: str, k: int = 4, **kwargs) -> List[Document]:
    """相似度检索（按配置路由数据源）

    与本地实现的签名保持一致，便于无缝替换。

    Args:
        query: 检索内容
        k: 召回条数
        **kwargs: 透传给本地向量库的额外参数（百炼模式下忽略）
    """
    if settings.rag_mode == "bailian":
        return _bailian_search(query, k)
    return _local_search(query, k, **kwargs)


def _bailian_search(query: str, k: int) -> List[Document]:
    from app.rag.bailian_kb import BailianKnowledgeError, bailian_similarity_search

    try:
        return bailian_similarity_search(query, k=k)
    except BailianKnowledgeError as exc:
        if not settings.bailian_kb_fallback_local:
            raise
        logger.warning("百炼知识库检索失败，已降级本地向量库：%s", exc)
        return _local_search(query, k)


def _local_search(query: str, k: int, **kwargs) -> List[Document]:
    from app.rag.vector_store import similarity_search as local_search

    return local_search(query, k=k, **kwargs)


def as_retriever(k: int = 4):
    """以 LangChain Retriever 形式返回当前数据源的检索器"""
    if settings.rag_mode == "bailian":
        from app.rag.bailian_kb import as_bailian_retriever

        return as_bailian_retriever(k=k)
    from app.rag.vector_store import as_retriever as local_retriever

    return local_retriever(k=k)


def describe_rag_backend() -> Dict[str, Any]:
    """当前 RAG 数据源诊断信息，供健康检查与排障使用"""
    info: Dict[str, Any] = {
        "configured_backend": settings.rag_backend,
        "active_backend": settings.rag_mode,
        "fallback_to_local_on_error": settings.bailian_kb_fallback_local,
    }
    if settings.rag_mode == "bailian":
        from app.rag.bailian_kb import get_bailian_client

        client = get_bailian_client()
        info.update(
            {
                "bailian_mode": "agent" if client.use_agent else "index",
                "bailian_workspace_id": client.workspace_id,
                "bailian_target": client.agent_id or client.index_id,
                "bailian_region": client.region,
                "bailian_url": client.url,
            }
        )
    return info
