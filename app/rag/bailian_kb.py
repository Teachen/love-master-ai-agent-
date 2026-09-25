"""恋爱大师 - 阿里云百炼知识库检索

把百炼（Knowledge Studio）的知识库检索接口包装成 LangChain Retriever，
使 chat_with_rag / 恋爱报告无需改动即可改用百炼控制台中已配置好的知识库。

支持两种检索路径，按配置自动选择：

1. **单知识库底层检索**（只配 ``BAILIAN_INDEX_ID``）
   ``POST /api/v1/indices/rag/index/retrieve``
   只做「向量 + 关键词」召回，不在此层做 Rerank，返回结果按原始分数排序。

2. **跨知识库联合检索**（配了 ``BAILIAN_AGENT_ID``，优先）
   ``POST /api/v1/indices/knowledge/search``
   检索策略（多库权重、知识路由、混排模型）预先在控制台配置并发布，
   调用方只需传检索意图 + agent_id。

两种路径共用：
- 服务地址 ``https://{workspaceId}.{region}.maas.aliyuncs.com``
- 鉴权头 ``Authorization: Bearer <DASHSCOPE_API_KEY>``
- 响应统一结构，**必须以 ``success`` 字段判定成功**，不能只看 HTTP 状态码

官方文档：
- 快速开始 https://docs.rag.bailian.aliyun.com/getting-started/quickstart
- 知识检索 https://help.aliyun.com/zh/model-studio/rag-knowledge-retrieval
- 接口参考 https://help.aliyun.com/zh/model-studio/knowledgesearch
"""
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# 两条检索路径
_ENDPOINT_INDEX_RETRIEVE = "/api/v1/indices/rag/index/retrieve"
_ENDPOINT_KNOWLEDGE_SEARCH = "/api/v1/indices/knowledge/search"


class BailianKnowledgeError(RuntimeError):
    """百炼知识库调用异常"""


def _join_url(workspace_id: str, region: str, path: str) -> str:
    return f"https://{workspace_id}.{region}.maas.aliyuncs.com{path}"


def _pick(value: Optional[str], default: str) -> str:
    """显式传参优先，仅在传 None 时回退默认值。

    不能用 `value or default`：那会把显式传入的空串也替换成默认值，
    导致「我就是要空」无法表达——配置校验也就形同虚设。
    """
    return default if value is None else value


