/**
 * 全局配置：后端地址
 *
 * 地址来源优先级：
 *   1. 运行时设置（App 内首页右上角 ⚙ 修改，存本地存储）
 *   2. 环境变量（.env.development / .env.production 里的 VITE_* 变量）
 *   3. 下面的兜底默认值（本地开发用）
 *
 * ⚠️ 读取地址请统一调用 getServerBase()，不要缓存返回值 ——
 *    它在每次请求时动态求值，因此 App 内改完地址可以立即生效、无需重启。
 *
 * 注意：Vite 只会静态替换 `import.meta.env.VITE_XXX` 这种「直接成员访问」，
 *       因此不要写成 `const e = import.meta.env; e.VITE_XXX`，那样三端会取不到值。
 *
 * 三端说明：
 * - H5：后端已开启 CORS（cors_origins=["*"]），可直接用完整地址；
 *       生产环境可改用相对路径 '/api' 走 nginx 反向代理。
 * - 微信小程序：开发工具里勾「不校验合法域名」后可用 localhost；
 *       真机调试需把 localhost 换成电脑局域网 IP（如 http://192.168.x.x:8000）。
 * - App：localhost 指手机自身，必须用局域网 IP 或正式域名。
 */

// 兜底默认值（未配置 .env 时使用）
const DEFAULT_BASE_URL = 'http://localhost:8000/api'

// 编译期默认地址（来自 .env，构建时静态注入）
const ENV_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE_URL).replace(/\/+$/, '')

/* ------------------------------------------------------------------ *
 * 运行时可覆盖的服务器地址
 *
 * 背景：打包成 App 后 localhost 指向「手机自身」，必须填电脑局域网 IP；
 *       而电脑 IP 会随路由器重新分配变化，若写死在 .env 里，每次变动都要
 *       重新云打包，成本极高。
 * 方案：允许在 App 内修改并存本地存储，运行时优先读存储值。
 * ------------------------------------------------------------------ */
const STORAGE_KEY = 'LM_SERVER_BASE'

/** 规范化地址：去空白、去结尾斜杠 */
function normalizeUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '')
}

/** 读取当前生效的后端地址（本地存储覆盖值 > .env 默认值） */
export function getServerBase() {
  try {
    const saved = uni.getStorageSync(STORAGE_KEY)
    if (saved) return normalizeUrl(saved)
  } catch (e) {
    // 存储不可用时静默回退到默认值
  }
  return ENV_BASE_URL
}

/**
 * 保存自定义后端地址；传空字符串则恢复默认
 * @returns {string} 保存后实际生效的地址
 */
export function setServerBase(url) {
  const v = normalizeUrl(url)
  try {
    if (!v) uni.removeStorageSync(STORAGE_KEY)
    else uni.setStorageSync(STORAGE_KEY, v)
  } catch (e) {
    // 忽略存储异常
  }
  return getServerBase()
}

/** 编译期默认地址（只读，供界面展示「默认值」） */
export const DEFAULT_SERVER_BASE = ENV_BASE_URL

/** 当前地址是否是用户自定义的（非默认） */
export function isCustomServer() {
  try {
    return !!uni.getStorageSync(STORAGE_KEY)
  } catch (e) {
    return false
  }
}

// 应用标题
export const APP_TITLE = import.meta.env.VITE_APP_TITLE || '恋爱大师'

// 当前是否开发环境（用于页面上的调试提示，可关闭）
export const IS_DEV = import.meta.env.MODE !== 'production'

// 后端接口路径（对应 Java 版 AiController / Python 版 app/api/ai.py）
export const API = {
  // 恋爱大师 SSE 流式对话
  loveChatSse: '/ai/love_app/chat/sse',
  // 超级智能体 SSE 流式推理
  manusChat: '/ai/manus/chat',
  // 健康检查
  health: '/health',
  // RAG 数据源诊断
  ragBackend: '/knowledge/backend',
}
