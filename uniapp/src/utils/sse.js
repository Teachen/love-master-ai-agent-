/**
 * 跨端 SSE（Server-Sent Events）封装
 *
 * 为什么不能用 axios：axios 面向「一次性响应」，不支持 SSE 的持久流式推送。
 * 三端机制差异很大，因此用条件编译分别实现：
 *
 * ┌──────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 平台      │ 实现方式                     │ 说明                         │
 * ├──────────┼─────────────────────────────┼─────────────────────────────┤
 * │ H5        │ 原生 EventSource            │ 浏览器自带，自动解析事件帧    │
 * │ App       │ 原生 EventSource            │ 运行在内置 WebView，同 H5     │
 * │ 微信小程序 │ uni.request enableChunked   │ 无 EventSource，手动解析字节流 │
 * └──────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 对外只暴露一个统一接口 createSse({ url, onMessage, onDone, onError })，
 * 返回 { close() } 供主动断开。
 */

import { getServerBase } from '@/config'

// 与后端 app/api/ai.py 约定的结束标记
const DONE_FLAG = '[DONE]'
// 后端错误标记
const ERROR_PREFIX = '[ERROR]'

/**
 * 建立一条 SSE 流
 * @param {Object} options
 * @param {string} options.url 完整 URL（含查询参数）
 * @param {(text: string) => void} options.onMessage 每收到一段增量文本
 * @param {() => void} [options.onDone] 收到 [DONE]，正常结束
 * @param {(err: Error | object) => void} [options.onError] 出错
 * @param {(errMsg: string) => void} [options.onServerError] 收到后端 [ERROR] 帧
 * @returns {{ close: () => void }}
 */
export function createSse(options) {
  // #ifdef H5 || APP-PLUS
  return _createEventSourceSse(options)
  // #endif

  // #ifndef H5 || APP-PLUS
  return _createChunkedSse(options)
  // #endif
}

/** 拼接查询参数（中文需 encodeURIComponent） */
export function buildQuery(params) {
  return Object.keys(params)
    .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== '')
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
    .join('&')
}

/** 组装 SSE 完整地址 */
export function sseUrl(path, params) {
  const qs = buildQuery(params || {})
  // 每次建立流时动态读取，支持运行中切换服务器地址
  return `${getServerBase()}${path}${qs ? '?' + qs : ''}`
}

/* ------------------------------------------------------------------ *
 * H5 / App：原生 EventSource
 * ------------------------------------------------------------------ */
// #ifdef H5 || APP-PLUS
function _createEventSourceSse({ url, onMessage, onDone, onError, onServerError }) {
  const es = new EventSource(url)
  let finished = false

  es.onmessage = (event) => {
    const data = event.data
    if (data === DONE_FLAG) {
      finished = true
      es.close()
      onDone && onDone()
      return
    }
    if (data.startsWith(ERROR_PREFIX)) {
      finished = true
      es.close()
      onServerError && onServerError(data.slice(ERROR_PREFIX.length).trim())
      return
    }
    onMessage && onMessage(data)
  }

  es.onerror = (err) => {
    // 服务器正常断开也会触发 error；若已收到 [DONE] 则忽略
    if (finished) return
    es.close()
    onError && onError(err)
  }

  return {
    close() {
      finished = true
      try {
        es.close()
      } catch (e) {
        /* ignore */
      }
    },
  }
}
// #endif

/* ------------------------------------------------------------------ *
 * 微信小程序：uni.request + enableChunked，手动解析 SSE 帧
 * ------------------------------------------------------------------ */
// #ifndef H5 || APP-PLUS
function _createChunkedSse({ url, onMessage, onDone, onError, onServerError }) {
  let buffer = ''
  let finished = false

  const requestTask = uni.request({
    url,
    method: 'GET',
    enableChunked: true, // 开启分块接收（基础库 2.4.4+）
    responseType: 'text',
    header: {
      Accept: 'text/event-stream',
    },
    success: () => {
      // 连接结束，flush 残余 buffer
      _flush(true)
      if (!finished) {
        finished = true
        onDone && onDone()
      }
    },
    fail: (err) => {
      if (finished) return
      finished = true
      onError && onError(err)
    },
  })

  if (typeof requestTask.onChunkReceived === 'function') {
    requestTask.onChunkReceived((res) => {
      buffer += _uint8ToUtf8(new Uint8Array(res.data))
      _flush(false)
    })
  } else {
    // 极端兜底：基础库过旧不支持分块，提示降级
    console.warn('[SSE] 当前基础库不支持 enableChunked，请升级微信开发者工具')
  }

  // 按 SSE 规范：事件以空行（\n\n）分隔，逐帧解析
  function _flush(isEnd) {
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      _handleEvent(rawEvent)
      if (finished) return
    }
    if (isEnd && buffer.trim()) {
      _handleEvent(buffer)
      buffer = ''
    }
  }

  // 一个事件可能含多条 data: 行，拼接为完整文本
  function _handleEvent(rawEvent) {
    const data = rawEvent
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n')
    if (!data) return

    if (data === DONE_FLAG) {
      finished = true
      _abort()
      onDone && onDone()
      return
    }
    if (data.startsWith(ERROR_PREFIX)) {
      finished = true
      _abort()
      onServerError && onServerError(data.slice(ERROR_PREFIX.length).trim())
      return
    }
    onMessage && onMessage(data)
  }

  function _abort() {
    try {
      requestTask.abort()
    } catch (e) {
      /* ignore */
    }
  }

  return {
    close() {
      finished = true
      _abort()
    },
  }
}

/**
 * Uint8Array -> UTF-8 字符串
 * 优先用 TextDecoder（基础库 2.19.1+），不支持时退回手写解码。
 */
function _uint8ToUtf8(arr) {
  if (typeof TextDecoder !== 'undefined') {
    return new TextDecoder('utf-8').decode(arr)
  }
  let binary = ''
  for (let i = 0; i < arr.length; i += 1) {
    binary += String.fromCharCode(arr[i])
  }
  try {
    return decodeURIComponent(escape(binary))
  } catch (e) {
    return binary
  }
}
// #endif
