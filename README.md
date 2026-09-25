# 恋爱大师 · AI 情感顾问

基于 **Python 3.12 + FastAPI + LangChain / LangGraph** 构建的 AI 情感顾问服务，是 Java 版
`yu-ai-agent` 的 Python 技术栈重写版本。

核心能力覆盖：**多轮对话、RAG 知识库问答、ReAct 智能体、Tool Calling、MCP 接入、PGVector 向量检索**。

---

## 一、技术选型

| 分类 | 技术 | 用途 |
|---|---|---|
| 语言 / 框架 | Python 3.12、FastAPI | Web 服务、自动 OpenAPI/Swagger 文档 |
| 编排 | LangChain、LangGraph | 链路编排、ReAct Agent 状态图 |
| RAG | LangChain + PGVector | 恋爱知识库检索增强 |
| 向量库 | PGVector（PostgreSQL） | 向量存储与相似度检索 |
| 大模型 | 阿里云百炼 DashScope（Qwen） | 对话与向量化 |
| 本地模型 | Ollama | 离线模型部署（可选） |
| 协议 | MCP（模型上下文协议） | 外部工具服务接入 |
| 抓取 | BeautifulSoup4、Playwright | 网页正文提取（可选） |
| 生成 | ReportLab | PDF 报告生成（可选） |
| 序列化 | orjson、msgpack | 高性能序列化（可选） |
| 前端 | uni-app（Vue3 + Vite）+ Axios | 一套代码编译 H5 / 微信小程序 / App |

---

## 二、目录结构

```
恋爱大师/
├── app/
│   ├── main.py                  # FastAPI 应用入口
│   ├── config/settings.py       # 配置管理（pydantic-settings）
│   ├── api/                     # 接口层
│   │   ├── chat.py              # 对话 / RAG / Agent 接口
│   │   ├── ai.py                # SSE 流式接口（对齐 Java AiController）
│   │   └── system.py            # 健康检查 / 知识库构建
│   ├── schemas/chat.py          # 请求响应模型
│   ├── schemas/report.py        # 恋爱报告结构化模型（LoveReport）
│   ├── models/llm_factory.py    # 大模型工厂（DashScope / Ollama）
│   ├── app/love_app.py          # 核心应用服务（对应 Java LoveApp）
│   ├── core/
│   │   ├── middleware.py        # HTTP 拦截器（鉴权 / 访问日志）
│   │   ├── llm_logging.py       # LLM 调用日志（对应 MyLoggerAdvisor）
│   │   └── report_pdf.py        # 恋爱报告 PDF 渲染
│   ├── agent/
│   │   ├── react_agent.py       # LangGraph ReAct 智能体
│   │   └── memory.py            # 文件化会话记忆
│   ├── rag/
│   │   ├── document_loader.py   # 文档加载与切分
│   │   ├── vector_store.py      # PGVector 向量库管理（本地数据源）
│   │   ├── bailian_kb.py        # 阿里云百炼知识库检索（百炼数据源）
│   │   ├── retriever.py         # 统一检索入口（按配置路由数据源）
│   │   ├── prompts.py           # 提示词模板
│   │   └── documents/           # 恋爱知识库（单身/恋爱/已婚）
│   ├── tools/love_tools.py      # 8 个 Tool Calling 工具
│   ├── mcp/client.py            # MCP 客户端
│   └── utils/logger.py          # 日志配置
├── tests/test_smoke.py          # 冒烟测试
├── tests/test_chat_memory.py    # 多轮对话记忆测试
├── tests/test_love_report.py    # 恋爱报告结构化输出测试
├── tests/test_chat_cli.py       # 控制台工具端到端测试
├── tests/test_bailian_kb.py     # 百炼知识库对接测试
├── tests/test_sse_stream.py     # SSE 流式接口测试
├── tests/conftest.py            # 测试夹具（隔离记忆目录）
├── chat_cli.py                  # 控制台交互对话工具（无需前端）
├── run_tests.py                 # 一键测试入口（pytest / 内置 runner）
├── main.py                      # 启动脚本
├── requirements.txt             # 核心依赖
├── requirements-optional.txt    # 扩展依赖
├── docker-compose.yml           # PGVector + API 编排
├── uniapp/                      # 跨端前端（H5 / 微信小程序 / App）
│   ├── src/
│   │   ├── pages/               # 主页 + 恋爱大师 + 超级智能体
│   │   ├── components/ChatRoom.vue   # 通用聊天室组件（复用）
│   │   ├── utils/sse.js         # 跨端 SSE 封装（核心）
│   │   ├── api/http.js          # Axios 实例（小程序走 adapter）
│   │   └── config/index.js      # 后端地址（读 .env）
│   ├── .env.development         # 开发环境变量
│   ├── .env.production          # 生产环境变量
│   └── README.md                # 前端专项文档
└── .env.example                 # 环境变量模板
```

