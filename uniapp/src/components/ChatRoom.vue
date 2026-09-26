<template>
  <view class="chat-room" :class="'theme-' + theme">
    <!-- 顶部会话信息条：展示自动生成的 chatId，可复制 -->
    <view class="toolbar">
      <text class="chat-id" @click="copyChatId">会话 ID：{{ chatId }}</text>
      <text v-if="readonly" class="toolbar-tag">历史查看</text>
      <text v-else class="toolbar-btn" @click="confirmClear">重新开始</text>
    </view>

    <!-- 聊天记录 -->
    <scroll-view
      class="chat-list"
      scroll-y
      :scroll-top="scrollTop"
      :scroll-with-animation="true"
      :enhanced="true"
      :show-scrollbar="false"
    >
      <view class="chat-inner">
        <!-- 欢迎语 -->
        <view v-if="welcomeText" class="welcome">
          <text class="welcome-text">{{ welcomeText }}</text>
        </view>

        <!-- 消息列表 -->
        <view
          v-for="msg in messages"
          :key="msg.id"
          :id="'msg-' + msg.id"
          class="msg-row"
          :class="msg.role === 'user' ? 'row-user' : 'row-ai'"
        >
          <!-- AI 头像（左） -->
          <view v-if="msg.role === 'ai'" class="avatar avatar-ai">
            <text class="avatar-text">{{ aiAvatar }}</text>
          </view>

          <!-- 气泡 -->
          <view class="bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-ai'">
            <text class="bubble-text" :selectable="true">{{ msg.content }}</text>
            <text v-if="msg.streaming" class="cursor">▍</text>
          </view>

          <!-- 用户头像（右） -->
          <view v-if="msg.role === 'user'" class="avatar avatar-user">
            <text class="avatar-text">我</text>
          </view>
        </view>

        <!-- 空态 -->
        <view v-if="messages.length === 0 && !welcomeText" class="empty">
          <text class="empty-text">开始对话吧～</text>
        </view>
      </view>
    </scroll-view>

    <!-- 输入区（历史查看模式下隐藏） -->
    <view v-if="!readonly" class="input-bar">
      <textarea
        class="input"
        v-model="inputValue"
        :placeholder="placeholder"
        :disabled="loading"
        :auto-height="true"
        :maxlength="-1"
        :show-confirm-bar="false"
        confirm-type="send"
        :cursor-spacing="20"
        :adjust-position="true"
        @confirm="send"
      />
      <button
        class="send-btn"
        :class="{ 'stop-btn': loading }"
        :disabled="!loading && !inputValue.trim()"
        @click="onAction"
      >
        {{ loading ? '停止' : '发送' }}
      </button>
    </view>
  </view>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { createSse } from '@/utils/sse'
import { genChatId } from '@/utils/id'
import { loadSession, loadSessionAsync, saveSession, latestSessionId } from '@/utils/chatStore'

const props = defineProps({
  // 主题：love（粉红）/ manus（紫）
  theme: { type: String, default: 'love' },
  placeholder: { type: String, default: '输入你想说的...' },
  welcomeText: { type: String, default: '' },
  aiAvatar: { type: String, default: '❤' },
  // 由页面注入：根据消息文本 + chatId 构造 SSE 完整 URL
  buildSseUrl: { type: Function, required: true },
  // 从「历史记录」进入时传入，用于加载指定会话
  sessionId: { type: String, default: '' },
  // 只读模式：仅查看历史，不显示输入区
  readonly: { type: Boolean, default: false },
  // 进入后自动发出的第一条消息（AI 助手页的「常用话题」走这条路）
  initialMessage: { type: String, default: '' },
})

const chatId = ref('')
const messages = ref([])
const inputValue = ref('')
const loading = ref(false)
const scrollTop = ref(0)

let currentSse = null
let msgSeq = 0
// 当前正在流式接收的 AI 消息 id（用于「停止生成」）
let streamingId = null
// 滚动触发计数：scroll-top 值不变时平台不会重新滚动，需保证每次都有变化
let scrollTick = 0

/** 消息时间戳（HH:MM），导出 PDF 时展示 */
function nowTime() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/* ------------------------------------------------------------------ *
 * 持久化：把当前会话写入本地存储
 *
 * 流式输出过程中高频调用，因此默认走 500ms 节流；
 * 一轮结束（完成 / 失败 / 主动停止）时立即落盘，避免返回上一页后丢失。
 * ------------------------------------------------------------------ */
