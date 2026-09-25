"""恋爱大师 - 恋爱报告数据模型

对应 Java 版「结构化输出 - 恋爱报告功能」中的 LoveReport 类。
用途：把大模型的自由文本输出约束为强类型对象，供下游程序可靠消费。

设计说明：
- 字段全部带 description，LangChain 会据此生成 JSON Schema 作为格式指令下发给模型。
- 列表字段用 min_length 约束，避免模型返回空数组导致报告无实质内容。
- 情绪评级等枚举型字段用 Literal，让模型只能在给定取值中选择。
"""
from typing import List, Literal

from pydantic import BaseModel, Field

# ---------- 子结构 ----------


class LoveSuggestion(BaseModel):
    """单条行动建议"""

    title: str = Field(description="建议标题，简短有力，15 字以内")
    detail: str = Field(description="具体做法，需可执行，50 字以内")
    priority: Literal["高", "中", "低"] = Field(description="优先级")


class RiskItem(BaseModel):
    """风险项"""

    risk: str = Field(description="风险描述，30 字以内")
    severity: Literal["高", "中", "低"] = Field(description="严重程度")
    advice: str = Field(description="应对方向，40 字以内")


# ---------- 报告主结构 ----------


class LoveReport(BaseModel):
    """恋爱报告（结构化输出目标模型）"""

    title: str = Field(description="报告标题，如「单身三年情感状态分析报告」")
    summary: str = Field(description="整体摘要，150 字以内，概括核心结论")

    stage: Literal["单身", "暧昧", "恋爱", "已婚", "其他"] = Field(
        description="用户当前所处的情感阶段"
    )
    mood_score: int = Field(
        ge=1, le=10, description="情绪状态评分，1 分最低、10 分最高"
    )

    strengths: List[str] = Field(
        min_length=1, description="用户的优势或关系中的积极因素，每条 20 字以内"
    )
    problems: List[str] = Field(
        min_length=1, description="当前主要问题，每条 20 字以内"
    )
    risks: List[RiskItem] = Field(
        default_factory=list, description="潜在风险及应对方向，可为空数组"
    )
    suggestions: List[LoveSuggestion] = Field(
        min_length=1, description="行动建议，按优先级排序，3 至 5 条"
    )

    encouragement: str = Field(description="给用户的鼓励语，温暖真诚，60 字以内")

    # 报告生成时是否用到了知识库召回资料
    used_knowledge_base: bool = Field(
        default=False, description="是否参考了恋爱知识库内容"
    )


# ---------- 接口请求 / 响应 ----------


class ReportRequest(BaseModel):
    """恋爱报告生成请求"""

    session_id: str = Field(default="default", max_length=64, description="会话 ID")
    export_pdf: bool = Field(default=False, description="是否同时导出 PDF 文件")
    use_rag: bool = Field(default=True, description="是否参考知识库内容生成")


class ReportResponse(BaseModel):
    """恋爱报告生成响应"""

    session_id: str
    report: LoveReport
    pdf_path: str | None = Field(default=None, description="PDF 导出路径（未导出为 null）")
    message_count: int = Field(description="参与生成报告的会话消息条数")
