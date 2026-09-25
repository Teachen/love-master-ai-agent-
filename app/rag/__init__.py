"""恋爱大师 - RAG 知识库检索包

对外暴露统一的检索入口：
    similarity_search / as_retriever 按 settings.rag_mode 自动路由到
    「本地向量库」或「阿里云百炼知识库」，调用方无需区分。
"""
from app.rag.bailian_kb import (
    BailianKnowledgeClient,
    BailianKnowledgeError,
    BailianKnowledgeRetriever,
    as_bailian_retriever,
    bailian_similarity_search,
    check_bailian_kb,
    get_bailian_client,
)
from app.rag.document_loader import (
    KNOWLEDGE_TOPICS,
    load_and_split,
    load_documents,
    split_documents,
)
from app.rag.retriever import (
    as_retriever,
    describe_rag_backend,
    similarity_search,
)
from app.rag.vector_store import (
    build_knowledge_base,
    get_vector_store,
    reset_vector_store,
)

__all__ = [
    # 文档加载
    "KNOWLEDGE_TOPICS",
    "load_documents",
    "split_documents",
    "load_and_split",
    # 统一检索入口（按配置路由）
    "similarity_search",
    "as_retriever",
    "describe_rag_backend",
    # 本地向量库
    "get_vector_store",
    "build_knowledge_base",
    "reset_vector_store",
    # 阿里云百炼知识库
    "BailianKnowledgeClient",
    "BailianKnowledgeRetriever",
    "BailianKnowledgeError",
    "get_bailian_client",
    "bailian_similarity_search",
    "as_bailian_retriever",
    "check_bailian_kb",
]