let saveTimer = null
function persist(immediate = false) {
  const doSave = () => {
    saveTimer = null
    saveSession({
      id: chatId.value,
      theme: props.theme,
      messages: messages.value,
    })
  }
  if (immediate) {
    if (saveTimer) {
      clearTimeout(saveTimer)
      saveTimer = null
    }
    doSave()
    return
  }
  if (saveTimer) return
  saveTimer = setTimeout(doSave, 500)
}

/** 把存储里的会话还原成组件消息结构 */
function restore(session) {
  const list = (session.messages || []).map((m, i) => ({
    id: i + 1,
    role: m.role,
    content: m.content || '',
    streaming: false,
    time: m.time || '',
  }))
  messages.value = list
  msgSeq = list.length
}

/**
 * 带入的「常用话题」自动发出。
 *
 * 只在会话为空时发（已有历史就不打扰用户，也避免把话题重复插进老对话）；
 * 只读模式下不发（那是查看历史，不该触发新请求）。
 */
function autoSendTopic() {
  const text = (props.initialMessage || '').trim()
  if (!text || props.readonly) return
  if (messages.value.length) return
  inputValue.value = text
  send()
}

onLoad(async () => {
  // 1) 调用方显式指定了会话 id：按 id 精确恢复（远程优先，本地兜底）
  //
  //    两个曾经的坑都在这里：
  //    a) 只查本地 → 后端开着 MySQL、换设备后本地没有该会话，会静默退回下面的
  //       「恢复最近一次」，结果点开 A 会话却显示 B 的内容。改用 loadSessionAsync。
  //    b) 本地查不到就退回「恢复最近一次」→ 首页点「新建对话」传进来的新 id
  //       查不到，于是又续上了旧对话。现在改为「按传入的 id 开新会话」。
  if (props.sessionId) {
    const s = await loadSessionAsync(props.sessionId)
    if (s && (s.messages || []).length) {
      chatId.value = s.id || props.sessionId
      restore(s)
      scrollToBottom()
      return
    }
    // 查不到（全新会话）→ 用调用方给的 id 开一条空会话
    chatId.value = props.sessionId
    autoSendTopic()
    return
  }

  // 2) 未指定 id：恢复本主题最近一次会话（解决「返回再进来记录没了」）
  const lastId = latestSessionId(props.theme)
  if (lastId) {
    const s = loadSession(lastId)
    if (s && (s.messages || []).length) {
      chatId.value = s.id
      restore(s)
      scrollToBottom()
      return
    }
  }
  // 3) 没有任何历史：开新会话
  chatId.value = genChatId(props.theme)
  autoSendTopic()
})

function nextId() {
  return ++msgSeq
}

/** 底部按钮：流式中为「停止」，空闲时为「发送」 */
function onAction() {
  if (loading.value) {
    stop()
  } else {
    send()
  }
}

function send() {
  const text = inputValue.value.trim()
  if (!text || loading.value) return

  // 用户消息
  messages.value.push({
    id: nextId(),
    role: 'user',
    content: text,
    streaming: false,
    time: nowTime(),
  })
  inputValue.value = ''
  loading.value = true
  scrollToBottom()

  // AI 占位消息（流式填充）
  const aiId = nextId()
  streamingId = aiId
  messages.value.push({
    id: aiId,
    role: 'ai',
    content: '',
    streaming: true,
    time: nowTime(),
  })
  scrollToBottom()
  persist(true) // 用户消息立即落盘，中途退出也不丢

  currentSse = createSse({
    url: props.buildSseUrl(text, chatId.value),
    onMessage: (chunk) => appendAi(aiId, chunk),
    onDone: () => finishAi(aiId),
    onError: () => failAi(aiId, '连接失败，请确认后端服务已启动'),
    onServerError: (msg) => failAi(aiId, msg || '服务异常，请稍后再试'),
  })
}

/**
 * 主动停止生成：断开 SSE 连接，保留已收到的部分内容。
 * close() 内部已置 finished 标记，因此不会再有 onDone / onError 回调。
 */
function stop() {
  if (!loading.value) return
  if (currentSse) {
    currentSse.close()
    currentSse = null
  }
  const msg = messages.value.find((m) => m.id === streamingId)
  if (msg) {
    if (!msg.content) msg.content = '（已停止生成）'
    else msg.content += '\n（已停止生成）'
    msg.streaming = false
  }
  loading.value = false
  streamingId = null
  persist(true)
  scrollToBottom()
}

