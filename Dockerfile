# ============================================================
# 恋爱大师 - 微信云托管部署镜像
#
# 微信云托管与本地开发的关键差异（踩过的坑都写在这了）：
#   1. 必须监听 0.0.0.0，端口由「新建版本」时控制台填写，默认 80；
#      端口范围 1~61000 且不能是 9100。所以下面用 ${PORT} 动态展开，
#      而不是像本地那样写死 8000。
#   2. 手动上传代码包时整包 ≤ 2 MiB —— 必须配 .dockerignore，
#      把 .venv / uniapp/dist / data / 文档素材 / 截图全部排除。
#   3. 环境变量在「服务设置 → 环境变量」里配，不要依赖镜像里的 .env
#      （.dockerignore 已强制排除 .env，避免 API Key 泄露进镜像）。
# ============================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    PIP_NO_CACHE_DIR=1 \
    PORT=80

WORKDIR /app

# ---------- 系统依赖 ----------
# 刻意不装 build-essential / libpq-dev：
# psycopg[binary] 自带预编译 libpq，lxml、pypdf 也都有 manylinux 轮子，
# 无需编译即可安装。能显著减小镜像体积、缩短云托管构建时间。
# curl 仅用于容器健康检查。
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- 核心 Python 依赖 ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- 按需扩展依赖 ----------
# requirements-optional.txt 里各组件互斥，不可整包安装，这里只挑实际用到的：
#   requests  —— app/tools/love_tools.py 模块级 import，属硬依赖，缺了会直接崩
#   reportlab —— 恋爱报告 PDF 生成（app/core/report_pdf.py）
#   chardet   —— 锁 5.x，避免 reportlab 拉入 7.x 触发 requests 告警刷屏
# 明确不装：
#   playwright —— 容器内无浏览器内核且体积巨大（代码里 0 处引用）
#   ollama     —— 云托管跑不动本地大模型（get_ollama_chat_model 是函数内软依赖）
#   mcp / llama-index —— 与当前核心栈版本冲突，见 requirements-optional.txt 说明
RUN pip install --no-cache-dir requests==2.32.3 reportlab==4.2.5 chardet==5.2.0

# ---------- 应用代码 ----------
COPY . .

# 运行时目录：app/rag/document_loader.py 的 ensure_directories() 会用到
RUN mkdir -p /app/tmp/files /app/tmp/pdf /app/data

EXPOSE 80

# 容器健康检查（首次启动要导入 LangChain，start-period 给足 90s）
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

# 用 shell 形式，${PORT} 才能被云托管注入的环境变量覆盖
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
