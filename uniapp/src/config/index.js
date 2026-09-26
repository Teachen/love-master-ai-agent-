/**
 * 全局配置：后端地址
 *
 * 地址来源优先级：
 *   1. 运行时设置（「我的 → 服务器地址」里修改，存本地存储）
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
 * 后端站点根（origin）：从当前生效地址里提取 http(s)://host[:port] 部分。
 *
 * 用途：下载后端返回的「绝对路径」文件（如 /api/files/xxx.pdf）。
 * 不能直接用 getServerBase() 拼 —— 它带 /api 前缀，会拼成 /api/api/... 导致 404。
 * 小程序端没有 URL 构造器，用正则手动提取。
 */
export function getServerOrigin() {
  const base = getServerBase()
  const m = base.match(/^(https?:\/\/[^/]+)/i)
  return m ? m[1] : ''
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

// 应用标题（来自 .env.<mode> 的 VITE_APP_TITLE）
// 用法：首页/登录页的标题直接绑它 —— 预发构建会显示「恋爱大师（预发）」，
//      一眼就能看出当前跑的是哪个环境，不用去猜。
export const APP_TITLE = import.meta.env.VITE_APP_TITLE || '恋爱大师'

// 当前构建模式（Vite 的 mode）：development / staging / e2e / production
export const ENV_MODE = import.meta.env.MODE || 'development'

/** 模式 → 中文标签，用于界面上的环境角标 */
export const ENV_LABEL = {
  development: '本地开发',
  staging: '预发环境',
  e2e: '端到端测试',
  production: '生产环境',
}[ENV_MODE] || ENV_MODE

/** 是否生产构建（.env.production） */
export const IS_PROD = ENV_MODE === 'production'

/** 当前是否开发环境（用于页面上的调试提示，生产不展示） */
export const IS_DEV = !IS_PROD

/* ------------------------------------------------------------------ *
 * ICP 备案信息
 *
 * 境内运营需要在显著位置标注备案号并链接工信部，配置项走环境变量
 * （不同环境/主体可能不同），未配置时用占位文案，界面照常显示，
 * 这样上线前一眼能看出「这里还没填真号」。
 *
 * 填写位置：uniapp/.env.<mode>
 *   VITE_BEIAN_ICP=闽ICP备2022001906号          （本项目实际备案号）
 *   VITE_BEIAN_OWNER=公司/主体全称        （可选，显示在备案号前面）
 *   VITE_BEIAN_POLICE=闽公网安备35010002000000号  （可选，公安备案）
 * ------------------------------------------------------------------ */
const BEIAN_ICP_ENV = import.meta.env.VITE_BEIAN_ICP || ''
/**
 * 占位用的示例号（明显不可能是真的）。
 * 值等于它说明还没换成真实备案号 —— 只作为「忘记替换」的哨兵，
 * 不要把它写成真实号码，否则 isPlaceholder 会永远为 true。
 */
const BEIAN_ICP_SAMPLE = '闽ICP备0000000000号-0'

export const BEIAN = {
  /** 网站备案号，如「闽ICP备2022001906号」 */
  icp: BEIAN_ICP_ENV || '备案号待配置',
  /** 备案主体名称（公司/个人全称），可选 */
  owner: import.meta.env.VITE_BEIAN_OWNER || '',
  /** 公安备案号，可选 */
  police: import.meta.env.VITE_BEIAN_POLICE || '',
  /** 工信部备案管理系统 */
  url: 'https://beian.miit.gov.cn',
  /** 是否仍是占位值（没配，或还是示例号）—— 上线前必须为 false */
  isPlaceholder: !BEIAN_ICP_ENV || BEIAN_ICP_ENV === BEIAN_ICP_SAMPLE,
}

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
  // 对话记录导出 PDF（POST，前端回传全文）
  chatExportPdf: '/ai/chat/export-pdf',
  // 对话历史（MySQL 持久化）；未启用时前端回退本地存储
  history: '/history',

  // ---------- 账号体系（对应 app/api/auth.py） ----------
  // 能力开关：返回是否支持手机号/小程序登录、是否开发模式短信等
  authConfig: '/auth/config',
  // 发送短信验证码（开发模式会回显 devCode）
  authSmsSend: '/auth/sms/send',
  // 手机号 + 验证码登录（未注册自动注册）
  authLoginPhone: '/auth/login/phone',
  // 微信小程序 wx.login 静默登录（后端换 openid）
  authLoginWechat: '/auth/login/wechat',
  // 给当前账号绑定手机号（冲突时可自动合并空账号）
  authBindPhone: '/auth/bind/phone',
  // 把游客时期的对话历史迁到当前账号
  authMergeGuest: '/auth/merge-guest',
  // 当前账号信息 / 改资料 / 退出
  authMe: '/auth/me',
  authProfile: '/auth/profile',
  authLogout: '/auth/logout',
}

// 页面路径（统一收敛，避免各处硬编码字符串写错）
export const PAGE = {
  // 三个底部 tab 页：只能用 switchTab / reLaunch 跳转，navigateTo 会失败
  index: '/pages/index/index',
  apps: '/pages/apps/apps',
  mine: '/pages/mine/mine',
  // 普通页面：navigateTo
  login: '/pages/login/login',
  history: '/pages/history/history',
  love: '/pages/love/love',
  manus: '/pages/manus/manus',
  profile: '/pages/profile/profile',
}

/** 底部 tab 页路径集合（判断跳转方式用） */
export const TAB_PAGES = [PAGE.index, PAGE.apps, PAGE.mine]

/**
 * 统一跳转：自动区分 tab 页（switchTab）与普通页（navigateTo）。
 * 直接写 navigateTo 跳 tab 页在微信小程序会静默失败，很难排查，所以收口到这里。
 */
export function goPage(path) {
  if (TAB_PAGES.indexOf(path) >= 0) {
    uni.switchTab({ url: path })
    return
  }
  uni.navigateTo({
    url: path,
    fail: () => uni.showToast({ title: '打开失败', icon: 'none' }),
  })
}