class BailianKnowledgeClient:
    """百炼知识库检索客户端（薄封装，无状态）

    所有参数默认取全局配置，也可显式传入以便测试或多空间切换。
    显式传入空串即表示该字段为空，不会再回退到全局配置。
    """

    def __init__(
        self,
        workspace_id: Optional[str] = None,
        api_key: Optional[str] = None,
        index_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        region: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.workspace_id = _pick(workspace_id, settings.bailian_workspace_id).strip()
        self.api_key = _pick(api_key, settings.dashscope_api_key).strip()
        self.index_id = _pick(index_id, settings.bailian_index_id).strip()
        self.agent_id = _pick(agent_id, settings.bailian_agent_id).strip()
        self.region = _pick(region, settings.bailian_region).strip() or "cn-beijing"
        self.timeout = timeout if timeout is not None else settings.bailian_kb_timeout

    # ---------- 配置校验 ----------
    def validate(self) -> None:
        """调用前置校验，缺什么明确报什么"""
        missing = []
        if not self.workspace_id:
            missing.append("BAILIAN_WORKSPACE_ID（百炼业务空间 ID）")
        if not self.api_key:
            missing.append("DASHSCOPE_API_KEY（百炼 API Key）")
        if not (self.index_id or self.agent_id):
            missing.append(
                "BAILIAN_INDEX_ID（知识库 ID）或 BAILIAN_AGENT_ID（知识检索服务 ID）"
            )
        if missing:
            raise BailianKnowledgeError(
                "百炼知识库未配置完整，缺少：" + "、".join(missing)
            )

    @property
    def use_agent(self) -> bool:
        """是否走跨库联合检索（配了 agent_id 优先）"""
        return bool(self.agent_id)

    @property
    def endpoint(self) -> str:
        return _ENDPOINT_KNOWLEDGE_SEARCH if self.use_agent else _ENDPOINT_INDEX_RETRIEVE

    @property
    def url(self) -> str:
        return _join_url(self.workspace_id, self.region, self.endpoint)

    # ---------- 请求构造 ----------
    def _build_payload(
        self, query: str, top_k: int, kb_search_configs: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """按所选路径构造请求体。

        两条路径的可选字段不同：
        - knowledge/search 只暴露 agent_id / query / images / kb_search_configs，
          top_k 由服务端发布配置决定，多传反而可能触发 InvalidParameter；
        - rag/index/retrieve 需要 index_id / query / top_k。
        """
        if self.use_agent:
            payload: Dict[str, Any] = {"agent_id": self.agent_id, "query": query}
            if kb_search_configs:
                payload["kb_search_configs"] = kb_search_configs
            return payload

        payload = {"index_id": self.index_id, "query": query, "top_k": int(top_k)}
        return payload

    # ---------- 调用 ----------
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        kb_search_configs: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """调用百炼检索接口，返回原始 nodes 列表"""
        self.validate()

        query = (query or "").strip()
        if not query:
            raise BailianKnowledgeError("检索内容不能为空")

        k = int(top_k if top_k is not None else settings.bailian_kb_top_k)
        if k <= 0:
            k = settings.bailian_kb_top_k

        payload = self._build_payload(query, k, kb_search_configs)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "百炼知识库检索 endpoint=%s 目标=%s top_k=%d",
            self.endpoint,
            self.agent_id or self.index_id,
            k,
        )

        try:
            resp = httpx.post(
                self.url, headers=headers, json=payload, timeout=self.timeout
            )
        except httpx.TimeoutException as exc:
            raise BailianKnowledgeError(
                f"百炼检索超时（{self.timeout}s），请检查网络或调大 BAILIAN_KB_TIMEOUT"
            ) from exc
        except httpx.HTTPError as exc:
            raise BailianKnowledgeError(f"百炼检索网络异常：{exc}") from exc

        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise BailianKnowledgeError(
                f"百炼返回非 JSON（HTTP {resp.status_code}）：{resp.text[:200]}"
            ) from exc

        if not isinstance(body, dict):
            raise BailianKnowledgeError(f"百炼返回结构异常：{str(body)[:200]}")

        # 官方明确要求：以 success 字段作为主判定
        if not body.get("success"):
            code = body.get("code") or body.get("status_code") or resp.status_code
            message = body.get("message") or "未知错误"
            request_id = body.get("request_id") or "-"
            if resp.status_code == 401 or str(code) == "InvalidApiKey":
                raise BailianKnowledgeError(
                    f"百炼鉴权失败(401)：DASHSCOPE_API_KEY 无效或缺失，request_id={request_id}"
                )
            raise BailianKnowledgeError(
                f"百炼检索失败 code={code} message={message} request_id={request_id}"
            )

        data = body.get("data") or {}
        nodes = data.get("nodes") or []
        if not isinstance(nodes, list):
            nodes = []

        # agent 模式无法在请求里控制条数（由服务端发布配置决定），这里按需截断
        if self.use_agent and len(nodes) > k:
            nodes = nodes[:k]

        logger.info(
            "百炼知识库检索完成 total=%s 返回=%d 耗时=%sms",
            data.get("total"),
            len(nodes),
            data.get("cost_time"),
        )
        return nodes

    def retrieve_documents(
        self,
        query: str,
        top_k: Optional[int] = None,
        kb_search_configs: Optional[List[Dict]] = None,
    ) -> List[Document]:
        """检索并转换为 LangChain Document，可直接并入现有 RAG 链路"""
        nodes = self.retrieve(query, top_k=top_k, kb_search_configs=kb_search_configs)
        return [_node_to_document(node) for node in nodes]


def _node_to_document(node: Dict[str, Any]) -> Document:
    """把百炼返回的单个 node 转成 LangChain Document。

    ``text`` 是按「字段名: 值」拼好的完整切片文本（含文档名、标题、正文），
    与百炼 Playground 展示一致，优先使用；为空时回退到 ``metadata.content``。
    """
    meta = node.get("metadata") or {}
    content = (node.get("text") or "").strip() or str(meta.get("content") or "").strip()
    source = meta.get("doc_name") or meta.get("title") or "百炼知识库"

    return Document(
        page_content=content,
        metadata={
            "source": source,
            "backend": "bailian",
            "score": node.get("score"),
            "doc_id": meta.get("doc_id"),
            "doc_name": meta.get("doc_name"),
            "title": meta.get("title"),
            "hier_title": meta.get("hier_title"),
            "pipeline_id": meta.get("pipeline_id"),
            "page_number": meta.get("page_number"),
        },
    )


class BailianKnowledgeRetriever(BaseRetriever):
    """把百炼知识库包装成 LangChain Retriever，可接入 LCEL 链"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Any
    k: int = 4

    def _get_relevant_documents(
        self, query: str, *, run_manager: Any = None
    ) -> List[Document]:
        return self.client.retrieve_documents(query, top_k=self.k)


# ---------- 便捷入口 ----------
def get_bailian_client() -> BailianKnowledgeClient:
    """按全局配置构造客户端"""
    return BailianKnowledgeClient()


def bailian_similarity_search(query: str, k: int = 4) -> List[Document]:
    """与本地 vector_store.similarity_search 同签名的百炼实现"""
    return get_bailian_client().retrieve_documents(query, top_k=k)


def as_bailian_retriever(k: int = 4) -> BailianKnowledgeRetriever:
    """以 Retriever 形式返回百炼知识库"""
    return BailianKnowledgeRetriever(client=get_bailian_client(), k=k)


def check_bailian_kb(query: str = "你好") -> Dict[str, Any]:
    """连通性自检：返回可直接展示给用户的诊断信息"""
    client = get_bailian_client()
    info: Dict[str, Any] = {
        "configured": settings.bailian_kb_ready,
        "mode": "agent" if client.use_agent else "index",
        "workspace_id": client.workspace_id or "(未配置)",
        "target": client.agent_id or client.index_id or "(未配置)",
        "region": client.region,
        "url": client.url if client.workspace_id else "(未配置)",
    }
    try:
        docs = client.retrieve_documents(query, top_k=1)
        info.update(
            {
                "ok": True,
                "hits": len(docs),
                "sample": docs[0].page_content[:80] if docs else "",
            }
        )
    except Exception as exc:  # noqa: BLE001
        info.update({"ok": False, "error": str(exc)})
    return info
