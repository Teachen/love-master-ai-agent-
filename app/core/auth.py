"""恋爱大师 - 账号鉴权核心

为什么手写 JWT 而不引 PyJWT / python-jose？
- HS256 的 JWT 就是「base64url(header).base64url(payload).base64url(HMAC-SHA256)」，
  标准库 hashlib + hmac + base64 十几行就能覆盖，签名与 exp 校验都是白盒可见；
- 云托管每次构建都要重新装依赖，少一个包少一份不确定性。

对外能力：
- create_token / decode_token     登录态签发与校验（无状态，不落库）
- get_current_user_id             强校验依赖：未登录返回 401
- get_optional_user_id            弱校验依赖：未登录返回空串（游客）
- mask_phone                      手机号脱敏（日志/返回体用）
"""
import base64
import hashlib
import hmac
import json
import re
import time
import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# 未登录用户的 ID 前缀：游客数据存在这个空间下，登录时由
# /api/auth/merge-guest 迁移到真实账号，避免"一登录历史就没了"。
GUEST_PREFIX = "guest-"

# 手机号校验：中国大陆 11 位，1 开头，第二位 3-9
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

_bearer = HTTPBearer(auto_error=False)


# ----------------------------- 手机号工具 ----------------------------- #
def is_valid_phone(phone: str) -> bool:
    """是否是中国大陆手机号"""
    return bool(_PHONE_RE.match((phone or "").strip()))


def normalize_phone(phone: str) -> str:
    """归一化：去掉空格、+86 / 86 前缀"""
    p = (phone or "").strip().replace(" ", "").replace("-", "")
    if p.startswith("+86"):
        p = p[3:]
    elif p.startswith("86") and len(p) == 13:
        p = p[2:]
    return p


def mask_phone(phone: str) -> str:
    """138****8888；非手机号原样返回（不泄露）"""
    p = (phone or "").strip()
    return f"{p[:3]}****{p[-4:]}" if len(p) == 11 else p


# ----------------------------- JWT ----------------------------- #
def _b64u_encode(raw: bytes) -> str:
    """base64url 编码并去掉 padding（JWT 规范要求）"""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    """base64url 解码，自动补回 padding"""
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(message: str) -> str:
    """HS256 签名"""
    digest = hmac.new(
        settings.jwt_secret_effective.encode("utf-8"),
        message.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64u_encode(digest)


def create_token(user_id: str, days: int | None = None) -> tuple[str, int]:
    """签发登录态。

    @return (token, 有效秒数)
    """
    ttl = int((days if days is not None else settings.token_expire_days) * 86400)
    now = int(time.time())
    # JSON 用紧凑分隔符：JWT 段里不该有多余空格
    header = _b64u_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _b64u_encode(
        json.dumps(
            {"sub": user_id, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex[:16]},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}"
    return f"{signing_input}.{_sign(signing_input)}", ttl


def decode_token(token: str) -> dict:
    """校验并解析 token。

    失败一律返回空 dict（由调用方决定是 401 还是按游客处理），
    不抛异常，避免把签名错误暴露成 500。
    """
    if not token or token.count(".") != 2:
        return {}
    header_seg, payload_seg, sig_seg = token.split(".")
    # 恒定时间比较，防时序攻击
    if not hmac.compare_digest(sig_seg, _sign(f"{header_seg}.{payload_seg}")):
        return {}
    try:
        payload = json.loads(_b64u_decode(payload_seg))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(payload, dict):
        return {}
    if int(payload.get("exp", 0)) < int(time.time()):
        return {}
    return payload


# ----------------------------- FastAPI 依赖 ----------------------------- #
def _read_token(request: Request, cred: HTTPAuthorizationCredentials | None) -> str:
    """取 token：优先 Authorization: Bearer，其次 X-Token 头（小程序端兼容用）"""
    if cred and cred.scheme and cred.scheme.lower() == "bearer":
        return cred.credentials or ""
    return request.headers.get("X-Token", "")


def get_optional_user_id(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """弱校验：返回登录用户 ID；未登录/登录态过期返回空串（按游客处理）。

    用于「登录了就用云端的，没登录用本地的」这类可选鉴权接口。
    """
    return str(decode_token(_read_token(request, cred)).get("sub", "") or "")


def get_current_user_id(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """强校验：必须带有效登录态，否则 401。"""
    user_id = str(decode_token(_read_token(request, cred)).get("sub", "") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return user_id


def make_guest_id() -> str:
    """生成游客 ID（前端本地存储用，后端只在合并时见到）"""
    return GUEST_PREFIX + uuid.uuid4().hex[:16]


def is_guest_id(user_id: str) -> bool:
    """是否是游客空间（含历史遗留的 default）"""
    return (not user_id) or user_id == "default" or user_id.startswith(GUEST_PREFIX)
