"""恋爱大师 - 账号接口

接口一览（前缀 /api/auth）：
- GET  /config                 能力开关（前端据此决定展示哪些登录方式，公开）
- POST /sms/send               发送短信验证码（限频；开发模式直接回显验证码）
- POST /login/phone            手机号 + 验证码登录（未注册自动注册）
- POST /login/wechat           微信小程序 wx.login 换登录态（code2Session）
- POST /bind/phone             给当前账号绑定手机号（冲突时可自动合并空账号）
- POST /merge-guest            把游客时期的对话历史迁到当前账号
- GET  /me                     当前账号信息 + 已绑定登录方式
- POST /profile                改资料（昵称/头像/性别/生日/个性签名/情感状态）
- POST /logout                 退出登录（无状态，前端删 token 即可）

设计约定：
- 登录态是自签的 HS256 JWT，服务端不存 session，水平扩容无需共享存储。
- 数据库不可用时：只读接口降级返回，登录类接口返回 503（前端提示"服务未就绪"）。
- 微信 AppSecret 只在服务端使用，绝不下发到前端。
"""
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.auth import (
    get_current_user_id,
    is_guest_id,
    is_valid_phone,
    mask_phone,
    normalize_phone,
)
from app.core.auth import create_token as _create_token
from app.db import (
    PROVIDER_PHONE,
    PROVIDER_WECHAT_MINIAPP,
    ChatMessage,
    ChatSession,
    SmsCode,
    User,
    UserIdentity,
    db_ready,
    session_scope,
)
from app.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["账号"])

_WECHAT_CODE2SESSION = "https://api.weixin.qq.com/sns/jscode2session"
_WECHAT_TIMEOUT = 8


# ----------------------------- Schemas ----------------------------- #
class SmsSendIn(BaseModel):
    phone: str = Field(description="手机号，支持 +86 前缀")
    scene: Literal["login", "bind"] = "login"


class PhoneLoginIn(BaseModel):
    phone: str
    code: str


class WechatLoginIn(BaseModel):
    code: str = Field(description="wx.login / uni.login 拿到的临时凭证 code")
    appId: str = Field(default="", description="小程序 AppID，留空用服务端配置")


class BindPhoneIn(BaseModel):
    phone: str
    code: str
    autoMerge: bool = Field(
        default=True,
        description="当当前账号是空壳（无其他登录方式、无对话记录）时，"
        "是否自动并入手机号所属账号",
    )


class MergeGuestIn(BaseModel):
    guestId: str = Field(description="游客空间 ID（前端本地存储）")


class ProfileIn(BaseModel):
    """修改资料的入参。

    约定：`None` 表示「不改这一项」，空串表示「清空这一项」——
    前端只提交用户真正改过的字段，避免把没填的项误清空。
    同时接受 camelCase 与 snake_case（populate_by_name），
    前端习惯用 camelCase，Python 侧保留 snake_case 更自然。
    """

    model_config = ConfigDict(populate_by_name=True)

    nickname: str | None = None
    avatar: str | None = None
    gender: str | None = None
    birthday: str | None = None
    bio: str | None = None
    emotion_status: str | None = Field(default=None, alias="emotionStatus")


# 允许取值（空串 = 未填写）
_GENDERS = {"", "male", "female", "secret"}
# 单身的英文 emotion_status 常被误写成 single，这里统一收敛
_EMOTIONS = {"", "single", "in_love", "married", "secret"}
_BIRTHDAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ----------------------------- 工具 ----------------------------- #
def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _require_db() -> None:
    """账号类接口的数据库前置检查。

    提示语刻意写成「怎么修」而不是「不可用」：本地默认 MYSQL_ENABLED=false，
    于是进登录页点「发送验证码」只会看到一句笼统的 503，
    很容易误判成短信通道没配（实际是压根没有库存验证码）。
    """
    if not db_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "账号服务未就绪：验证码与账号都要落库。"
                "本地调试把 .env.dev 里 MYSQL_ENABLED 改为 true，"
                "并可用 MYSQL_HOST=sqlite:///./tmp/dev.db 零依赖自测；"
                "生产请配置 MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE。"
                "自检接口：GET /api/health/config"
            ),
        )


