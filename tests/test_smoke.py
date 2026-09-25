"""恋爱大师 - 冒烟测试：验证项目骨架与依赖可正常导入"""
import sys


def test_import_config():
    from app.config import settings

    assert settings.app_name == "恋爱大师"
    assert settings.port == 8000


def test_import_rag():
    from app.rag import load_documents, split_documents

    docs = load_documents()
    assert len(docs) == 3, f"知识库文档数量应为 3，实际 {len(docs)}"
    chunks = split_documents(docs, chunk_size=300, chunk_overlap=50)
    assert len(chunks) > 0


def test_import_tools():
    from app.tools import ALL_TOOLS

    tool_names = {t.name for t in ALL_TOOLS}
    assert "search_love_knowledge" in tool_names
    assert "terminate" in tool_names
    assert len(ALL_TOOLS) == 8


def test_import_agent():
    from app.agent import FileChatMemory, get_chat_memory

    memory = get_chat_memory("test_session")
    memory.clear()
    memory.add_user_message("你好")
    memory.add_ai_message("你好呀")
    assert len(memory.get_messages()) == 2
    assert "历史" not in memory.get_history_text()
    memory.clear()
    assert isinstance(memory, FileChatMemory)
    # 清理测试残留的会话文件
    memory.file_path.unlink(missing_ok=True)


def test_import_app_entry():
    from app.main import app

    routes = {r.path for r in app.routes}
    assert "/api/health" in routes
    assert "/api/chat" in routes
    assert "/api/chat/rag" in routes
    assert "/api/chat/agent" in routes


def test_fastapi_testclient():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "恋爱大师"


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f"[PASS] {name}")
    print("\n全部冒烟测试通过")
    sys.exit(0)
