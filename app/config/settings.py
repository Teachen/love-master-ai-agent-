"""恋爱大师 - 统一配置管理（按环境分层）

## 加载顺序（后面的覆盖前面的）

    .env            本机实际配置：基线 + 密钥。**不入库**（.gitignore 已排除）
    .env.<环境>     该环境的覆盖项：提交入库，**禁止写任何密钥**
    系统环境变量    最高优先级 —— 云托管控制台 / CI / 命令行临时覆盖

## 环境怎么选

由 `APP_ENV` 决定，解析优先级：

    系统环境变量 APP_ENV  >  .env 文件里的 APP_ENV  >  "dev"

取值（含常见别名，如 development / production / cloudrun）：

    dev      本地开发（默认）——  DEBUG=true、MYSQL 关、短信走开发模式
    test     跑自动化测试时用
    staging  预发
    prod     生产 —— DEBUG=false、MySQL 开、短信走真实通道（腾讯云或阿里云）

切换方式：

    # Windows CMD
    set APP_ENV=prod && python main.py
    # PowerShell
    $env:APP_ENV="prod"; python main.py
    # Git Bash / Linux / macOS
    APP_ENV=prod python main.py
    # 或者直接改 .env 里的 APP_ENV=xxx 一行（推荐本地开发用这种方式）

> 云托管容器里 `.env*` 被 .dockerignore 排除，配置全部来自控制台环境变量，
> 所以镜像里不存在密钥泄露风险。见 docs/环境配置说明.md
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 标准环境名，顺序即加载顺序（后者覆盖前者）
SUPPORTED_ENVS = ("dev", "test", "staging", "prod")

# 环境名别名 → 标准名（兼容各种写法，避免拼错就静默退回默认值）
_ENV_ALIASES = {
    "dev": "dev",
    "development": "dev",
    "local": "dev",
    "debug": "dev",
    "test": "test",
    "testing": "test",
    "unittest": "test",
    "staging": "staging",
    "stage": "staging",
    "pre": "staging",
    "uat": "staging",
    "prod": "prod",
    "production": "prod",
    "online": "prod",
    "release": "prod",
    "cloudrun": "prod",
    "cloud": "prod",
}


def project_root() -> Path:
    """项目根目录。

    用「requirements.txt + app/ 目录」双条件向上定位，而不是用 Path.cwd()：
    uvicorn / 测试 / IDE 的启动工作目录各不相同，锚定项目根才不会「换个方式启动就读不到 .env」。
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir():
            return parent
    return Path.cwd()


PROJECT_ROOT = project_root()


