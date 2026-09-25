"""恋爱大师 - 核心对话服务

对应 Java 版 app/LoveApp.java，聚合普通对话、RAG 问答、Agent 推理、恋爱报告。
"""
from typing import List, Optional

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent import get_chat_memory, get_react_agent
from app.config import settings
from app.rag.prompts import (
    LOVE_SYSTEM_PROMPT,
    RAG_SYSTEM_PROMPT,
    REPORT_EMPTY_HISTORY_HINT,
    REPORT_SYSTEM_PROMPT,
)
from app.schemas import LoveReport
from app.utils import get_logger

logger = get_logger(__name__)

# 恋爱场景预设角色
LOVE_PRESETS = {
    "single": "单身篇",
    "dating": "恋爱篇",
    "married": "已婚篇",
}


class LoveApp:
    """恋爱大师核心应用"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.memory = get_chat_memory(session_id)

    # ---------- 基础对话 ----------
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """普通多轮对话（带会话记忆）"""
        from app.models import get_chat_model

        llm = get_chat_model(temperature=0.7)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt or LOVE_SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
                ("human", "{input}"),
            ]
        )
        chain = prompt | llm | StrOutputParser()

        history = self.memory.get_messages()
        answer = chain.invoke({"history": history, "input": message})
        self.memory.add_user_message(message)
        self.memory.add_ai_message(answer)
        logger.info("对话完成 session=%s", self.session_id)
        return answer

    # ---------- SSE 流式对话（对应 Java doChatWithLoveAppSse） ----------
    def chat_stream(self, message: str, system_prompt: Optional[str] = None):
        """流式多轮对话：逐块产出文本，供 SSE 接口实时下发。

        与 chat 共享同一份会话记忆与系统提示，唯一的区别是边生成边产出，
        全程结束后才把完整回答写入记忆，保证记忆与非流式路径一致。
        """
        from app.models import get_chat_model

        llm = get_chat_model(temperature=0.7, streaming=True)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt or LOVE_SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
                ("human", "{input}"),
            ]
        )
        chain = prompt | llm | StrOutputParser()

        history = self.memory.get_messages()
        parts: List[str] = []
        for chunk in chain.stream({"history": history, "input": message}):
            parts.append(chunk)
            yield chunk

        answer = "".join(parts)
        self.memory.add_user_message(message)
        self.memory.add_ai_message(answer)
        logger.info("流式对话完成 session=%s 长度=%d", self.session_id, len(answer))

    # ---------- RAG 问答 ----------
    def chat_with_rag(self, message: str, k: int = 4) -> str:
        """基于恋爱知识库的 RAG 增强问答"""
        from app.models import get_chat_model
        from app.rag import similarity_search

        docs = similarity_search(message, k=k)
        context = (
            "\n\n---\n\n".join(
                f"[{d.metadata.get('source', '知识库')}]\n{d.page_content}" for d in docs
            )
            or "（知识库暂无相关内容）"
        )

        llm = get_chat_model(temperature=0.5)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
                ("human", "{input}"),
            ]
        )
        chain = prompt | llm | StrOutputParser()

        answer = chain.invoke(
            {
                "context": context,
                "history": self.memory.get_messages(),
                "input": message,
            }
        )

        self.memory.add_user_message(message)
        self.memory.add_ai_message(answer)
        logger.info("RAG 问答完成，召回 %d 条资料", len(docs))
        return answer

    # ---------- Agent 推理 ----------
    def run_agent(self, message: str) -> str:
        """ReAct 智能体推理（可自主调用工具）"""
        agent = get_react_agent()
        answer = agent.run(message, history=self.memory.get_history_text())
        self.memory.add_user_message(message)
        self.memory.add_ai_message(answer)
        logger.info("Agent 推理完成 session=%s", self.session_id)
        return answer

    # ---------- Agent 流式推理（对应 Java doChatWithManus） ----------
    def agent_stream(self, message: str):
        """智能体流式推理：边推理边产出文本，供 SSE 实时下发。

        用 LangGraph 的 stream_mode="messages" 流式输出各节点 LLM token；
        工具调用决策节点的 content 通常为空，过滤后用户看到的主体是最终回答。
        空历史时不拼接占位符，避免把「（暂无历史对话）」混进提示词。
        """
        agent = get_react_agent()
        history_text = self.memory.get_history_text()
        content = (
            message
            if history_text == "（暂无历史对话）"
            else f"【历史对话】\n{history_text}\n\n【当前问题】\n{message}"
        )

        parts: List[str] = []
        for token, _meta in agent.graph.stream(
            {"messages": [HumanMessage(content=content)]},
            config={"recursion_limit": agent.max_iterations * 2},
            stream_mode="messages",
        ):
            text = getattr(token, "content", "")
            if text:
                parts.append(text)
                yield text

        answer = "".join(parts) or "抱歉，本轮未能生成有效回复，请换个说法再试一次。"
        self.memory.add_user_message(message)
        self.memory.add_ai_message(answer)
        logger.info("流式 Agent 推理完成 session=%s 长度=%d", self.session_id, len(answer))

    # ---------- 恋爱报告（结构化输出） ----------
    def generate_report(self, use_rag: bool = True) -> LoveReport:
        """基于当前会话历史生成结构化恋爱报告。

        对应 Java 版「结构化输出 - 恋爱报告功能」。
        先用 StrOutputParser 拿不到类型安全，这里改用 with_structured_output
        把 Pydantic 模型转成 JSON Schema 下发（前置处理），
        再把模型返回的 JSON 反序列化为 LoveReport 实例（后处理）。

        Args:
            use_rag: 是否先检索知识库，把资料作为参考注入提示词
        """
        from app.models import get_chat_model

        history = self.memory.get_messages()
        if not history:
            logger.warning("会话 %s 无历史，将生成初步报告", self.session_id)

        # 组装提示词：system + 知识库参考 + 对话记录 + 生成指令
        system_parts = [REPORT_SYSTEM_PROMPT]

        if use_rag:
            context = self._retrieve_report_context(history)
            if context:
                system_parts.append(f"可用于参考的恋爱知识库内容：\n\n{context}")

        # 用 ChatPromptTemplate 统一解析为消息对象，避免元组与 BaseMessage 混用
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "\n\n".join(system_parts)),
                MessagesPlaceholder("history", optional=True),
                ("human", "{instruction}"),
            ]
        )
        messages = prompt.format_messages(
            history=history or [HumanMessage(content=REPORT_EMPTY_HISTORY_HINT)],
            instruction="请基于以上对话记录，生成结构化恋爱报告。",
        )

        llm = get_chat_model(temperature=0.3)
        report = self._invoke_structured(llm, messages, use_rag=use_rag)

        logger.info(
            "恋爱报告生成完成 session=%s 消息数=%d 建议数=%d",
            self.session_id,
            len(history),
            len(report.suggestions),
        )
        return report

    def _retrieve_report_context(self, history: List) -> str:
        """提取最近几轮用户诉求，检索知识库作为报告参考。失败时静默降级。"""
        from app.rag import similarity_search

        user_texts = [
            str(m.content) for m in history if type(m).__name__ == "HumanMessage"
        ][-3:]
        if not user_texts:
            return ""
        try:
            docs = similarity_search(" ".join(user_texts), k=4)
        except Exception as exc:  # noqa: BLE001
            logger.warning("报告知识库检索失败，降级为无参考生成: %s", exc)
            return ""
        if not docs:
            return ""
        return "\n\n---\n\n".join(
            f"[{d.metadata.get('source', '知识库')}]\n{d.page_content}" for d in docs
        )

    @staticmethod
    def _invoke_structured(llm, messages, use_rag: bool) -> LoveReport:
        """调用结构化输出，method 逐级回退以适配不同模型的协议支持度。

        DashScope 经 OpenAI 兼容协议接入时，不同模型的 function calling /
        json_schema 支持度不一致，因此按 json_schema -> function_calling 顺序尝试。
        """
        last_error: Exception | None = None
        for method in ("json_schema", "function_calling"):
            try:
                structured_llm = llm.with_structured_output(LoveReport, method=method)
                report = structured_llm.invoke(messages)
                if report is None:
                    raise ValueError("模型返回了空报告")
                if use_rag and isinstance(report, LoveReport):
                    report.used_knowledge_base = True
                return report
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("结构化输出 method=%s 失败: %s", method, exc)

        raise RuntimeError(
            f"结构化输出失败，已尝试 json_schema / function_calling：{last_error}"
        ) from last_error

    # ---------- 知识库构建 ----------
    @staticmethod
    def build_knowledge_base(force_rebuild: bool = False) -> int:
        """构建恋爱知识库向量索引"""
        from app.rag import build_knowledge_base

        return build_knowledge_base(force_rebuild=force_rebuild)

    # ---------- 会话管理 ----------
    def get_history(self) -> List[dict]:
        """获取当前会话历史"""
        role_map = {"HumanMessage": "user", "AIMessage": "assistant"}
        return [
            {"role": role_map.get(type(m).__name__, "user"), "content": m.content}
            for m in self.memory.get_messages()
        ]

    def clear_history(self) -> None:
        """清空当前会话历史"""
        self.memory.clear()
        logger.info("会话已清空 session=%s", self.session_id)
