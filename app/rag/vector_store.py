"""恋爱大师 - PGVector 向量库管理

对应 Java 版 PgVectorVectorStoreConfig。
PGVector 不可用时可自动降级为内存向量库，保证项目能跑起来。
"""
from typing import Optional

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

_vector_store = None


def get_vector_store(allow_fallback: bool = True):
    """获取向量库实例（优先 PGVector，失败则降级内存库）"""
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    from app.models import get_embedding_model

    embeddings = get_embedding_model()

    try:
        from langchain_postgres import PGVector

        _vector_store = PGVector(
            connection=settings.pgvector_connection_string,
            collection_name=settings.pgvector_table,
            embeddings=embeddings,
            use_jsonb=True,
        )
        logger.info("PGVector 向量库已连接: %s/%s",
                    settings.pgvector_host, settings.pgvector_database)
        return _vector_store
    except Exception as exc:  # noqa: BLE001
        if not allow_fallback:
            raise
        logger.warning("PGVector 连接失败(%s)，降级为内存向量库", exc)

    from langchain_core.vectorstores import InMemoryVectorStore

    _vector_store = InMemoryVectorStore(embedding=embeddings)
    logger.info("已启用内存向量库（重启后数据丢失，生产环境请配置 PGVector）")
    return _vector_store


def build_knowledge_base(force_rebuild: bool = False) -> int:
    """构建/刷新恋爱知识库，返回入库文本块数量"""
    from app.rag.document_loader import load_and_split

    chunks = load_and_split()
    if not chunks:
        logger.warning("知识库为空，跳过入库")
        return 0

    store = get_vector_store()
    if force_rebuild:
        try:
            store.delete_collection()
            logger.info("已清空旧向量集合")
        except Exception as exc:  # noqa: BLE001
            logger.debug("清空集合跳过: %s", exc)

    store.add_documents(chunks)
    logger.info("知识库构建完成，入库 %d 个文本块", len(chunks))
    return len(chunks)


def similarity_search(query: str, k: int = 4, **kwargs):
    """向量相似度检索"""
    store = get_vector_store()
    return store.similarity_search(query, k=k, **kwargs)


def as_retriever(k: int = 4):
    """以 Retriever 形式返回，便于接入 LCEL 链"""
    store = get_vector_store()
    return store.as_retriever(search_kwargs={"k": k})


def reset_vector_store() -> None:
    """重置全局向量库句柄（配置变更后使用）"""
    global _vector_store
    _vector_store = None
