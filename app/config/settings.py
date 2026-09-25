"""恋爱大师 - 统一配置管理

所有配置项均可通过环境变量或 .env 文件覆盖。
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 服务基础配置 ----------
    app_name: str = Field(default="恋爱大师", description="应用名称")
    app_env: str = Field(default="dev", description="运行环境")
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8000, description="监听端口")
    debug: bool = Field(default=True, description="调试模式")
    cors_origins: List[str] = Field(default=["*"], description="允许的跨域来源")

    # ---------- 阿里云百炼 ----------
    dashscope_api_key: str = Field(default="", description="DashScope API Key")
    dashscope_chat_model: str = Field(default="qwen-plus", description="对话模型")
    dashscope_embedding_model: str = Field(
        default="text-embedding-v3", description="向量模型"
    )

    # ---------- RAG 数据源：本地向量库 / 百炼知识库 ----------
    rag_backend: str = Field(
        default="local",
        description="RAG 数据源：local=本地向量库 / bailian=阿里云百炼知识库",
    )
    bailian_workspace_id: str = Field(
        default="", description="百炼业务空间 ID，形如 llm-xxxxxxxxxxxx"
    )
    bailian_region: str = Field(
        default="cn-beijing", description="百炼服务地域，如 cn-beijing / ap-southeast-1"
    )
    bailian_index_id: str = Field(
        default="", description="百炼知识库 ID，用于单库底层检索"
    )
    bailian_agent_id: str = Field(
        default="", description="百炼知识检索服务 ID（形如 aid-xxx），用于跨库联合检索"
    )
    bailian_kb_top_k: int = Field(default=5, description="百炼检索默认召回条数")
    bailian_kb_timeout: float = Field(default=30.0, description="百炼检索超时（秒）")
    bailian_kb_fallback_local: bool = Field(
        default=False, description="百炼检索失败时是否降级到本地向量库"
    )

    # ---------- PGVector ----------
    pgvector_host: str = Field(default="localhost")
    pgvector_port: int = Field(default=5432)
    pgvector_database: str = Field(default="love_master")
    pgvector_user: str = Field(default="postgres")
    pgvector_password: str = Field(default="postgres")
    pgvector_table: str = Field(default="love_vectors")

    # ---------- Ollama ----------
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_chat_model: str = Field(default="qwen2.5:7b")

    # ---------- 第三方接口 ----------
    search_api_key: str = Field(default="")
    pexels_api_key: str = Field(default="")

    # ---------- 文件存储 ----------
    file_save_dir: str = Field(default="./tmp/files")
    pdf_save_dir: str = Field(default="./tmp/pdf")

    # ---------- 前置鉴权（HTTP 拦截器） ----------
    api_key_enabled: bool = Field(
        default=False, description="是否开启 API Key 前置鉴权"
    )
    # 用 str 接收，兼容 .env 里逗号分隔写法（pydantic-settings 对 List 字段要求 JSON）
    api_keys: str = Field(default="", description="有效 API Key，英文逗号分隔")

    # ---------- LLM 调用日志（对应 Java MyLoggerAdvisor） ----------
    llm_log_enabled: bool = Field(
        default=True, description="成对打印每次 LLM 调用的请求/响应日志"
    )
    llm_log_max_chars: int = Field(
        default=200, description="日志中每条消息的最大截断长度"
    )

    # ---------- 派生属性 ----------
    @property
    def api_key_list(self) -> List[str]:
        """解析后的有效 API Key 列表"""
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def pgvector_connection_string(self) -> str:
        """PGVector 连接串"""
        return (
            f"postgresql+psycopg://{self.pgvector_user}:{self.pgvector_password}"
            f"@{self.pgvector_host}:{self.pgvector_port}/{self.pgvector_database}"
        )

    @property
    def llm_ready(self) -> bool:
        """大模型是否已配置"""
        return bool(self.dashscope_api_key) and not self.dashscope_api_key.startswith("sk-xxx")

    @property
    def bailian_kb_ready(self) -> bool:
        """百炼知识库是否具备调用条件（需业务空间 ID + 知识库 ID 或检索服务 ID）"""
        has_space = bool(self.bailian_workspace_id.strip())
        has_target = bool(self.bailian_index_id.strip() or self.bailian_agent_id.strip())
        return has_space and has_target

    @property
    def rag_mode(self) -> str:
        """实际生效的 RAG 数据源。

        配了 rag_backend=bailian 但参数不全时，自动回退 local，
        避免因漏填配置导致整个 RAG 链路不可用。
        """
        if self.rag_backend.strip().lower() == "bailian":
            if self.bailian_kb_ready:
                return "bailian"
            return "local"
        return "local"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