def _user_base(user: User) -> dict:
    """用户基础字段（不含已绑定登录方式）。

    `_user_out`（/me、/profile）与 `_issue`（登录响应）共用这一份字段清单。
    原先两处各写一份，结果给 User 加字段时只改了一处，
    登录响应里新字段直接缺失（前端读到 undefined）—— 这就是把它们收敛的原因。
    """
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "phone": mask_phone(user.phone) if user.phone else "",
        "hasPhone": bool(user.phone),
        "registerFrom": user.register_from,
        # ---------- 资料扩展 ----------
        "gender": user.gender or "",
        "birthday": user.birthday or "",
        "bio": user.bio or "",
        "emotionStatus": user.emotion_status or "",
        "createdAt": _fmt(user.created_at),
    }


def _user_out(user: User, identities: list[UserIdentity]) -> dict:
    """对外用户视图：手机号脱敏，附已绑定的登录方式"""
    return {
        **_user_base(user),
        "identities": [
            {
                "provider": i.provider,
                "appId": i.app_id,
                "boundAt": _fmt(i.created_at),
            }
            for i in identities
        ],
    }


def _load_user(db, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="账号不存在，请重新登录")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被停用")
    return user


def _identities_of(db, user_id: str) -> list[UserIdentity]:
    return list(
        db.scalars(
            select(UserIdentity)
            .where(UserIdentity.user_id == user_id)
            .order_by(UserIdentity.id)
        )
    )


def _find_identity(db, provider: str, app_id: str, open_id: str) -> UserIdentity | None:
    return db.scalar(
        select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.app_id == app_id,
            UserIdentity.open_id == open_id,
        )
    )


def _default_nickname(phone: str) -> str:
    return f"用户{phone[-4:]}" if len(phone) >= 4 else "恋爱大师用户"


def _upsert_identity(
    db,
    user: User,
    provider: str,
    app_id: str,
    open_id: str,
    union_id: str = "",
    session_key: str = "",
) -> UserIdentity:
    """写入/更新一条登录身份（幂等）。"""
    ident = _find_identity(db, provider, app_id, open_id)
    if ident is None:
        ident = UserIdentity(
            user_id=user.id,
            provider=provider,
            app_id=app_id,
            open_id=open_id,
        )
        db.add(ident)
    if union_id:
        ident.union_id = union_id
    if session_key:
        ident.session_key = session_key
    ident.updated_at = datetime.now()
    return ident


def _issue(user: User) -> dict:
    """签发登录态（用户字段与 /me 完全一致，见 _user_base）"""
    token, ttl = _create_token(user.id)
    return {
        "token": token,
        "tokenType": "Bearer",
        "expiresIn": ttl,
        "user": _user_base(user),
    }


