/**
 * 基于 Axios 的 HTTP 请求封装（对应需求技术选型：Axios 请求库）
 *
 * 跨端适配：
 * - H5 / App：axios 默认走 XHR，可直接用；
 * - 微信小程序：无 XHR，需 axios-miniprogram-adapter 把 wx.request 适配成 axios。
 *
 * 注意：SSE 流式接口不走这里（axios 不支持流式），见 src/utils/sse.js。
 */

import axios from 'axios'
import { getServerBase } from '@/config'
import { clearSession, getToken } from '@/utils/authStore'

// 小程序端用适配器替换默认 XHR adapter
let adapter
// #ifdef MP-WEIXIN
import mpAdapter from 'axios-miniprogram-adapter'
adapter = mpAdapter
// #endif

// #ifdef APP-PLUS
/**
 * App 端适配器（uni-app 编译到 App 后，业务 JS 运行在独立逻辑层 V8/JSCore，
 * 没有 XMLHttpRequest / fetch / EventSource，axios 默认 XHR adapter 会直接报
 * "XMLHttpRequest is not defined"，因此用 uni.request 实现 axios adapter 协议）
 */
function uniRequestAdapter(config) {
  return new Promise((resolve, reject) => {
    // axios 的 adapter 收到的 url 是相对路径，需要自己拼 baseURL
    let fullUrl = config.url || ''
    if (config.baseURL && !/^https?:\/\//i.test(fullUrl)) {
      fullUrl = `${config.baseURL.replace(/\/+$/, '')}/${fullUrl.replace(/^\/+/, '')}`
    }
    // params 序列化（与 axios 行为一致）
    const params = config.params
    if (params && typeof params === 'object') {
      const qs = Object.keys(params)
        .filter((k) => params[k] !== undefined && params[k] !== null)
        .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
        .join('&')
      if (qs) fullUrl += (fullUrl.includes('?') ? '&' : '?') + qs
    }

    // AxiosHeaders 需转成普通对象交给 uni.request
    const rawHeaders = config.headers
    const header =
      rawHeaders && typeof rawHeaders.toJSON === 'function'
        ? rawHeaders.toJSON()
        : rawHeaders || {}

    uni.request({
      url: fullUrl,
      method: (config.method || 'get').toUpperCase(),
      data: config.data,
      header,
      timeout: config.timeout || 20000,
      success: (res) => {
        const response = {
          data: res.data,
          status: res.statusCode,
          statusText: String(res.statusCode),
          headers: res.header || {},
          config,
          request: res,
        }
        const validate =
          config.validateStatus || ((status) => status >= 200 && status < 300)
        if (validate(res.statusCode)) {
          resolve(response)
        } else {
          // 带 response 的错误，保证响应拦截器能拿到 error.response.data.detail
          const error = new Error(`Request failed with status code ${res.statusCode}`)
          error.config = config
          error.response = response
          reject(error)
        }
      },
      fail: (err) => {
        const error = new Error((err && err.errMsg) || '网络请求失败')
        error.config = config
        reject(error)
      },
    })
  })
}
adapter = uniRequestAdapter
// #endif

const service = axios.create({
  timeout: 20000,
  adapter,
})

// 请求拦截：统一注入后端地址与登录态
service.interceptors.request.use(
  (config) => {
    // 每次请求都重新读取，App 内改了服务器地址可立即生效，无需重启
    config.baseURL = getServerBase()
    // 登录态统一注入，业务代码不用管；未登录时不带该头，后端按游客处理
    const token = getToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一错误提示；登录态失效时清本地并广播事件
service.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const res = error.response
    const status = (res && res.status) || 0
    const msg =
      (res && res.data && res.data.detail) || error.message || '网络异常'

    // 401 且本次请求确实带了登录态 → 说明 token 过期/被撤销：
    // 清掉本地登录态并广播，页面可据此提示重新登录。
    // 注意：登录接口本身返回 401（如 code 无效）时请求没带 token，不会误伤。
    const sentToken = !!(error.config && error.config.headers && error.config.headers.Authorization)
    if (sentToken && res && res.status === 401) {
      clearSession()
      try {
        uni.$emit('auth:expired', { detail: msg })
      } catch (e) {
        /* 非 uni 环境忽略 */
      }
    }

    console.error('[HTTP] 请求失败：', status || '-', msg)
    // 把 HTTP 状态码带出去：调用方需要区分「404 后端没这个路由」与
    // 「503 后端在但没就绪」—— 两者以前都只是一句文案，无法判断真实原因。
    const wrapped = new Error(typeof msg === 'string' ? msg : '请求失败')
    wrapped.status = status
    wrapped.url = (error.config && error.config.url) || ''
    return Promise.reject(wrapped)
  }
)

export default service
