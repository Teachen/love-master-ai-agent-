/**
 * 会话持久化存储层
 *
 * 解决的问题：从对话页返回上一页再进来，消息全没了（原实现每次 onLoad 都新建会话 ID，
 * 且消息只存在于组件内存）。
 *
 * 存储策略：**后端（MySQL）优先 + 本地兜底**
 * - 后端可用（MYSQL_ENABLED=true 且连得上）时，历史以数据库为准，可跨设备、容器重启不丢
 * - 后端不可用（本地开发没装 MySQL / 服务未启动）时，完全回退本地存储，功能不受影响
 *
 * 本地存储结构（uni.getStorageSync，三端一致）：
 *   LM_CHAT_INDEX  -> [{ id, title, theme, updatedAt, preview, msgCount }]  会话列表（倒序）
 *   LM_CHAT_<id>   -> { id, title, theme, createdAt, updatedAt, messages: [...] }
 */
const INDEX_KEY = 'LM_CHAT_INDEX'
const SESSION_PREFIX = 'LM_CHAT_'

/** 列表最大保留条数，超出后淘汰最旧的 */
const MAX_SESSIONS = 50

/* ================================================================== *
 * 远程（MySQL）能力探测与同步
 *
 * remoteOk 三态：null 未探测 / true 后端可用 / false 不可用
 * 只在首次使用时探测一次；失败后所有远程调用静默跳过，走本地。
 * ================================================================== */
import {
  fetchHistoryList,
  fetchHistorySession,
  saveHistorySession,
  deleteHistorySession,
  clearHistoryRemote,
} from '@/api'

let remoteOk = null

/** 探测后端历史存储是否可用（结果缓存） */
export async function probeRemote() {
  if (remoteOk !== null) return remoteOk
  try {
    const res = await fetchHistoryList({ limit: 1 })
    remoteOk = !!(res && res.available)
  } catch (e) {
    // 503（未启用）或网络异常都视为不可用
    remoteOk = false
  }
  return remoteOk
}

/** 当前远程是否可用（未探测时返回 false，不阻塞调用方） */
export function isRemoteOk() {
  return remoteOk === true
}

/** 把一条会话同步到后端（失败静默，不影响本地） */
export async function syncSessionRemote(session) {
  if (!(await probeRemote())) return false
  try {
    await saveHistorySession(session.id, {
      title: session.title || makeTitle(session.messages),
      theme: session.theme || 'love',
      updatedAt: session.updatedAt || nowStamp(),
      messages: (session.messages || []).map((m) => ({
        role: m.role,
        content: m.content || '',
        time: m.time || '',
      })),
    })
    return true
  } catch (e) {
    return false
  }
}

/** 拉取历史列表：远程优先，失败回退本地 */
export async function loadIndexAsync() {
  if (await probeRemote()) {
    try {
      const res = await fetchHistoryList({ limit: MAX_SESSIONS })
      if (res && res.available && Array.isArray(res.items)) {
        return res.items.map((it) => ({
          id: it.id,
          title: it.title,
          theme: it.theme,
          updatedAt: it.updatedAt,
          preview: it.preview || '',
          msgCount: it.msgCount || 0,
        }))
      }
    } catch (e) {
      /* 落到本地 */
    }
  }
  return loadIndex()
}

/** 拉取会话详情：远程优先，失败回退本地 */
export async function loadSessionAsync(id) {
  if (id && (await probeRemote())) {
    try {
      const res = await fetchHistorySession(id)
      if (res && res.available && Array.isArray(res.messages)) {
        return {
          id,
          title: res.title,
          theme: res.theme,
          createdAt: res.createdAt,
          updatedAt: res.updatedAt,
          messages: res.messages,
        }
      }
    } catch (e) {
      /* 落到本地 */
    }
  }
  return loadSession(id)
}

/** 删除：远程 + 本地都删（任一侧失败不影响另一侧） */
export async function removeSessionAsync(id) {
  if (await probeRemote()) {
    try {
      await deleteHistorySession(id)
    } catch (e) {
      /* ignore */
    }
  }
  return removeSession(id)
}

/** 清空：远程 + 本地 */
export async function clearAllSessionsAsync() {
  if (await probeRemote()) {
    try {
      await clearHistoryRemote()
    } catch (e) {
      /* ignore */
    }
  }
  clearAllSessions()
}

