<template>
  <ChatRoom
    theme="love"
    ai-avatar="❤"
    placeholder="向恋爱大师倾诉..."
    welcome-text="你好呀，我是恋爱大师 ❤ 有什么情感上的困惑，都可以跟我说～"
    :build-sse-url="buildSseUrl"
    :session-id="chatId"
    :readonly="readonly"
    :initial-message="initialMessage"
  />
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import ChatRoom from '@/components/ChatRoom.vue'
import { sseUrl } from '@/utils/sse'
import { useTopicEntry } from '@/utils/topicEntry'
import { API } from '@/config'

// 入口有三种：常用话题（开新会话并自动发问）/ 指定会话 / 最近的会话
// 解析逻辑与 manus 页共用，见 utils/topicEntry.js
const { chatId, readonly, initialMessage, init } = useTopicEntry('love')

onLoad((options = {}) => init(options))

// 恋爱大师：GET /api/ai/love_app/chat/sse?message=&chatId=
function buildSseUrl(message, chatId) {
  return sseUrl(API.loveChatSse, { message, chatId })
}
</script>
