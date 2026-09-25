"""恋爱大师 - 健康检查与系统信息接口"""
from fastapi import APIRouter, HTTPException

from app import __version__
from app.config import settings
from app.rag import check_bailian_kb, describe_rag_backend
from app.rag.document_loader import KNOWLEDGE_TOPICS, load_documents
from app.schemas import BuildKbRequest, BuildKbResponse, HealthResponse

router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health() -> HealthResponse:
    """服务存活与配置状态检查"""
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=__version__,
        llm_ready=settings.llm_ready,
        env=settings.app_env,
        detail=None if settings.llm_ready else "DASHSCOPE_API_KEY 未配置，大模型能力不可用",
    )


@router.get("/knowledge/backend", summary="RAG 数据源诊断")
def knowledge_backend(check: bool = False) -> dict:
    """查看当前 RAG 用的是本地向量库还是百炼知识库。

    Args:
        check: 为 true 时向百炼发起一次真实检索做连通性自检

    注意本接口用同步 def 定义，FastAPI 会调度到线程池执行，
    避免百炼的阻塞式 HTTP 调用卡住事件循环。
    """
    info = describe_rag_backend()
    if check:
        info["bailian_check"] = check_bailian_kb()
    return info


@router.get("/knowledge/topics", summary="知识库主题列表")
async def knowledge_topics() -> dict:
    """返回恋爱知识库主题与文档清单（仅本地向量库模式有内容）"""
    documents = load_documents()
    return {
        "topics": KNOWLEDGE_TOPICS,
        "document_count": len(documents),
        "documents": [doc.metadata.get("source") for doc in documents],
        "active_backend": settings.rag_mode,
    }


@router.post("/knowledge/build", response_model=BuildKbResponse, summary="构建知识库向量索引")
async def build_knowledge(request: BuildKbRequest) -> BuildKbResponse:
    """加载恋爱知识文档并写入向量库"""
    try:
        from app.app import LoveApp

        count = LoveApp.build_knowledge_base(force_rebuild=request.force_rebuild)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"知识库构建失败：{exc}") from exc

    return BuildKbResponse(
        success=count > 0,
        chunk_count=count,
        message=f"知识库构建完成，共入库 {count} 个文本块" if count else "知识库为空",
    )
