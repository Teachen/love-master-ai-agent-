/**
 * 业务接口封装（普通 HTTP；SSE 流式接口见 src/utils/sse.js）
 */

import http from './http'
import { API } from '@/config'

/** 健康检查 */
export function checkHealth() {
  return http.get(API.health)
}

/** RAG 数据源诊断 */
export function getRagBackend(check = false) {
  return http.get(API.ragBackend, { params: { check } })
}