---

## 三、快速开始

### 1. 配置环境变量

```bash
copy .env.example .env
```

编辑 `.env`，**至少填写** `DASHSCOPE_API_KEY`（否则大模型能力不可用）：

```ini
DASHSCOPE_API_KEY=sk-你的真实密钥
DASHSCOPE_CHAT_MODEL=qwen-plus
```

API Key 获取地址：<https://bailian.console.aliyun.com/>

### 2. 安装依赖

```bash
# 创建虚拟环境（已创建可跳过）
python -m venv .venv

# 激活（Windows PowerShell）
.\.venv\Scripts\Activate.ps1
# 激活（Windows CMD）
.\.venv\Scripts\activate.bat

# 安装核心依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 可选：扩展依赖（MCP / Playwright / ReportLab 等）
pip install -r requirements-optional.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 启动服务

```bash
python main.py
```

服务启动后访问：

| 地址 | 说明 |
|---|---|
| <http://localhost:8000> | 服务概览 |
| <http://localhost:8000/docs> | Swagger UI 交互文档 |
| <http://localhost:8000/redoc> | ReDoc 文档 |
| <http://localhost:8000/api/health> | 健康检查 |

> 未配置 API Key 时服务仍可正常启动，健康检查会提示 `llm_ready=false`，接口可访问但大模型调用会返回明确错误。

### 4. 控制台直接对话（无需前端）

不想开浏览器、也不想调 Swagger，可以直接在终端里聊：

```bash
python chat_cli.py                        # 默认 chat 模式，会话 ID = cli_default
python chat_cli.py -s user_001            # 指定会话 ID（再次运行可续上历史）
python chat_cli.py -m rag                 # 知识库问答模式
python chat_cli.py -s user_001 -m agent   # 智能体推理模式
python chat_cli.py --report -s user_001   # 非交互：直接给已有会话生成报告
python chat_cli.py --report -s user_001 --pdf   # 生成报告并导出 PDF
```

会话内以 `/` 开头的命令：

| 命令 | 作用 |
|---|---|
| `/chat` `/rag` `/agent` | 运行时切换对话模式 |
| `/report` | 生成结构化恋爱报告（会询问是否参考知识库、是否导出 PDF） |
| `/history` | 打印当前会话全部历史消息 |
| `/clear` | 清空当前会话历史 |
| `/mode` | 查看当前模式、会话 ID、消息条数 |
| `/help` | 显示命令帮助 |
| `/exit` | 退出（`Ctrl+C` 亦可） |

直接输入文字即为对话。脚本复用 `LoveApp` 与 `FileChatMemory`，**与 HTTP 接口共用同一份会话数据**——
在控制台聊的内容，用同一个 `session_id` 调 `/api/chat/report` 也能读到。

> 与 `main.py` 启动的服务是两条独立入口：`chat_cli.py` 不启服务、不占端口，适合本地调试与快速验证。

### 5. 启动前端（可选，跨端 UI）

需要图形化聊天界面时，起 `uniapp/`（同一套代码可编译 H5 / 微信小程序 / App）：

```bash
cd uniapp
npm install --ignore-scripts
npm run dev:h5        # 浏览器访问 http://localhost:5173
```

主页可切换「AI 恋爱大师」与「AI 超级智能体」两个应用，均为 SSE 逐字流式对话。
详见 [五、7. 前端调用（uni-app 跨端）](#7-前端调用uni-app-跨端) 与 [`uniapp/README.md`](uniapp/README.md)。

---

## 三之二、依赖版本约束（重要，勿随意改动）

本项目的依赖组合经过实测锁定，**改动版本前请先读本节**，否则极易搞坏可运行状态。

### 核心依赖是成套锁定的

`fastapi 0.115.6` 要求 `starlette<0.42`，`langchain 0.3.14` 要求 `pydantic 2.10.x`。
这两条约束是整条依赖链的支点，任何试图升级 `starlette` 或 `pydantic` 的操作都会连带崩掉整个栈。

### 已知的三个坑

| 包 | 直接装会怎样 | 正确处理 |
|---|---|---|
| `mcp` / `langchain-mcp-adapters` | 拉入 `sse-starlette>=3` → `starlette 1.6` → 卸载并替换现有 starlette，`fastapi` 直接不可用；同时把 `pydantic` 抬到 2.13，`langchain` 也崩 | **当前不启用**。需 MCP 则整体迁移到 langchain 1.x 栈 |
| `llama-index-core` | 放开版本会解析到 0.14+，改为 `llama-index-workflows` 生态，要求 `pydantic>=2.11.5`，同样崩 | 锁定 `==0.12.8`（已锁） |
| `llama-index-vector-stores-postgres` | 依赖 `asyncpg`，无 Python 3.13 预编译轮子，需 VS C++ 编译器，安装必失败 | **不装**。PGVector 访问由 `psycopg` + `langchain-postgres` 承担 |

### 校验命令

装完任何东西后执行：

```bash
python -m pip check
```

期望输出 `No broken requirements found.`。若出现 `X requires Y, which is not installed` 或版本不兼容提示，说明栈已被破坏。

### 修复方法

依赖被污染后，不要逐个救包，直接重装核心依赖即可回归正确版本：

```bash
pip install -r requirements.txt
```

`requirements.txt` 中所有版本均已钉死，重装会自动把 `starlette`、`pydantic`、`langsmith` 等拉回正确版本。若提示存在无效的 `~xxxx` 目录（中断卸载的残留），删除 `.venv\Lib\site-packages\~*` 后重试。

---

## 四、向量数据库（可选）

不启动 PGVector 时，系统会自动降级为**内存向量库**（重启丢数据），可先跑通流程。

需要持久化检索时启动 PGVector：

```bash
docker-compose up -d pgvector
```

随后调用知识库构建接口，把恋爱知识文档写入向量库。

---

## 五、接口说明

### 1. 统一对话入口

```http
POST /api/chat
Content-Type: application/json