function nowStamp() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(
    d.getMinutes()
  )}`
}

/** 读取会话列表（倒序：最近更新的在前） */
export function loadIndex() {
  try {
    const list = uni.getStorageSync(INDEX_KEY)
    return Array.isArray(list) ? list : []
  } catch (e) {
    return []
  }
}

function saveIndex(list) {
  try {
    uni.setStorageSync(INDEX_KEY, list)
  } catch (e) {
    /* 存储满或不可用时静默失败，不影响对话 */
  }
}

/** 读取单个会话；不存在返回 null */
export function loadSession(id) {
  if (!id) return null
  try {
    const s = uni.getStorageSync(SESSION_PREFIX + id)
    return s && typeof s === 'object' ? s : null
  } catch (e) {
    return null
  }
}

/** 从消息列表生成标题：取第一条用户消息前 22 字 */
export function makeTitle(messages, fallback = '新对话') {
  const first = (messages || []).find((m) => m.role === 'user' && m.content)
  if (!first) return fallback
  const t = String(first.content).replace(/\s+/g, ' ').trim()
  return t.length > 22 ? t.slice(0, 22) + '…' : t || fallback
}

/** 从最后一条消息生成预览 */
export function makePreview(messages) {
  const list = (messages || []).filter((m) => m.content)
  if (!list.length) return ''
  const last = list[list.length - 1]
  const prefix = last.role === 'user' ? '我：' : 'AI：'
  const t = String(last.content).replace(/\s+/g, ' ').trim()
  return prefix + (t.length > 40 ? t.slice(0, 40) + '…' : t)
}

/**
 * 保存（新增 / 更新）一条会话，并同步列表索引
 * @param {{id:string,title?:string,theme?:string,messages:Array}} session
 * @returns {Array} 最新列表
 */
export function saveSession(session) {
  if (!session || !session.id) return loadIndex()
  const messages = session.messages || []
  const old = loadSession(session.id)
  const record = {
    id: session.id,
    theme: session.theme || (old && old.theme) || 'love',
    title: session.title || makeTitle(messages, (old && old.title) || '新对话'),
    createdAt: (old && old.createdAt) || nowStamp(),
    updatedAt: nowStamp(),
    messages: messages.map((m) => ({
      role: m.role,
      content: m.content || '',
      time: m.time || '',
    })),
  }

  try {
    uni.setStorageSync(SESSION_PREFIX + record.id, record)
  } catch (e) {
    // 存储写入失败（配额满）：淘汰最旧会话后重试一次
    const list = loadIndex()
    if (list.length) {
      removeSession(list[list.length - 1].id)
      try {
        uni.setStorageSync(SESSION_PREFIX + record.id, record)
      } catch (e2) {
        return loadIndex()
      }
    }
  }

  // 更新索引
  let list = loadIndex().filter((it) => it.id !== record.id)
  list.unshift({
    id: record.id,
    title: record.title,
    theme: record.theme,
    updatedAt: record.updatedAt,
    preview: makePreview(messages),
    msgCount: messages.filter((m) => m.role === 'user').length,
  })
  if (list.length > MAX_SESSIONS) {
    for (const dropped of list.slice(MAX_SESSIONS)) removeSession(dropped.id)
    list = list.slice(0, MAX_SESSIONS)
  }
  saveIndex(list)
  // 本地已存好，再异步同步到后端（不阻塞 UI；后端不可用时会静默跳过）
  syncSessionRemote(record)
  return list
}

/** 删除一条会话 */
export function removeSession(id) {
  if (!id) return loadIndex()
  try {
    uni.removeStorageSync(SESSION_PREFIX + id)
  } catch (e) {
    /* ignore */
  }
  const list = loadIndex().filter((it) => it.id !== id)
  saveIndex(list)
  return list
}

/** 清空全部会话 */
export function clearAllSessions() {
  for (const it of loadIndex()) {
    try {
      uni.removeStorageSync(SESSION_PREFIX + it.id)
    } catch (e) {
      /* ignore */
    }
  }
  saveIndex([])
}

/** 取该主题下最近一条会话（用于「进入页面自动恢复上次对话」） */
export function latestSessionId(theme) {
  const list = loadIndex()
  const hit = list.find((it) => !theme || it.theme === theme)
  return hit ? hit.id : ''
}
