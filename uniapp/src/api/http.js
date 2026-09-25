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

// 小程序端用适配器替换默认 XHR adapter
let adapter
// #ifdef MP-WEIXIN
import mpAdapter from 'axios-miniprogram-adapter'
adapter = mpAdapter
// #endif

const service = axios.create({
  timeout: 20000,
  adapter,
})

// 请求拦截：统一打印（可按需加 token）
service.interceptors.request.use(
  (config) => {
    // 每次请求都重新读取，App 内改了服务器地址可立即生效，无需重启
    config.baseURL = getServerBase()
    // const token = uni.getStorageSync('token')
    // if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一错误提示
service.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg =
      (error.response && error.response.data && error.response.data.detail) ||
      error.message ||
      '网络异常'
    console.error('[HTTP] 请求失败：', msg)
    return Promise.reject(new Error(typeof msg === 'string' ? msg : '请求失败'))
  }
)

export default service
