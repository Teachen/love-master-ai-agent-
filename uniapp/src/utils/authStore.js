/**
 * 登录态与游客身份管理
 *
 * 两类身份：
 * 1. 登录用户（token 来自后端，HS256 JWT）—— 对话历史存到账号名下，跨设备同步
 * 2. 游客（本机 guest 空间）—— 不登录也能用，数据只在本机对应的空间里，
 *    登录时由 mergeGuestData() 迁到账号名下，避免"一登录历史就没了"
 *
 * 为什么游客空间要按设备生成而不是共用一个 "default"？
 *    旧实现里所有游客都写 "default"，两台设备会互相看到对方的对话。
 *    现在首次运行生成 guest-<随机>，实现一设备一空间；
 *    同时用 LM_GUEST_LEGACY 标记"本机可能有写在 default 里的老数据"，
 *    首次登录时一并合并过去。
 */
import { reactive } from 'vue'

const TOKEN_KEY = 'LM_AUTH_TOKEN'
const USER_KEY = 'LM_AUTH_USER'
const GUEST_KEY = 'LM_GUEST_ID'
const LEGACY_KEY = 'LM_GUEST_LEGACY'

const LEGACY_GUEST_ID = 'default'

/* ----------------------------- 存储读写 ----------------------------- */
function read(key, def) {
  try {
    const v = uni.getStorageSync(key)
    return v === '' || v === undefined || v === null ? def : v
  } catch (e) {
    return def
  }
}

function write(key, val) {
  try {
    uni.setStorageSync(key, val)
  } catch (e) {
    /* 存储不可用时静默降级，不影响主流程 */
  }
}

function drop(key) {
  try {
    uni.removeStorageSync(key)
  } catch (e) {
    /* ignore */
  }
}

function randomHex(len) {
  let s = ''
  const chars = '0123456789abcdef'
  for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * 16)]
  return s
}

/* ----------------------------- 登录态 ----------------------------- */
/** 响应式登录态：页面可直接绑定，登录/退出后自动刷新 */
export const authState = reactive({
  token: read(TOKEN_KEY, ''),
  user: read(USER_KEY, null),
})

export function getToken() {
  return authState.token
}

export function isLoggedIn() {
  return !!authState.token
}

export function getUser() {
  return authState.user
}

/**
 * 写入登录态
 * @param {{token?:string, user?:object}|null} payload 传 null 表示清除
 */
export function setSession(payload) {
  const token = (payload && payload.token) || ''
  const user = (payload && payload.user) || null
  authState.token = token
  authState.user = user
  if (token) write(TOKEN_KEY, token)
  else drop(TOKEN_KEY)
  if (user) write(USER_KEY, user)
  else drop(USER_KEY)
}

/** 退出登录（清本地登录态，不动游客数据） */
export function clearSession() {
  setSession(null)
}

/** 更新用户资料（改昵称/头像后同步本地缓存） */
export function updateUser(user) {
  authState.user = user || null
  if (user) write(USER_KEY, user)
  else drop(USER_KEY)
}

/** 展示名：昵称 > 脱敏手机号 > 兜底 */
export function displayName() {
  const u = authState.user
  if (!u) return '未登录'
  return u.nickname || u.phone || '已登录'
}

/* ----------------------------- 游客空间 ----------------------------- */
/**
 * 当前设备的游客空间 ID。
 * 首次调用会生成并持久化，保证同一台设备多次启动拿到同一个空间。
 */
export function getGuestId() {
  let g = ''
  try {
    g = uni.getStorageSync(GUEST_KEY) || ''
  } catch (e) {
    g = ''
  }
  if (!g) {
    g = 'guest-' + randomHex(16)
    write(GUEST_KEY, g)
    // 本机首次启用新版本：老数据可能写在 default 空间，标记一次待合并
    write(LEGACY_KEY, 1)
    console.log('[authStore] 生成新的游客空间:', g)
  }
  return g
}

/**
 * 登录后需要合并的游客空间列表。
 * @returns {string[]} 例如 ['default', 'guest-3f2a...']
 *
 * ⚠️ 必须先调用 getGuestId() 再读 LEGACY_KEY：
 *    首次运行时 LEGACY_KEY 是在 getGuestId() 内部写入的，
 *    顺序反了会让 "default" 这个历史空间被漏掉、游客数据迁不过去。
 */
export function guestSpacesToMerge() {
  const cur = getGuestId()
  const list = []
  if (read(LEGACY_KEY, 0)) list.push(LEGACY_GUEST_ID)
  if (cur && list.indexOf(cur) === -1) list.push(cur)
  return list
}

/** 合并成功后清掉标记，避免每次登录都重复请求 */
export function clearLegacyFlag() {
  drop(LEGACY_KEY)
}

/* ----------------------------- 微信登录能力 ----------------------------- */
/** 当前平台是否可能支持微信一键登录（App 端移动应用微信登录需企业主体，暂不支持） */
export function wechatLoginSupported() {
  let ok = false
  // #ifdef MP-WEIXIN
  ok = true
  // #endif
  return ok
}

/* ----------------------------- 展示工具 ----------------------------- */
/** 登录方式中文名 */
export function providerLabel(provider) {
  const map = {
    phone: '手机号',
    wechat_miniapp: '微信小程序',
    wechat_app: '微信 App',
    wechat_mp: '微信公众号',
  }
  return map[provider] || provider
}

/** 手机号脱敏展示（后端已脱敏，这里兜底） */
export function maskPhone(phone) {
  const p = String(phone || '')
  return p.length === 11 ? `${p.slice(0, 3)}****${p.slice(-4)}` : p
}
