/**
 * 对话导出 PDF（共享逻辑）
 *
 * 原先这段逻辑内联在「对话历史」页里。现在首页的会话列表长按也要能导出，
 * 抽成公用模块避免两份实现各自漂移。
 *
 * 流程：
 *   1. 优先调「按 sessionId 从库里取」的接口（前端不用回传整段对话）
 *   2. 后端未启用 MySQL 时，回退到「前端回传全文」的接口（本地存储数据）
 *   3. 拿到 /api/files/xxx.pdf 这类绝对路径 → 用「站点根 origin」拼完整地址
 *      （base 自带 /api 前缀，直接拼会变成 /api/api/... 导致 404）
 *   4. H5 走 fetch+blob 真正落盘；App / 小程序走 downloadFile + openDocument
 */
import { exportChatPdf, exportHistoryPdf } from '@/api'
import { getServerOrigin } from '@/config'
import { loadSessionAsync } from '@/utils/chatStore'

/**
 * 导出某个会话为 PDF
 * @param {{id:string,title?:string}} item 会话索引项
 * @returns {Promise<boolean>} 是否成功
 */
export async function exportSessionPdf(item) {
  if (!item || !item.id) return false
  uni.showLoading({ title: '正在生成 PDF...', mask: true })

  try {
    let res = null
    try {
      res = await exportHistoryPdf(item.id)
    } catch (e) {
      res = null // 未启用 MySQL 时会 503，落到下面的回传全文方案
    }

    if (!res || res.ok === false) {
      const session = await loadSessionAsync(item.id)
      if (!session || !session.messages || session.messages.length === 0) {
        uni.hideLoading()
        uni.showToast({ title: '该会话没有可导出的内容', icon: 'none' })
        return false
      }
      res = await exportChatPdf({
        title: session.title || item.title || '对话记录',
        chatId: item.id,
        messages: session.messages,
      })
    }

    uni.hideLoading()

    if (!res || res.ok === false) {
      uni.showToast({ title: (res && res.detail) || '导出失败', icon: 'none' })
      return false
    }

    const fileUrl = getServerOrigin() + res.url

    // #ifdef H5
    // H5：跨域 <a download> 的 download 属性会被浏览器忽略并直接导航，
    // 所以先 fetch 成 blob，再走同源 objectURL 下载（真正落盘而不是打开预览）
    const resp = await fetch(fileUrl)
    if (!resp.ok) {
      uni.showToast({ title: `下载失败（HTTP ${resp.status}）`, icon: 'none' })
      return false
    }
    const blob = await resp.blob()
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = res.filename || '对话记录.pdf'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(objUrl)
    // #endif

    // #ifndef H5
    // App / 小程序：先下载到临时文件，再用系统能力打开
    uni.downloadFile({
      url: fileUrl,
      success: (r) => {
        uni.openDocument({
          filePath: r.tempFilePath,
          fileType: 'pdf',
          success: () => {},
          fail: () => uni.showToast({ title: '打开失败，文件已下载', icon: 'none' }),
        })
      },
      fail: () => uni.showToast({ title: '下载失败', icon: 'none' }),
    })
    // #endif

    uni.showToast({ title: '导出成功', icon: 'none' })
    return true
  } catch (e) {
    uni.hideLoading()
    uni.showToast({
      title: (e && e.message) || '导出失败，请确认后端可用',
      icon: 'none',
    })
    return false
  }
}

/**
 * 会话时间显示（微信式）：今天显示时刻、昨天显示「昨天」、
 * 一周内显示星期几、更早显示日期。
 */
export function formatChatTime(stamp) {
  if (!stamp) return ''
  const m = String(stamp).match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  if (!m) return String(stamp)
  const y = +m[1]
  const mo = +m[2]
  const d = +m[3]
  const hh = m[4]
  const mm = m[5]

  const now = new Date()
  const dayStart = (dt) => new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime()
  const diffDays = Math.round((dayStart(now) - dayStart(new Date(y, mo - 1, d))) / 86400000)

  if (diffDays <= 0) return `${hh}:${mm}`
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) {
    return ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][
      new Date(y, mo - 1, d).getDay()
    ]
  }
  return `${y}/${mo}/${d}`
}