# ----------------------------- 短信发送 ----------------------------- #
def _send_sms_by_tencent(phone: str, code: str) -> str:
    """腾讯云短信（TC3-HMAC-SHA256 签名）。返回实际下发的验证码。

    未配置短信通道时不会走到这里（sms_provider=none 为开发模式）。
    注意：本函数需要真实的 SecretId/Key + 已审核模板才能验证，
    本地无法自测；配好后可用 /api/auth/sms/send 实发一条确认。
    """
    import hashlib
    import hmac as _hmac
    import json as _json

    secret_id = settings.tencent_secret_id.strip()
    secret_key = settings.tencent_secret_key.strip()
    if not (secret_id and secret_key and settings.tencent_sms_sdk_app_id):
        raise RuntimeError("腾讯云短信配置不完整（SecretId/SecretKey/SdkAppId）")

    host = "sms.tencentcloudapi.com"
    action = "SendSms"
    version = "2021-01-11"
    region = "ap-guangzhou"
    service = "sms"
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

    payload = _json.dumps(
        {
            "PhoneNumberSet": [f"+86{phone}"],
            "SmsSdkAppId": settings.tencent_sms_sdk_app_id,
            "SignName": settings.tencent_sms_sign_name,
            "TemplateId": settings.tencent_sms_template_id,
            # 模板形如「您的验证码是{1}，{2}分钟内有效」，两个占位符
            "TemplateParamSet": [code, str(max(1, settings.sms_code_ttl // 60))],
        },
        separators=(",", ":"),
    )

    def _sha256hex(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _hmac256(key: bytes, msg: str) -> bytes:
        return _hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    canonical_headers = (
        "content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = (
        f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{_sha256hex(payload)}"
    )
    string_to_sign = (
        f"TC3-HMAC-SHA256\n{timestamp}\n{date}/{service}/tc3_request\n"
        f"{_sha256hex(canonical_request)}"
    )
    secret_date = _hmac256(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _hmac256(secret_date, service)
    secret_signing = _hmac256(secret_service, "tc3_request")
    signature = _hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{date}/{service}/tc3_request, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    resp = requests.post(
        f"https://{host}",
        data=payload.encode("utf-8"),
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": version,
            "X-TC-Region": region,
        },
        timeout=10,
    )
    data = resp.json().get("Response", {})
    if data.get("Error"):
        raise RuntimeError(
            f"腾讯云短信失败 {data['Error'].get('Code')}: {data['Error'].get('Message')}"
        )
    status = (data.get("SendStatusSet") or [{}])[0]
    if status.get("Code") and status["Code"] != "Ok":
        raise RuntimeError(f"短信下发失败 {status.get('Code')}: {status.get('Message')}")
    # 返回值语义与阿里云通道对齐：实际下发的验证码（腾讯云用我们传进去的那个）
    return code


def _aliyun_rpc_post(endpoint: str, action: str, extra: dict) -> dict:
    """调用阿里云 RPC 风格 OpenAPI（V1 签名：HMAC-SHA1 + Base64）。

    短信服务的 dysmsapi 与号码认证服务的 dypnsapi 都是这套签名，所以共用一份实现
    （官方文档：help.aliyun.com/zh/sdk/product-overview/rpc-mechanism）。

      CanonicalizedQueryString = 参数按 key 字典序 → "percentEncode(k)=percentEncode(v)" → "&" 连接
      StringToSign             = "POST&" + percentEncode("/") + "&" + percentEncode(CanonicalizedQueryString)
      Signature                = Base64(HMAC-SHA1(AccessKeySecret + "&", StringToSign))

    三个特别容易写错、错了只会得到一句 InvalidSignature 的点：
    1. percentEncode 里 `/` **必须**编码成 %2F。Python 的 quote 默认 safe='/'，所以要显式传 safe=''；
       而 -_.~ 按规范不编码，quote(safe='') 恰好也不编码，规则吻合。
    2. 待签名参数里**不能包含 Signature 本身**（先算签名，再作为普通参数塞进表单）。
    3. AccessKeySecret 后面要补一个 "&" 当 HMAC 密钥 —— 阿里云特有约定，漏了签名永远对不上。
    """
    import base64
    import hashlib
    import hmac as _hmac
    from urllib.parse import quote

    key_id = settings.aliyun_access_key_id.strip()
    key_secret = settings.aliyun_access_key_secret.strip()
    if not (key_id and key_secret):
        raise RuntimeError("阿里云配置不完整（ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET）")

    params = {
        "AccessKeyId": key_id,
        "Action": action,
        "Format": "JSON",
        "RegionId": settings.aliyun_sms_region.strip() or "cn-hangzhou",
        "SignatureMethod": "HMAC-SHA1",
        # 每次都换，防重放；阿里云要求 31 分钟内的请求才有效
        "SignatureNonce": uuid.uuid4().hex,
        "SignatureVersion": "1.0",
        # 必须是 UTC 的 ISO8601，用本地时间会直接报 InvalidTimeStamp
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2017-05-25",
        **extra,
    }

    def _pe(value) -> str:
        return quote(str(value), safe="")

    canonical = "&".join(f"{_pe(k)}={_pe(params[k])}" for k in sorted(params))
    string_to_sign = f"POST&{_pe('/')}&{_pe(canonical)}"
    digest = _hmac.new(
        f"{key_secret}&".encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1
    ).digest()
    params["Signature"] = base64.b64encode(digest).decode("utf-8")

    resp = requests.post(f"https://{endpoint}/", data=params, timeout=10)
    # 阿里云即使参数/签名错误也返回 HTTP 200，业务结果只看 Code 字段
    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(
            f"阿里云返回非 JSON（HTTP {resp.status_code}）：{resp.text[:200]}"
        ) from exc
    return data


def _send_sms_by_aliyun(phone: str, code: str) -> str:
    """阿里云短信服务（dysmsapi）—— 需企业实名认证 + 自己申请的签名与模板。

    ⚠️ 个人认证账号走不通：签名实名制报备要求签名归属方提供企业资质。
    个人开发者请改用 sms_provider=aliyun_pnvs（号码认证服务的短信认证）。
    """
    import json as _json

    sign_name = settings.aliyun_sms_sign_name.strip()
    template_code = settings.aliyun_sms_template_code.strip()
    if not (sign_name and template_code):
        raise RuntimeError(
            "阿里云短信配置不完整（ALIYUN_SMS_SIGN_NAME / ALIYUN_SMS_TEMPLATE_CODE，"
            "均需在控制台审核通过）"
        )

    data = _aliyun_rpc_post(
        settings.aliyun_sms_endpoint.strip() or "dysmsapi.aliyuncs.com",
        "SendSms",
        {
            "PhoneNumbers": phone,
            "SignName": sign_name,
            "TemplateCode": template_code,
            # 变量名必须与模板里 ${xxx} 完全一致，由 ALIYUN_SMS_CODE_PARAM 控制
            "TemplateParam": _json.dumps(
                {settings.aliyun_sms_code_param.strip() or "code": code}
            ),
        },
    )
    if data.get("Code") != "OK":
        raise RuntimeError(f"阿里云短信失败 {data.get('Code')}: {data.get('Message')}")
    return code


def _send_sms_by_aliyun_pnvs(phone: str, code: str) -> str:
    """阿里云号码认证服务 - 短信认证（dypnsapi）—— **个人实名账号可用**。

    与上面短信服务的本质差别：这里用平台**赠送的签名和模板**，不用自己申请，
    所以个人认证账号也能开通。代价是签名不能自定义（短信里【】内是阿里云分配的名字），
    且赠送签名必须搭配赠送模板使用。

    验证码由阿里云侧生成：TemplateParam 传占位符 "##code##" + ReturnVerifyCode=true，
    接口会把生成的验证码放在 Model.VerifyCode 里返回来。
    所以本函数**返回实际下发的验证码**而不是入参 code —— 上层要用它落库，
    否则用户收到的码和我们存的码不一致，永远校验不过。
    """
    import json as _json

    sign_name = settings.aliyun_sms_sign_name.strip()
    template_code = settings.aliyun_sms_template_code.strip()
    if not (sign_name and template_code):
        raise RuntimeError(
            "阿里云短信认证配置不完整（ALIYUN_SMS_SIGN_NAME / ALIYUN_SMS_TEMPLATE_CODE，"
            "取控制台「短信认证参数管理」里的赠送签名与赠送模板）"
        )

    code_param = settings.aliyun_sms_code_param.strip() or "code"
    data = _aliyun_rpc_post(
        "dypnsapi.aliyuncs.com",
        "SendSmsVerifyCode",
        {
            "PhoneNumber": phone,
            "CountryCode": "86",
            "SignName": sign_name,
            "TemplateCode": template_code,
            "TemplateParam": _json.dumps({code_param: "##code##"}),
            # 与本地校验的位数保持一致：我们自己也是存 6 位
            "CodeLength": "6",
            "CodeType": "1",
            "ValidTime": str(settings.sms_code_ttl),
            "Interval": str(settings.sms_send_interval),
            # 同一个号码在有效期内重复发送时，旧验证码作废（避免用户拿旧码反复试）
            "DuplicatePolicy": "1",
            "ReturnVerifyCode": "true",
            "AutoRetry": "1",
        },
    )
    if data.get("Code") != "OK":
        raise RuntimeError(
            f"阿里云短信认证失败 {data.get('Code')}: {data.get('Message')}"
            "（FUNCTION_NOT_OPENED = 还没在号码认证控制台开通短信认证）"
        )
    verify_code = str((data.get("Model") or {}).get("VerifyCode") or "").strip()
    if not verify_code:
        # 没回传验证码就说明配置与预期不符（比如模板变量名写错），
        # 此时绝不能返回入参 code：那样用户收到的会是别的码，登录必然失败
        raise RuntimeError(
            "阿里云短信认证未回传验证码（Model.VerifyCode 为空）："
            "请检查 RETURN_VERIFY_CODE 是否为 true、模板变量名是否与模板一致"
        )
    return verify_code


def _send_sms_real(phone: str, code: str) -> str:
    """按 SMS_PROVIDER 分派到具体通道，返回**实际下发**的验证码。

    返回值的意义：阿里云号码认证由服务端生成验证码，可能与入参不同，
    上层必须拿这个返回值落库，否则「收到的码」和「库里的码」会对不上。
    """
    provider = settings.sms_provider.strip().lower()
    if provider == "tencent":
        return _send_sms_by_tencent(phone, code)
    if provider == "aliyun":
        return _send_sms_by_aliyun(phone, code)
    if provider == "aliyun_pnvs":
        return _send_sms_by_aliyun_pnvs(phone, code)
    # 走到这里说明 sms_dev_mode 判定与分派表不一致（新增通道时最容易漏改这里）
    raise RuntimeError(f"未知的短信通道 SMS_PROVIDER={settings.sms_provider!r}")


@router.post("/sms/send", summary="发送短信验证码")
def send_sms(payload: SmsSendIn) -> dict:
    _require_db()
    phone = normalize_phone(payload.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    # 生产环境绝不允许"回显验证码"：那等于任何人用任意手机号请求即可拿到码，
    # 直接把别人的账号接管走。没配短信通道时**直接拒绝**，而不是退化成把码返回给调用方。
    if settings.sms_dev_mode and not settings.sms_dev_code_exposed:
        raise HTTPException(
            status_code=503,
            detail=(
                "短信服务未配置：请把 SMS_PROVIDER 设为 aliyun_pnvs（个人可用）/ aliyun / "
                "tencent 并补齐对应参数（缺项可用 GET /api/health/config 查看 smsMissing）"
            ),
        )

    now = datetime.now()
    with session_scope() as db:
        # ① 同号发送间隔
        last = db.scalar(
            select(SmsCode)
            .where(SmsCode.phone == phone)
            .order_by(SmsCode.id.desc())
            .limit(1)
        )
        if last:
            elapsed = (now - last.created_at).total_seconds()
            if elapsed < settings.sms_send_interval:
                raise HTTPException(
                    status_code=429,
                    detail=f"发送过于频繁，请 {int(settings.sms_send_interval - elapsed) + 1} 秒后再试",
                )
        # ② 单日上限
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_cnt = (
            db.scalar(
                select(func.count())
                .select_from(SmsCode)
                .where(SmsCode.phone == phone, SmsCode.created_at >= day_start)
            )
            or 0
        )
        if today_cnt >= settings.sms_daily_limit:
            raise HTTPException(status_code=429, detail="今日验证码次数已达上限，请明天再试")

        code = f"{secrets.randbelow(1000000):06d}"
        record = SmsCode(
            phone=phone,
            code=code,
            scene=payload.scene,
            expires_at=now + timedelta(seconds=settings.sms_code_ttl),
        )
        db.add(record)
        # flush 拿到主键，下面失败回滚时要用它删掉这一行
        db.flush()
        record_id = record.id

    if not settings.sms_dev_mode:
        try:
            sent_code = _send_sms_real(phone, code)
        except Exception as exc:  # noqa: BLE001
            logger.exception("短信下发失败（通道 %s）：%s", settings.sms_provider, exc)
            # 发失败就把刚才那行验证码删掉。
            # 不删的话有两个后果：① 这行会占掉「同号 60 秒间隔」和「单日上限」的名额，
            # 用户改完配置想立刻重试会被自己的失败记录挡住；② 库里留着一堆没发出去的废码。
            with session_scope() as db:
                stale = db.get(SmsCode, record_id)
                if stale is not None:
                    db.delete(stale)
            raise HTTPException(
                status_code=502,
                detail=f"短信发送失败（通道 {settings.sms_provider}）：{exc}",
            ) from exc

        # 阿里云号码认证由服务端生成验证码：把它替换成**真正下发**的那一个。
        # 不改的话用户收到的码与我们存的对不上，输入正确提示也永远是「验证码不正确」。
        if sent_code and sent_code != code:
            with session_scope() as db:
                row = db.get(SmsCode, record_id)
                if row is not None:
                    row.code = sent_code
            code = sent_code

    result = {
        "ok": True,
        "phone": mask_phone(phone),
        "expiresIn": settings.sms_code_ttl,
        "resendAfter": settings.sms_send_interval,
    }
    if settings.sms_dev_code_exposed:
        # 开发/测试环境：不回显就无法本地联调。
        # 生产环境（app_env=prod）默认走不到这里 —— 上面已拦截为 503。
        result["devCode"] = code
        result["notice"] = "开发模式（SMS_PROVIDER=none）：未发送真实短信，验证码见 devCode"
        logger.info("[开发模式] 手机号 %s 验证码 %s", mask_phone(phone), code)
    return result


def _consume_code(db, phone: str, code: str, scene: str) -> None:
    """校验并消费验证码；不通过直接抛 HTTPException"""
    if not code or not code.strip():
        raise HTTPException(status_code=400, detail="请输入验证码")
    record = db.scalar(
        select(SmsCode)
        .where(
            SmsCode.phone == phone,
            SmsCode.scene == scene,
            SmsCode.used.is_(False),
        )
        .order_by(SmsCode.id.desc())
        .limit(1)
    )
    if record is None:
        # 区分「没发过」和「发过但已用掉」，避免用户看到误导性提示
        used = db.scalar(
            select(SmsCode)
            .where(SmsCode.phone == phone, SmsCode.scene == scene)
            .order_by(SmsCode.id.desc())
            .limit(1)
        )
        if used is not None:
            raise HTTPException(status_code=400, detail="验证码已使用，请重新获取")
        raise HTTPException(status_code=400, detail="请先获取验证码")
    if datetime.now() > record.expires_at:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    if record.code != code.strip():
        raise HTTPException(status_code=400, detail="验证码不正确")
    record.used = True


# ----------------------------- 手机号登录 ----------------------------- #
@router.post("/login/phone", summary="手机号验证码登录（自动注册）")
def login_phone(payload: PhoneLoginIn) -> dict:
    _require_db()
    phone = normalize_phone(payload.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    with session_scope() as db:
        _consume_code(db, phone, payload.code, "login")

        ident = _find_identity(db, PROVIDER_PHONE, "", phone)
        if ident is not None:
            user = _load_user(db, ident.user_id)
        else:
            # 首次登录 = 注册
            user = User(
                id=uuid.uuid4().hex,
                nickname=_default_nickname(phone),
                phone=phone,
                register_from="phone",
            )
            db.add(user)
            db.flush()
            _upsert_identity(db, user, PROVIDER_PHONE, "", phone)

        user.phone = phone
        user.last_login_at = datetime.now()
        db.flush()
        return _issue(user)


# ----------------------------- 微信小程序登录 ----------------------------- #
def _code2session(code: str, app_id: str) -> dict:
    """用 code 换 openid / session_key / unionid"""
    secret = settings.wechat_miniapp_secret.strip()
    try:
        resp = requests.get(
            _WECHAT_CODE2SESSION,
            params={
                "appid": app_id,
                "secret": secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=_WECHAT_TIMEOUT,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("调用微信 code2Session 失败：%s", exc)
        raise HTTPException(status_code=502, detail="微信服务暂不可用，请稍后重试") from exc

    if not data.get("openid"):
        errcode = data.get("errcode")
        errmsg = data.get("errmsg", "未知错误")
        # 40029=code 无效；45011=频率限制；40226=高风险用户
        hint = {
            40029: "登录凭证已失效，请重试",
            45011: "操作过于频繁，请稍后再试",
            40226: "当前账号存在风险，已被限制登录",
        }.get(errcode, f"微信登录失败（{errcode}）：{errmsg}")
        raise HTTPException(status_code=401, detail=hint)
    return data


@router.post("/login/wechat", summary="微信小程序登录（wx.login 静默登录）")
def login_wechat(payload: WechatLoginIn) -> dict:
    _require_db()
    if not settings.wechat_login_ready:
        raise HTTPException(
            status_code=503,
            detail="微信小程序登录未配置（需 WECHAT_MINIAPP_APPID + WECHAT_MINIAPP_SECRET）",
        )

    app_id = (payload.appId or settings.wechat_miniapp_appid).strip()
    if app_id != settings.wechat_miniapp_appid.strip():
        # 防止拿着别家小程序的 code 来换本服务的登录态
        raise HTTPException(status_code=400, detail="AppID 与服务端配置不一致")

    data = _code2session(payload.code, app_id)
    openid = data["openid"]
    union_id = data.get("unionid", "") or ""
    session_key = data.get("session_key", "") or ""

    with session_scope() as db:
        ident = _find_identity(db, PROVIDER_WECHAT_MINIAPP, app_id, openid)
        if ident is not None:
            user = _load_user(db, ident.user_id)
        else:
            user = User(
                id=uuid.uuid4().hex,
                nickname="微信用户",
                register_from=PROVIDER_WECHAT_MINIAPP,
            )
            db.add(user)
            db.flush()
            try:
                _upsert_identity(
                    db,
                    user,
                    PROVIDER_WECHAT_MINIAPP,
                    app_id,
                    openid,
                    union_id,
                    session_key,
                )
                db.flush()
            except IntegrityError:
                # 并发同时首次登录：回滚本次插入，改用已存在的那条
                db.rollback()
                ident = _find_identity(db, PROVIDER_WECHAT_MINIAPP, app_id, openid)
                if ident is None:
                    raise
                user = _load_user(db, ident.user_id)

        if ident is not None and (union_id or session_key):
            _upsert_identity(
                db,
                user,
                PROVIDER_WECHAT_MINIAPP,
                app_id,
                openid,
                union_id,
                session_key,
            )
        user.last_login_at = datetime.now()
        db.flush()
        return _issue(user)


# ----------------------------- 绑定手机号 ----------------------------- #
@router.post("/bind/phone", summary="绑定手机号（可自动合并空账号）")
def bind_phone(
    payload: BindPhoneIn, user_id: str = Depends(get_current_user_id)
) -> dict:
    _require_db()
    phone = normalize_phone(payload.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    switched_user: User | None = None
    with session_scope() as db:
        _consume_code(db, phone, payload.code, "bind")
        user = _load_user(db, user_id)

        owner = _find_identity(db, PROVIDER_PHONE, "", phone)
        if owner is not None and owner.user_id != user.id:
            # 手机号已属于另一个账号 —— 典型场景：先用微信快捷登录建了账号，
            # 再想绑手机号，发现这个号早就注册过了（其实是同一个人）。
            # 只有**当前账号是个空壳**（除本次微信身份外没有任何登录方式、
            # 也没有任何对话记录）时才自动并入手机号账号；否则宁可报错，
            # 也不能悄悄吞掉用户的数据。
            target = _load_user(db, owner.user_id)
            my_idents = _identities_of(db, user.id)
            my_sessions = (
                db.scalar(
                    select(func.count())
                    .select_from(ChatSession)
                    .where(ChatSession.user_id == user.id)
                )
                or 0
            )
            is_empty = len(my_idents) <= 1 and my_sessions == 0
            if not (payload.autoMerge and is_empty):
                raise HTTPException(
                    status_code=409,
                    detail="该手机号已注册过账号，请改用手机号登录（当前账号有数据，未做自动合并）",
                )
            for ident in my_idents:
                ident.user_id = target.id
                ident.updated_at = datetime.now()
            _merge_sessions(db, user.id, target.id)
            db.delete(user)
            switched_user = target
        else:
            if owner is None:
                _upsert_identity(db, user, PROVIDER_PHONE, "", phone)
            user.phone = phone

        active = switched_user or user
        active.last_login_at = datetime.now()
        db.flush()
        result = _issue(active)
        result["switched"] = switched_user is not None
        return result


# ----------------------------- 游客数据合并 ----------------------------- #
def _merge_sessions(db, from_user_id: str, to_user_id: str) -> int:
    """把 from_user_id 名下的会话迁到 to_user_id，返回迁移条数。"""
    if not from_user_id or not to_user_id or from_user_id == to_user_id:
        return 0
    sessions = list(
        db.scalars(select(ChatSession).where(ChatSession.user_id == from_user_id))
    )
    for s in sessions:
        s.user_id = to_user_id
    return len(sessions)


@router.post("/merge-guest", summary="把游客历史合并到当前账号")
def merge_guest(payload: MergeGuestIn, user_id: str = Depends(get_current_user_id)) -> dict:
    _require_db()
    guest_id = (payload.guestId or "").strip()
    if not guest_id or guest_id == user_id:
        return {"ok": True, "moved": 0}
    # 只接受"游客空间"标识（default / guest-xxx），
    # 否则等于允许把任意账号的数据迁到自己名下
    if not is_guest_id(guest_id):
        logger.warning("拒绝合并非游客空间 guestId=%s", guest_id)
        raise HTTPException(status_code=400, detail="游客标识不合法")

    with session_scope() as db:
        _load_user(db, user_id)
        moved = _merge_sessions(db, guest_id, user_id)
    return {"ok": True, "moved": moved}


# ----------------------------- 账号信息 ----------------------------- #
@router.get("/me", summary="当前账号信息")
def me(user_id: str = Depends(get_current_user_id)) -> dict:
    _require_db()
    with session_scope() as db:
        user = _load_user(db, user_id)
        return _user_out(user, _identities_of(db, user.id))


@router.post("/profile", summary="修改资料（昵称/头像/性别/生日/签名/情感状态）")
def update_profile(
    payload: ProfileIn, user_id: str = Depends(get_current_user_id)
) -> dict:
    """只更新入参里**显式出现**的字段（None = 不改）。

    校验一律在服务端做：昵称长度、头像长度、性别/情感状态的枚举、
    生日格式 —— 前端可以绕过，服务端不能假设它是干净的。
    """
    _require_db()
    with session_scope() as db:
        user = _load_user(db, user_id)

        if payload.nickname is not None:
            name = payload.nickname.strip()
            if not name:
                raise HTTPException(status_code=400, detail="昵称不能为空")
            if len(name) > 24:
                raise HTTPException(status_code=400, detail="昵称最长 24 个字符")
            user.nickname = name

        if payload.avatar is not None:
            user.avatar = payload.avatar.strip()[:512]

        if payload.gender is not None:
            g = payload.gender.strip().lower()
            if g not in _GENDERS:
                raise HTTPException(status_code=400, detail="性别取值不合法")
            user.gender = g

        if payload.birthday is not None:
            b = payload.birthday.strip()
            if b and not _BIRTHDAY_RE.match(b):
                raise HTTPException(status_code=400, detail="生日格式应为 YYYY-MM-DD")
            if b:
                try:
                    datetime.strptime(b, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="生日不是有效日期") from None
                if b > datetime.now().strftime("%Y-%m-%d"):
                    raise HTTPException(status_code=400, detail="生日不能晚于今天")
            user.birthday = b

        if payload.bio is not None:
            bio = payload.bio.strip()
            if len(bio) > 60:
                raise HTTPException(status_code=400, detail="个性签名最长 60 个字符")
            user.bio = bio

        if payload.emotion_status is not None:
            s = payload.emotion_status.strip().lower()
            if s not in _EMOTIONS:
                raise HTTPException(status_code=400, detail="情感状态取值不合法")
            user.emotion_status = s

        db.flush()
        return _user_out(user, _identities_of(db, user.id))


@router.post("/logout", summary="退出登录")
def logout(user_id: str = Depends(get_current_user_id)) -> dict:
    """无状态登录态：服务端无需处理，前端清掉本地 token 即可。

    保留该接口是为了让前端有统一的调用口径（将来换成
    可撤销 token / 黑名单机制时前端无需改动）。
    """
    logger.info("用户退出登录：%s", user_id)
    return {"ok": True}


@router.get("/config", summary="前端登录能力开关（公开）")
def auth_config() -> dict:
    """前端进入登录页先拉一次，按返回结果决定展示哪些登录方式。"""
    return {
        "authEnabled": settings.auth_enabled,
        "smsDevMode": settings.sms_dev_mode,
        "smsInterval": settings.sms_send_interval,
        "smsCodeTtl": settings.sms_code_ttl,
        # 通道名与是否配齐：前端可据此把「点发送没反应」变成一句明确的提示，
        # 而不是让用户对着 502/503 猜。缺哪几项只在 /api/health/config 里给出。
        "smsProvider": settings.sms_provider,
        "smsReady": settings.sms_ready,
        "phoneLogin": True,
        "wechatMiniAppLogin": settings.wechat_login_ready,
        # 移动应用微信登录需企业主体 + 开放平台认证，服务端当前不提供
        "wechatAppLogin": False,
        "guestMerge": True,
    }