{
  "message": "单身三年了，越来越焦虑怎么办？",
  "session_id": "user_001",
  "mode": "rag"
}
```

`mode` 可选值：

- `chat` — 普通多轮对话
- `rag` — 基于恋爱知识库的检索增强问答
- `agent` — ReAct 智能体推理（可自主调用工具）

### 2. 独立接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/rag` | 知识库问答 |
| POST | `/api/chat/agent` | 智能体推理 |
| POST | `/api/chat/report` | 生成恋爱报告（结构化输出） |
| GET | `/api/chat/history?session_id=xxx` | 查询会话历史 |
| DELETE | `/api/chat/history?session_id=xxx` | 清空会话历史 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/knowledge/topics` | 知识库主题列表 |
| GET | `/api/knowledge/backend` | **RAG 数据源诊断**（`?check=true` 额外做连通性自检） |
| POST | `/api/knowledge/build` | 构建知识库向量索引（仅本地向量库模式） |
| GET | `/api/ai/love_app/chat/sse` | **SSE 流式**恋爱大师对话（`?message=&chatId=`），对齐 Java `doChatWithLoveAppSse` |
| GET | `/api/ai/manus/chat` | **SSE 流式**超级智能体推理（`?message=&chatId=`），对齐 Java `doChatWithManus` |

### 3. 拦截器：前置鉴权与访问日志

对应 Java 版的自定义拦截器（preHandle 鉴权 + 日志打印），实现在 `app/core/middleware.py`：

| 拦截器 | 对应 Java 概念 | 作用 |
|---|---|---|
| `ApiKeyMiddleware` | preHandle 前置鉴权 | 校验 `X-API-Key` 请求头 |
| `AccessLogMiddleware` | 拦截器日志 | 每请求一行：方法、路径、状态码、耗时（毫秒）|
| `LLMLoggingHandler` | `MyLoggerAdvisor` | 成对打印每次 LLM 调用的请求消息与响应文本 |

**开启鉴权**（默认关闭，本地开发无感）：

```ini
# .env
API_KEY_ENABLED=true
API_KEYS=my-secret-key-1,my-secret-key-2
```

开启后，除健康检查与文档外，所有 `/api/*` 接口需要携带请求头：

```bash
curl http://localhost:8000/api/chat/history?session_id=u1 \
  -H "X-API-Key: my-secret-key-1"
```

规则细节：

- 文档（`/docs`、`/redoc`、`/openapi.json`）、健康检查（`/api/health`）、OPTIONS 预检始终放行
- 未配置任何 `API_KEYS` 时开启鉴权会**全部拒绝**（防止忘配 Key 裸奔）
- Key 比较使用恒定时间算法（防时序攻击）

**访问日志**始终开启，输出到 stdout：

```
2026-09-22 15:30:00 | INFO | app.access | 请求完成 POST /api/chat -> 200 (3512 ms)
```

**LLM 调用日志**默认开启（`LLM_LOG_ENABLED=true`），由模型工厂自动注入，无需接线：

```
2026-09-22 15:30:01 | INFO | app.llm_advisor | [LLM请求 run=a1b2c3d4] system: 你是「恋爱大师」...
2026-09-22 15:30:01 | INFO | app.llm_advisor | [LLM请求 run=a1b2c3d4] human: 单身三年了怎么办
2026-09-22 15:30:04 | INFO | app.llm_advisor | [LLM响应 run=a1b2c3d4] 先共情，再分析...
```

每条消息按 `LLM_LOG_MAX_CHARS`（默认 200）截断，避免长 Prompt 刷屏。

### 4. 恋爱报告：结构化输出

对应 Java 版「结构化输出 - 恋爱报告功能」。把大模型的自由文本约束为 `LoveReport`
强类型对象，供下游程序可靠消费，并可导出中文 PDF。

**请求**

```http
POST /api/chat/report
Content-Type: application/json

{
  "session_id": "user_001",
  "use_rag": true,
  "export_pdf": true
}
```

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `session_id` | str | `default` | 会话 ID，取其对话历史作报告依据 |
| `use_rag` | bool | `true` | 是否检索知识库作为参考注入提示词 |
| `export_pdf` | bool | `false` | 是否同时导出 PDF 到 `PDF_SAVE_DIR` |

**响应（节选）**

```json
{
  "session_id": "user_001",
  "report": {
    "title": "单身三年情感状态分析报告",
    "summary": "用户长期单身并伴随焦虑，自我觉察能力较强。",
    "stage": "单身",
    "mood_score": 4,
    "strengths": ["自我觉察清晰", "有改变意愿"],
    "problems": ["社交圈狭窄", "过度焦虑"],
    "risks": [
      { "risk": "焦虑引发自我否定", "severity": "中", "advice": "规律作息与运动" }
    ],
    "suggestions": [
      { "title": "扩大低压社交", "detail": "每周参加一次兴趣活动", "priority": "高" }
    ],
    "encouragement": "单身不等于不完整，你已迈出重要一步。",
    "used_knowledge_base": true
  },
  "pdf_path": "tmp\\pdf\\love_report_20260922_165039.pdf",
  "message_count": 2
}
```

**实现要点**

- 模型定义：`app/schemas/report.py` 的 `LoveReport`，字段带 `description` 供 LangChain 生成 JSON Schema；
  `mood_score` 限定 1-10，`strengths` / `problems` / `suggestions` 设 `min_length=1` 防止空报告。
- 生成逻辑：`app/app/love_app.py` 的 `LoveApp.generate_report()`，复用会话记忆，
  经 `ChatPromptTemplate` 组装为消息列表后走 `with_structured_output`。
- **method 自动回退**：按 `json_schema` → `function_calling` 顺序尝试，
  适配 DashScope 上不同模型对协议支持度的差异；两者都失败抛 `RuntimeError`（接口映射为 400）。
- 知识库检索失败会静默降级为无参考生成，不影响报告产出。
- PDF 渲染：`app/core/report_pdf.py`，分节排版（摘要 / 优势 / 问题 / 风险 / 建议 / 结语），
  使用 `STSong-Light` 中文字体；未装 `reportlab` 时抛 `RuntimeError`。

### 5. 构建知识库示例

```bash
curl -X POST http://localhost:8000/api/knowledge/build \
  -H "Content-Type: application/json" \
  -d "{\"force_rebuild\": true}"
```

### 6. RAG 数据源：接入阿里云百炼知识库

项目默认用**本地向量库**（`app/rag/documents/*.md` 自建索引）。
如果你在百炼控制台已经配置好知识库，可以一键切换数据源，**业务代码零改动**。

#### 切换方式

```bash
# .env
RAG_BACKEND=bailian
BAILIAN_WORKSPACE_ID=llm-xxxxxxxxxxxx   # 业务空间 ID
BAILIAN_INDEX_ID=kb_xxxxxxxxxxxx        # 知识库 ID（单库检索）
# 或
BAILIAN_AGENT_ID=aid-xxxxxxxxxxxxxxxx   # 知识检索服务 ID（跨库联合检索，优先）
```

配置项获取位置：

| 配置项 | 控制台位置 | 格式 |
|---|---|---|
| `BAILIAN_WORKSPACE_ID` | 业务空间管理 | `llm-xxxxxxxxxxxx` |
| `BAILIAN_INDEX_ID` | 数据接入 → 知识管理 → 点知识库复制 | 知识库 ID |
| `BAILIAN_AGENT_ID` | 知识服务 → 知识检索 → 创建并**发布** | `aid-xxxxxxxxxxxxxxxx` |

> `DASHSCOPE_API_KEY` 两处通用，百炼知识库不额外需要 Key。

#### 两条检索路径

| 配置 | 接口 | 特点 |
|---|---|---|
| 只配 `BAILIAN_INDEX_ID` | `POST /api/v1/indices/rag/index/retrieve` | 直接返回向量+关键词召回，**不做 Rerank**，可传 `top_k` |
| 配 `BAILIAN_AGENT_ID` | `POST /api/v1/indices/knowledge/search` | 多库权重、知识路由、混排模型在控制台**发布**后生效；接口不暴露 `top_k` |

两者都走统一网关 `https://{workspaceId}.{region}.maas.aliyuncs.com`。
`agent_id` 优先级更高，两者都配时走跨库检索。

#### 验证配置

用控制台工具最直接：

```bash
python chat_cli.py
> /kb          # 查看当前数据源与完整配置
> /kb check    # 发起一次真实检索做连通性自检
```

或走 HTTP：

```bash
curl "http://localhost:8000/api/knowledge/backend?check=true"
```

#### 实现要点

- 客户端：`app/rag/bailian_kb.py` 的 `BailianKnowledgeClient`，
  两条路径由 `use_agent` 自动选择，请求体按各自参数表分别构造
  （`knowledge/search` 只认 `agent_id` / `query`，多传 `top_k` 可能触发 `InvalidParameter`）。
- LangChain 适配：`BailianKnowledgeRetriever(BaseRetriever)`，可接入任意 LCEL 链。
- 统一入口：`app/rag/retriever.py` 的 `similarity_search` / `as_retriever`
  按 `settings.rag_mode` 路由，`chat_with_rag` 与恋爱报告**无需感知数据源差异**。
- **以 `success` 字段判定成败**：百炼可能在 HTTP 200 下返回业务失败，只判状态码会漏掉错误。
- 配置不全时 `rag_mode` 自动回退 `local`，不会因漏填配置让整个 RAG 不可用。
- `BAILIAN_KB_FALLBACK_LOCAL=true` 可在百炼临时故障时降级本地向量库继续服务。

**已知限制**

- `agent` 模式下召回条数由控制台发布配置决定，客户端仅按 `BAILIAN_KB_TOP_K` 做二次截断。
- 百炼检索是同步 HTTP 调用；`/api/knowledge/backend` 用同步 `def` 定义以便 FastAPI 调度到线程池，
  但 `chat_with_rag` 本身仍是同步链路，高并发场景建议再包一层线程池。

---

### 7. 前端调用（uni-app 跨端）

`uniapp/` 是一套代码编译 **H5 / 微信小程序 / App** 的前端，Vue3 + Axios。

| 页面 | 应用 | 调用接口 |
|---|---|---|
| 主页 | 应用切换（并做后端健康检查） | `GET /api/health` |
| 页面 1 | AI 恋爱大师 | `GET /api/ai/love_app/chat/sse` |
| 页面 2 | AI 超级智能体 | `GET /api/ai/manus/chat` |

聊天室交互：用户消息在右、AI 在左，进入页面自动生成 `chatId`，AI 回复**逐字流式渲染**；流式中按钮变「停止」可中断，顶部可复制会话 ID / 一键重新开始。

```bash
cd uniapp
npm install --ignore-scripts     # Windows 踩坑见 uniapp/README.md
npm run dev:h5                   # 浏览器打开 http://localhost:5173
npm run build:mp-weixin          # 产物 dist/build/mp-weixin，用微信开发者工具导入
npm run build:app                # 产物 dist/build/app，用 HBuilderX 打包
```

**SSE 为什么不用 Axios**：Axios 面向一次性响应，不支持持久流式推送。因此三端分别实现（`uniapp/src/utils/sse.js`）：

| 平台 | 实现 |
|---|---|
| H5 / App | 原生 `EventSource` |
| 微信小程序 | `uni.request({ enableChunked: true })` + `onChunkReceived` 手动解析字节流 |

靠 uni-app **条件编译**（`#ifdef H5 \|\| APP-PLUS` / `#ifndef`）隔离，已验证三端产物互不污染。

**后端地址配置**：改 `uniapp/.env.development` / `.env.production` 里的 `VITE_API_BASE_URL`、`VITE_SSE_BASE_URL`，
代码通过 `import.meta.env` 读取；另支持 `--mode staging` 加载 `.env.staging`。

```bash
curl -N "http://localhost:8000/api/ai/love_app/chat/sse?message=你好&chatId=test_1"   # 可直接在终端看流式输出
```

> 详细说明（安装踩坑、各端配置、FAQ）见 [`uniapp/README.md`](uniapp/README.md)。

---

## 六、工具清单（Tool Calling）

ReAct 智能体可调用以下 8 个工具：

| 工具名 | 功能 |
|---|---|
| `search_love_knowledge` | 检索恋爱知识库 |
| `write_file` | 写入文件 |
| `read_file` | 读取文件 |
| `download_resource` | 下载网络资源 |
| `scrape_webpage` | 抓取网页正文 |
| `web_search` | 联网搜索（需 SearchAPI Key）|
| `generate_pdf` | 生成 PDF 报告（需 reportlab）|
| `terminate` | 结束 ReAct 循环 |

---

## 七、测试

### 推荐：一键入口（自动找 pytest，找不到就用内置 runner）

```bash
python run_tests.py                 # 跑全部测试
python run_tests.py -v              # 详细输出
python run_tests.py memory          # 只跑多轮记忆相关测试（关键字过滤）
python run_tests.py report -s       # 报告测试，并显示测试里的 print 输出
python run_tests.py --no-pytest     # 强制用内置 runner（不需要装 pytest）
```

### 直接用 pytest

```bash
python -m pytest tests/ -v                    # 全部测试
python -m pytest tests/test_chat_memory.py -v # 仅多轮对话会话记忆
python -m pytest tests/test_love_report.py -v # 仅恋爱报告（结构化输出）
python -m pytest tests/ -s                    # -s 显示测试内的 print 输出
python -m pytest tests/ -k "report"           # 只跑用例名/文件名含 report 的
```

### 冒烟测试

```bash
python -m tests.test_smoke
```

| 测试文件 | 用例数 | 覆盖内容 |
|---|---|---|
| `tests/test_smoke.py` | 6 | 依赖导入、路由注册、知识库加载、健康检查 |
| `tests/test_chat_memory.py` | 9 | 多轮对话记忆：历史注入 Prompt、会话隔离、重启恢复、窗口裁剪、HTTP 端到端 |
| `tests/test_love_report.py` | 13 | 恋爱报告：结构化输出、历史注入、method 回退、模型校验、RAG 注入与降级、PDF 导出 |
| `tests/test_chat_cli.py` | 24 | 控制台工具：交互循环、多轮记忆注入、各内置命令、模式切换、报告渲染、`/kb` 数据源诊断、EOF 优雅退出 |
| `tests/test_bailian_kb.py` | 33 | 百炼知识库：两条检索路径的请求构造、响应解析、失败处理、路由分流与降级、端到端注入 Prompt |
| `tests/conftest.py` | — | 全局夹具：把记忆目录重定向到临时目录，避免污染 `tmp/memory/` |

当前全量结果：**94 passed**。

> 三个测试文件均**无需 API Key**，全部用假模型替换 `app.models.get_chat_model`：
> - `test_chat_memory.py` 的 `RecordingFakeChatModel` 按脚本返回回答，并记录每轮实际送入模型的消息列表，
>   以此断言「上一轮对话确实进入了下一轮 Prompt」。
> - `test_love_report.py` 的 `FakeStructuredLLM` 让 `with_structured_output` 返回 `RunnableLambda`
>   （与真实 API 一致），可直接返回预设 `LoveReport`，并支持模拟指定 method 失败以验证回退逻辑。
>
> 测试全程使用临时目录，不污染 `tmp/memory/` 与 `tmp/pdf/`。

### 看不到结果 / 想手动验证时

测试是断言驱动、默认静默的，感受不到「对话」。若要肉眼看到输出：

1. `python run_tests.py report -s` —— 让测试打印它收到的 Prompt 与回答。
2. `python chat_cli.py` —— 直接在控制台打字对话，是最贴近真实体验的方式。

> 测试全程写入临时目录（见 `tests/conftest.py`），不会在 `tmp/memory/` 留下任何会话文件。

---

## 八、Docker 部署

```bash
# 构建并启动全部服务
docker-compose up -d --build

# 查看日志
docker-compose logs -f api
```

---

## 九、常见问题

**Q：启动报 `DASHSCOPE_API_KEY 未配置`？**
A：这是预期提示。填好 `.env` 中的 Key 后重启即可启用大模型能力。

**Q：PGVector 连接失败？**
A：确认已执行 `docker-compose up -d pgvector`，且 `.env` 中数据库配置一致。系统会自动降级为内存向量库，不影响接口调试。

**Q：`pip install` 速度慢？**
A：已默认使用清华源。可换阿里源：`-i https://mirrors.aliyun.com/pypi/simple/`

**Q：MCP 工具加载失败？**
A：MCP 依赖当前与核心栈冲突，已在 `requirements-optional.txt` 中封存，详见「三之二、依赖版本约束」。

---

## 十、故障排查

### 症状：`python main.py` 报 `ModuleNotFoundError: No module named 'langsmith'`

**根因**：安装扩展依赖时 pip 升级了 `starlette`/`pydantic`，过程中卸载了 `langsmith`（`langchain-core` 的必需依赖），且进程中断导致 venv 停留在半卸载状态。

**修复**：

```bash
# 1. 清理中断卸载的残留目录
Remove-Item .\.venv\Lib\site-packages\~* -Recurse -Force

# 2. 重装核心依赖（自动拉回 langsmith 与正确版本的 starlette）
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 校验
.\.venv\Scripts\python.exe -m pip check
```

### 症状：终端刷 `StarletteDeprecationWarning` 或 `RequestsDependencyWarning`

**根因**：依赖被升级/污染，或 `reportlab` 拉入了 `chardet 7.x`。

**修复**：重装核心依赖（同上），并把 `chardet` 锁回 `5.2.0`：

```bash
.\.venv\Scripts\python.exe -m pip install "chardet==5.2.0"
```

### 症状：`pip check` 提示 `fastapi has requirement starlette<0.42, but you have starlette 1.6.0`

**根因**：安装了 MCP 相关包，其 `sse-starlette` 依赖强升 `starlette`。

**修复**：卸载 MCP 包后重装核心依赖，`starlette` 会自动降回 `0.41.3`：

```bash
.\.venv\Scripts\python.exe -m pip uninstall -y mcp mcp-types sse-starlette langchain-mcp-adapters
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 通用原则

依赖出问题后**不要逐个救包**（容易修 A 坏 B）。`requirements.txt` 已钉死全部版本，重装即可回归正确状态。
