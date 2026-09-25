"""恋爱大师 - 模型层"""
from app.models.llm_factory import (
    get_chat_model,
    get_embedding_model,
    get_ollama_chat_model,
)

__all__ = ["get_chat_model", "get_embedding_model", "get_ollama_chat_model"]
