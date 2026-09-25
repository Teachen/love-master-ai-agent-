"""恋爱大师 - ReAct 智能体

对应 Java 版 BaseAgent / ReActAgent / ToolCallAgent。
基于 LangGraph 构建 ReAct 循环：思考 -> 调用工具 -> 观察 -> 再思考。
"""
from typing import Annotated, List, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.models import get_chat_model
from app.tools import ALL_TOOLS
from app.utils import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是「恋爱大师」，一位专业、温暖的情感顾问智能体。

你可以调用以下工具来更好地帮助用户：
- search_love_knowledge：检索恋爱知识库，遇到具体情感困惑时优先使用
- write_file / read_file：读写本地文件
- download_resource：下载网络资源
- scrape_webpage：抓取网页正文
- web_search：联网搜索实时信息
- generate_pdf：生成 PDF 报告
- terminate：任务完成后结束流程

行为准则：
1. 涉及恋爱、婚恋、情感困惑的问题，先检索知识库再作答
2. 建议要具体可执行，先共情再分析最后给方案
3. 危机情况（自伤自残等）优先建议求助专业机构
4. 始终用中文回复，语气亲切自然，回答控制在 500 字以内
"""


class AgentState(TypedDict):
    """ReAct 状态"""

    messages: Annotated[List[BaseMessage], add_messages]


class ReActAgent:
    """ReAct 模式智能体"""

    def __init__(self, tools: Sequence | None = None, max_iterations: int = 8):
        self.tools = list(tools) if tools is not None else list(ALL_TOOLS)
        self.max_iterations = max_iterations
        self._graph = None

    # ---------- 图构建 ----------
    def _build_graph(self):
        """构建 LangGraph 状态图"""
        llm = get_chat_model(temperature=0.5)
        llm_with_tools = llm.bind_tools(self.tools) if self.tools else llm

        def call_model(state: AgentState) -> dict:
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}

        def should_continue(state: AgentState) -> str:
            last = state["messages"][-1]
            if getattr(last, "tool_calls", None):
                tool_names = {t.name for t in self.tools}
                valid = [tc for tc in last.tool_calls if tc["name"] in tool_names]
                if valid and "terminate" not in {tc["name"] for tc in valid}:
                    return "tools"
            return END

        graph = StateGraph(AgentState)
        graph.add_node("agent", call_model)
        if self.tools:
            graph.add_node("tools", ToolNode(self.tools))
            graph.add_conditional_edges(
                "agent", should_continue, {"tools": "tools", END: END}
            )
            graph.add_edge("tools", "agent")
        else:
            graph.add_edge("agent", END)

        graph.set_entry_point("agent")
        return graph.compile()

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    # ---------- 对外接口 ----------
    def run(self, question: str, history: str = "") -> str:
        """执行一次完整推理，返回最终回答"""
        logger.info("ReAct 推理开始: %s", question[:50])
        content = question if not history else f"【历史对话】\n{history}\n\n【当前问题】\n{question}"
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=content)]},
            config={"recursion_limit": self.max_iterations * 2},
        )
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if msg.__class__.__name__ == "AIMessage" and msg.content:
                if not getattr(msg, "tool_calls", None):
                    return str(msg.content)
        return "抱歉，本轮未能生成有效回复，请换个说法再试一次。"

    async def arun(self, question: str, history: str = "") -> str:
        """异步执行一次完整推理"""
        content = question if not history else f"【历史对话】\n{history}\n\n【当前问题】\n{question}"
        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=content)]},
            config={"recursion_limit": self.max_iterations * 2},
        )
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if msg.__class__.__name__ == "AIMessage" and msg.content:
                if not getattr(msg, "tool_calls", None):
                    return str(msg.content)
        return "抱歉，本轮未能生成有效回复，请换个说法再试一次。"


_agent_instance: ReActAgent | None = None


def get_react_agent() -> ReActAgent:
    """获取 ReAct 智能体单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReActAgent()
    return _agent_instance