function appendAi(id, chunk) {
  const msg = messages.value.find((m) => m.id === id)
  if (msg) {
    msg.content += chunk
    scrollToBottom()
    persist() // 流式过程中节流保存
  }
}

function finishAi(id) {
  const msg = messages.value.find((m) => m.id === id)
  if (msg) msg.streaming = false
  loading.value = false
  currentSse = null
  streamingId = null
  persist(true)
  // 流式结束后再滚一次：去掉打字光标后文字会重新折行，避免最后一行被挤出可视区
  scrollToBottom()
}

function failAi(id, errText) {
  const msg = messages.value.find((m) => m.id === id)
  if (msg) {
    msg.content = errText
    msg.streaming = false
  }
  loading.value = false
  currentSse = null
  streamingId = null
  persist(true)
  scrollToBottom()
}

/**
 * 滚动到底部，让流式新增的内容始终可见。
 *
 * 踩坑记录（均为实测确认，非猜测）：
 * 1. `scroll-into-view` 指向最后一条消息 —— 它会把元素「顶部」对齐滚动区顶部，
 *    长回复时只能看到开头，新增内容落在屏幕外。
 * 2. `scroll-into-view` 指向末尾空锚点 —— 只能贴到大致底部，仍会漏掉尾部若干行。
 * 3. `scroll-top` 给超大值让平台钳制 —— H5 端在内容高度持续增长时不可靠：
 *    实测流式结束后 scrollTop=381 而最大可滚动 715，尾部整段看不到。
 *
 * 因此 H5 端直接操作真实滚动容器。注意 uni-app 的 scroll-view 渲染成两层同名节点：
 *   <uni-scroll-view class="chat-list">
 *     <div class="uni-scroll-view">                      ← 外层，不滚动
 *       <div class="uni-scroll-view ..." style="overflow: hidden auto">  ← 真正滚动的是这层
 * 用 querySelector 会命中外层，所以这里按计算样式的 overflow-y 精确挑选。
 * 小程序 / App 端 scroll-top 超大值由平台钳制到底部，行为正常。
 */
function scrollToBottom() {
  nextTick(() => {
    // #ifdef H5
    const nodes = document.querySelectorAll('.chat-list .uni-scroll-view')
    for (let i = 0; i < nodes.length; i += 1) {
      const el = nodes[i]
      const oy = getComputedStyle(el).overflowY
      if (oy === 'auto' || oy === 'scroll') {
        el.scrollTop = el.scrollHeight
        return
      }
    }
    // #endif

    // #ifndef H5
    // 数值递增，否则相同值不会触发 scroll-view 重新滚动
    scrollTick += 1
    scrollTop.value = 9999999 + scrollTick
    // #endif
  })
}

function clearHistory() {
  if (currentSse) currentSse.close()
  currentSse = null
  streamingId = null
  messages.value = []
  loading.value = false
}

// 复制会话 ID（H5 非安全上下文可能不支持剪贴板，需容错）
function copyChatId() {
  if (!chatId.value) return
  uni.setClipboardData({
    data: chatId.value,
    success: () => uni.showToast({ title: '会话 ID 已复制', icon: 'none' }),
    fail: () => uni.showToast({ title: '复制失败', icon: 'none' }),
  })
}

// 重新开始：清空对话并生成新会话 ID
function confirmClear() {
  if (messages.value.length === 0) {
    uni.showToast({ title: '当前还没有对话', icon: 'none' })
    return
  }
  uni.showModal({
    title: '重新开始',
    content: '将清空当前对话并生成新的会话 ID，确定吗？',
    success: (res) => {
      if (!res.confirm) return
      clearHistory()
      chatId.value = genChatId(props.theme)
      uni.showToast({ title: '已开启新会话', icon: 'none' })
    },
  })
}

defineExpose({ clearHistory, chatId, copyChatId })

onUnmounted(() => {
  if (currentSse) currentSse.close()
  // 离页兜底：立即保存，避免节流窗口内退出导致最后一段回复丢失
  if (messages.value.length) persist(true)
})
</script>

