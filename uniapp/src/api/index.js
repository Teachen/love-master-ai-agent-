/**
 * 业务接口封装（普通 HTTP；SSE 流式接口见 src/utils/sse.js）
 */

import http from './http'
import { API } from '@/config'

/**
 * 健康检查
 * @param {number} [timeout] 单次超时（毫秒）。不传则用 http 默认 20s。
 *   云托管冷启动较慢，App 启动探测建议传 30000。
 */
export function checkHealth(timeout) {
  return http.get(API.health, timeout ? { timeout } : {})
}

/** RAG 数据源诊断 */
export function getRagBackend(check = false) {
  return http.get(API.ragBackend, { params: { check } })
}

/**
 * 对话记录导出 PDF（前端回传全文；MySQL 不可用时用它兜底）
 * @param {{title?:string, chatId?:string, messages: Array<{role:string,content:string,time?:string}>}} payload
 * @returns {Promise<{ok:boolean, url:string, filename:string}>}
 */
export function exportChatPdf(payload) {
  return http.post(API.chatExportPdf, payload)
}

/* ------------------ 对话历史（MySQL 持久化） ------------------ */
// 后端未启用 MySQL 时：读接口返回 {available:false}，写接口返回 503，
// 调用方据此回退本地存储 —— 见 utils/chatStore.js
//
// 归属规则：请求头带登录态时后端以账号为准（忽略 user_id）；
//          未登录则按 user_id 落到游客空间。这里统一带上游客 ID，
//          登录后自动失效，不需要分支判断。

import { getGuestId } from '@/utils/authStore'

const _enc = (id) => encodeURIComponent(id)

/** 历史列表；返回 {available, items} */
export function fetchHistoryList(params = {}) {
  return http.get(API.history, { params: { user_id: getGuestId(), ...params } })
}

/** 历史详情（含 messages）；返回 {available, messages} */
export function fetchHistorySession(id) {
  return http.get(`${API.history}/${_enc(id)}`, { params: { user_id: getGuestId() } })
}

/** 整段保存（upsert）；登录态下 user_id 由后端以 token 为准 */
export function saveHistorySession(id, data) {
  return http.put(`${API.history}/${_enc(id)}`, { ...data, user_id: getGuestId() })
}

/** 删除单条 */
export function deleteHistorySession(id) {
  return http.delete(`${API.history}/${_enc(id)}`, { params: { user_id: getGuestId() } })
}

/** 清空全部 */
export function clearHistoryRemote(userId = '') {
  return http.delete(API.history, { params: { user_id: userId || getGuestId() } })
}

/** 按库里的记录导出 PDF（推荐；前端无需回传全文） */
export function exportHistoryPdf(id) {
  return http.post(`${API.history}/${_enc(id)}/export-pdf`, null, {
    params: { user_id: getGuestId() },
  })
}

/* ------------------ 账号体系 ------------------ */
export * from './auth'