def read_env_value(path: Path, key: str) -> str:
    """从 .env 文件里读单个键。

    只为解析 APP_ENV 而写的最小实现：不处理 `${VAR}` 插值、多行值等高级语法
    （要读的值就是个简单标识符，够用且不引入额外依赖）。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip().upper() == key.upper():
            return v.split("#")[0].strip().strip('"').strip("'")
    return ""


def resolve_env_name() -> str:
    """解析当前运行环境名（标准名）"""
    raw = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "").strip()
    if not raw:
        # 允许「改 .env 里的一行」就切换环境，不必每次都设系统环境变量
        raw = read_env_value(PROJECT_ROOT / ".env", "APP_ENV")
    if not raw:
        raw = "dev"
    return _ENV_ALIASES.get(raw.lower(), raw.lower())


ENV_NAME = resolve_env_name()


def describe_env_files(env_name: str = "") -> list[tuple[str, Path, bool]]:
    """列出候选配置文件：[(文件名, 绝对路径, 是否存在)]

    先 .env（基线）后 .env.<环境>（覆盖），顺序即覆盖顺序。
    """
    name = env_name or ENV_NAME
    out = []
    for fn in (".env", f".env.{name}"):
        path = PROJECT_ROOT / fn
        out.append((fn, path, path.exists()))
    return out


def _env_files() -> tuple[str, ...]:
    """pydantic-settings 的 env_file 参数：只保留真实存在的文件"""
    return tuple(str(p) for _, p, exists in describe_env_files() if exists)


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        # 元组形式：后面的文件覆盖前面的；系统环境变量始终优先级最高
        env_file=_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 真正会「发短信」的通道。除这些之外的值一律按开发模式处理（验证码回显）。
    # 用 ClassVar 声明：pydantic 不会把它当成配置字段，避免被 .env 覆盖。
    #
    # aliyun_pnvs = 阿里云**号码认证服务**的「短信认证」（dypnsapi.SendSmsVerifyCode）。
    #   与 aliyun（短信服务 dysmsapi）的区别很关键：
    #   - 短信服务需企业实名认证（签名实名制报备要求提供企业资质），个人账号走不通；
    #   - 号码认证用平台赠送的签名和模板，**个人实名账号即可开通**，代价是签名不可自定义。
    REAL_SMS_PROVIDERS: ClassVar[tuple] = ("tencent", "aliyun", "aliyun_pnvs")

    # ---------- 服务基础配置 ----------
    app_name: str = Field(default="恋爱大师", description="应用名称")
    app_env: str = Field(default=ENV_NAME, description="运行环境：dev/test/staging/prod")
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

    # ---------- 对话历史存储（MySQL） ----------
    # 云托管容器文件系统不持久，历史记录必须落库。
    # 关闭时（本地开发没装 MySQL）前端自动回退本地存储，不影响其他功能。
    mysql_enabled: bool = Field(
        default=False, description="是否启用 MySQL 存储对话历史"
    )
    mysql_host: str = Field(default="localhost", description="MySQL 主机")
    mysql_port: int = Field(default=3306, description="MySQL 端口")
    mysql_database: str = Field(default="love_master", description="数据库名")
    mysql_user: str = Field(default="root", description="用户名")
    mysql_password: str = Field(default="", description="密码")
    mysql_charset: str = Field(default="utf8mb4", description="字符集")
    # 连接池
    mysql_pool_size: int = Field(default=5, description="连接池大小")
    mysql_pool_recycle: int = Field(
        default=280, description="连接回收秒数（小于 MySQL wait_timeout）"
    )

    # ---------- 账号体系（手机号 / 微信登录） ----------
    # 设计目标：三端同一套账号，登录后对话历史按 user_id 云端同步；
    #          未登录（游客）仍可正常使用，登录时把游客数据合并过来。
    auth_enabled: bool = Field(default=True, description="是否开放账号接口")
    jwt_secret: str = Field(
        default="",
        description="Token 签名密钥；留空则用内置开发密钥（生产环境必须显式配置）",
    )
    token_expire_days: int = Field(default=30, description="登录态有效期（天）")

    # 短信服务：none=开发模式（验证码直接回显，不发真实短信，便于本地联调）
    #          tencent=腾讯云短信（需 SecretId/Key + SdkAppId + 签名 + 模板）
    #          aliyun =阿里云短信（需 AccessKeyId/Secret + 签名 + 模板 Code）
    # 两个真实通道的差别：腾讯云走 POST JSON + TC3-HMAC-SHA256 签名，
    # 阿里云走表单 POST + RPC 风格 HMAC-SHA1 签名（见 app/api/auth.py）。
    sms_provider: str = Field(default="none", description="短信通道：none / tencent / aliyun")
    sms_allow_dev_code_in_prod: bool = Field(
        default=False,
        description="生产环境是否允许回显验证码。默认禁止："
        "生产环境回显验证码 = 任何人用任意手机号请求即可拿到码并接管账号",
    )
    sms_code_ttl: int = Field(default=300, description="验证码有效期（秒）")
    sms_send_interval: int = Field(default=60, description="同一手机号两次发送最小间隔（秒）")
    sms_daily_limit: int = Field(default=10, description="同一手机号单日发送上限")
    tencent_secret_id: str = Field(default="", description="腾讯云 SecretId（短信）")
    tencent_secret_key: str = Field(default="", description="腾讯云 SecretKey（短信）")
    tencent_sms_sdk_app_id: str = Field(default="", description="腾讯云短信 SdkAppId")
    tencent_sms_sign_name: str = Field(default="", description="腾讯云短信签名内容")
    tencent_sms_template_id: str = Field(default="", description="腾讯云短信模板 ID")

    # ---------- 阿里云短信 ----------
    # AccessKey 建议用 RAM 子账号并只授「AliyunDysmsFullAccess」，不要用主账号密钥。
    aliyun_access_key_id: str = Field(default="", description="阿里云 AccessKeyId")
    aliyun_access_key_secret: str = Field(default="", description="阿里云 AccessKeySecret")
    aliyun_sms_sign_name: str = Field(
        default="", description="阿里云短信签名名称（需审核通过，短信里【】内的内容）"
    )
    aliyun_sms_template_code: str = Field(
        default="", description="阿里云短信模板 Code，形如 SMS_154950909"
    )
    aliyun_sms_region: str = Field(default="cn-hangzhou", description="阿里云短信接入区域")
    aliyun_sms_endpoint: str = Field(
        default="dysmsapi.aliyuncs.com", description="阿里云短信接入地址（一般不用改）"
    )
    aliyun_sms_code_param: str = Field(
        default="code",
        description="验证码在模板里的变量名。阿里云模板形如「您的验证码为${code}，"
        "5分钟内有效」，这里的值要与 ${} 里的名字完全一致，写错会返回 isv.PARAM_LENGTH_LIMIT 之类的报错",
    )

    # 微信小程序（后端 code2Session 换 openid 用；AppSecret 绝不能下发到前端）
    wechat_miniapp_appid: str = Field(default="", description="小程序 AppID")
    wechat_miniapp_secret: str = Field(default="", description="小程序 AppSecret")

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

    # ---------- 环境判定与自检 ----------
    @property
    def is_production(self) -> bool:
        """是否生产环境（用于决定要不要打安全告警、禁止危险默认值）"""
        return self.app_env.strip().lower() in ("prod", "production", "online", "release")

    @property
    def env_files_loaded(self) -> List[str]:
        """本次实际加载的配置文件（相对项目根），供启动横幅与 /api/health 展示。

        排查「我明明改了配置却不生效」时，第一步就看这里少没少文件。
        """
        return [fn for fn, _, exists in describe_env_files(self.app_env) if exists]

    @property
    def sms_dev_code_exposed(self) -> bool:
        """是否在接口响应里回显短信验证码（仅开发/测试环境允许）"""
        if not self.sms_dev_mode:
            return False
        return (not self.is_production) or self.sms_allow_dev_code_in_prod

    @property
    def config_warnings(self) -> List[str]:
        """生产环境下的「可以公开」的配置告警。

        刻意**不含** JWT_SECRET 相关项：本属性会经 /api/health/config 对外暴露，
        而「你的签名密钥还是内置默认值」这句话等于直接告诉攻击者
        "可以拿源码里的默认密钥伪造任意用户 token"。密钥类告警只在服务端日志里打
        （见 jwt_warning）。
        """
        if not self.is_production:
            return []
        warns: List[str] = []
        if self.debug:
            warns.append("DEBUG=true：生产环境请关掉（.env.prod 已默认 false）")
        if self.sms_dev_mode and not self.sms_allow_dev_code_in_prod:
            warns.append(
                "SMS_PROVIDER 不是 tencent/aliyun：短信验证码接口将直接返回 503，"
                "手机号登录不可用；生产请配置阿里云或腾讯云短信"
            )
        elif self.sms_channel_missing:
            warns.append(
                "短信通道配置不完整，缺少："
                + "、".join(self.sms_channel_missing)
                + "；验证码会发送失败（接口返回 502）"
            )
        if not self.db_url:
            warns.append("MYSQL_ENABLED=false：对话历史只能存在本机，容器重启即丢")
        if self.cors_origins == ["*"]:
            warns.append("CORS_ORIGINS=*：生产建议收敛为具体域名")
        return warns

    @property
    def jwt_warning(self) -> str:
        """签名密钥告警 —— 只在服务端日志输出，不进任何 HTTP 响应"""
        if not (self.is_production and self.jwt_secret_is_default):
            return ""
        return (
            "JWT_SECRET 未配置：正在使用内置开发密钥，任何人只要读到源码就能伪造登录态；"
            "请在环境变量里配置一个随机 64 位十六进制串"
            "（生成：python -c \"import secrets;print(secrets.token_hex(32))\"）"
        )

    @property
    def config_summary(self) -> dict:
        """不含敏感值的配置摘要（启动日志 / 健康检查共用，可安全对外暴露）"""
        return {
            "env": self.app_env,
            "envFiles": self.env_files_loaded,
            "debug": self.debug,
            "llm": "ready" if self.llm_ready else "missing",
            # 请求值与生效值分开：配了 bailian 但参数不全时会自动回退 local，
            # 只看一个字段会误以为配置没生效
            "ragRequested": self.rag_backend,
            "ragEffective": self.rag_mode,
            "historyDb": "mysql" if self.mysql_enabled else "off(本地存储)",
            "auth": self.auth_enabled,
            "sms": self.sms_provider,
            # 把「能不能真发出去」和「还缺哪几项」一起暴露出来：
            # 排查「发送验证码不可用」时，先看这两项，不用去翻日志。
            "smsReady": self.sms_ready,
            "smsMissing": self.sms_channel_missing,
            # 会不会真的扣短信费。之前只有 smsDevMode 一个布尔值，
            # 「本地联调时到底有没有真发短信」只能靠人记着，
            # 而本地和线上共用同一个阿里云账号/签名/号码的频控额度
            # （1 条/分钟、5 条/小时、10 条/天），本地狂点会挤掉线上的额度。
            "smsRealSend": not self.sms_dev_mode,
            "smsDevCodeExposed": self.sms_dev_code_exposed,
            # 签名与模板 CODE 不算秘密（签名本来就会显示在短信里），
            # 暴露出来是为了「App 报 INVALID_PARAMETERS 时，
            # 直接拿这里的值和阿里云控制台/门户调试成功的参数逐字比对」，
            # 不用登服务器翻环境变量。
            "smsSignName": self.aliyun_sms_sign_name,
            "smsTemplateCode": self.aliyun_sms_template_code,
            "warnings": self.config_warnings,
        }

    @property
    def db_url(self) -> str:
        """对话历史的数据库连接串（SQLAlchemy 格式）

        - 未启用（mysql_enabled=False）返回空串，调用方据此降级到本地存储
        - 支持 sqlite:/// 开头，便于本地无 MySQL 时自测（生产不要这样用）
        """
        if not self.mysql_enabled:
            return ""
        if self.mysql_host.startswith("sqlite"):
            return self.mysql_host  # 本地自测：直接给完整 SQLAlchemy URL
        from urllib.parse import quote_plus

        return (
            f"mysql+pymysql://{quote_plus(self.mysql_user)}:"
            f"{quote_plus(self.mysql_password)}@{self.mysql_host}:{self.mysql_port}"
            f"/{self.mysql_database}?charset={self.mysql_charset}"
        )

    @property
    def jwt_secret_effective(self) -> str:
        """实际生效的签名密钥。

        开发环境允许留空（用内置密钥，重启后登录态不失效）；
        生产环境留空会告警 —— 密钥变了所有用户的登录态都会失效。
        """
        if self.jwt_secret.strip():
            return self.jwt_secret.strip()
        return f"love-master-dev-secret::{self.app_name}"

    @property
    def jwt_secret_is_default(self) -> bool:
        """是否在用内置开发密钥（生产环境应显式配置 JWT_SECRET）"""
        return not self.jwt_secret.strip()

    @property
    def sms_dev_mode(self) -> bool:
        """是否开发模式短信（验证码直接回显，不产生短信费用）

        判定为「provider 不在真实通道集合里」而不是「不等于 tencent」——
        后者在新增阿里云通道时会静默失效：配了 aliyun 却被当成开发模式，
        于是生产环境既不真发短信也不回显验证码，登录直接死掉。
        """
        return self.sms_provider.strip().lower() not in self.REAL_SMS_PROVIDERS

    @property
    def sms_channel_missing(self) -> List[str]:
        """当前短信通道还缺哪些配置项（空列表 = 配置完整）

        用途：把「发送验证码不可用」从一句笼统的 503 变成可执行的清单。
        provider 写错时会返回提示项本身，避免出现「什么都不缺但还是发不出去」。
        """
        p = self.sms_provider.strip().lower()
        if p not in self.REAL_SMS_PROVIDERS:
            return [
                f"SMS_PROVIDER 需为 tencent / aliyun / aliyun_pnvs（当前：{self.sms_provider or '空'}）"
            ]
        if p == "tencent":
            pairs = [
                ("TENCENT_SECRET_ID", self.tencent_secret_id),
                ("TENCENT_SECRET_KEY", self.tencent_secret_key),
                ("TENCENT_SMS_SDK_APP_ID", self.tencent_sms_sdk_app_id),
                ("TENCENT_SMS_SIGN_NAME", self.tencent_sms_sign_name),
                ("TENCENT_SMS_TEMPLATE_ID", self.tencent_sms_template_id),
            ]
        else:
            # 两个阿里云通道的配置项一样：签名名 + 模板 Code + AccessKey。
            # 区别只是「aliyun 用自己申请的」「aliyun_pnvs 用控制台赠送的」。
            pairs = [
                ("ALIYUN_ACCESS_KEY_ID", self.aliyun_access_key_id),
                ("ALIYUN_ACCESS_KEY_SECRET", self.aliyun_access_key_secret),
                ("ALIYUN_SMS_SIGN_NAME", self.aliyun_sms_sign_name),
                ("ALIYUN_SMS_TEMPLATE_CODE", self.aliyun_sms_template_code),
            ]
        return [name for name, value in pairs if not str(value).strip()]

    @property
    def sms_ready(self) -> bool:
        """真实短信通道是否可直接使用（开发模式恒为 False：它本来就不发短信）"""
        return not self.sms_dev_mode and not self.sms_channel_missing

    @property
    def wechat_login_ready(self) -> bool:
        """小程序登录是否可用（需配齐 AppID + AppSecret）"""
        return bool(self.wechat_miniapp_appid.strip()) and bool(
            self.wechat_miniapp_secret.strip()
        )

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