<style lang="scss" scoped>
.chat-room {
  display: flex;
  flex-direction: column;
  height: 100vh;
  /* #ifdef H5 */
  /*
   * H5 端的导航栏是页面内的真实元素，会占据文档流高度（约 44px）。
   * 若只用 100vh，容器会比可视区高出导航栏那一截，底部输入框被顶出屏幕。
   * --window-top 是 uni-app 在 H5 注入的导航栏高度变量；
   * App / 小程序用原生导航栏，不占文档流，故这两端保持 100vh。
   */
  height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
  background: #fff5f7;
}

.chat-list {
  flex: 1;
  overflow: hidden;
}

/* 顶部会话信息条 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12rpx 24rpx;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1rpx solid #f0f0f0;
}
.chat-id {
  flex: 1;
  font-size: 22rpx;
  color: #999;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin-right: 16rpx;
}
.toolbar-btn {
  flex-shrink: 0;
  font-size: 24rpx;
  color: #ff4d6d;
  padding: 6rpx 20rpx;
  border: 1rpx solid #ff4d6d;
  border-radius: 24rpx;
}
.theme-manus .toolbar-btn {
  color: #6c5ce7;
  border-color: #6c5ce7;
}
.toolbar-tag {
  flex-shrink: 0;
  font-size: 22rpx;
  color: #999;
  padding: 6rpx 18rpx;
  background: #f5f6f8;
  border-radius: 24rpx;
}

.chat-inner {
  padding: 24rpx;
}

/* 欢迎语 */
.welcome {
  display: flex;
  justify-content: center;
  margin-bottom: 28rpx;
}
.welcome-text {
  background: #fff;
  color: #999;
  font-size: 26rpx;
  padding: 14rpx 32rpx;
  border-radius: 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

/* 消息行 */
.msg-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 28rpx;
}
.row-user {
  justify-content: flex-end;
}
.row-ai {
  justify-content: flex-start;
}

/* 头像 */
.avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-ai {
  background: #ffe0e6;
  margin-right: 16rpx;
}
.avatar-user {
  background: #ff4d6d;
  margin-left: 16rpx;
}
.avatar-text {
  font-size: 32rpx;
  color: #fff;
}
.avatar-ai .avatar-text {
  color: #ff4d6d;
}

/* 气泡 */
.bubble {
  max-width: 70%;
  padding: 20rpx 24rpx;
  border-radius: 20rpx;
  font-size: 30rpx;
  line-height: 1.6;
  word-break: break-word;
}
.bubble-user {
  background: #ff4d6d;
  color: #fff;
  border-top-right-radius: 6rpx;
}
.bubble-ai {
  background: #fff;
  color: #333;
  border-top-left-radius: 6rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.bubble-text {
  white-space: pre-wrap;
}

/* 流式打字光标 */
.cursor {
  color: #ff4d6d;
  animation: blink 1s infinite;
}
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 空态 */
.empty {
  display: flex;
  justify-content: center;
  padding: 80rpx 0;
}
.empty-text {
  color: #bbb;
  font-size: 28rpx;
}

/* 输入区 */
.input-bar {
  display: flex;
  align-items: flex-end;
  padding: 16rpx 20rpx;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1rpx solid #f0f0f0;
}
.input {
  flex: 1;
  min-height: 72rpx;
  max-height: 200rpx;
  background: #f5f6f8;
  border-radius: 36rpx;
  padding: 18rpx 28rpx;
  font-size: 30rpx;
  margin-right: 16rpx;
  line-height: 1.5;
}
.send-btn {
  width: 132rpx;
  height: 72rpx;
  line-height: 72rpx;
  text-align: center;
  border-radius: 36rpx;
  background: #ff4d6d;
  color: #fff;
  font-size: 30rpx;
  flex-shrink: 0;
}
.send-btn[disabled] {
  background: #ffb3c0;
  color: #fff;
}

/* 流式中：发送按钮变「停止」，用中性灰区分 */
.send-btn.stop-btn {
  background: #f0f0f0;
  color: #ff4d6d;
}
.theme-manus .send-btn.stop-btn {
  color: #6c5ce7;
}

/* ===== manus 主题（紫） ===== */
.theme-manus .avatar-user { background: #6c5ce7; }
.theme-manus .bubble-user { background: #6c5ce7; }
.theme-manus .send-btn { background: #6c5ce7; }
.theme-manus .send-btn[disabled] { background: #c3bef5; }
.theme-manus .avatar-ai { background: #e6e2ff; }
.theme-manus .avatar-ai .avatar-text { color: #6c5ce7; }
.theme-manus .cursor { color: #6c5ce7; }
</style>
