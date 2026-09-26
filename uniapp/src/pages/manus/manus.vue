<template>
  <ChatRoom
    theme="manus"
    ai-avatar="智"
    placeholder="向超级智能体提问..."
    welcome-text="我是 AI 超级智能体，可自主调用搜索、文件、PDF 等工具帮你完成复杂任务。"
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

// 同 love 页：话题入口 / 指定会话 / 最近会话三合一
const { chatId, readonly, initialMessage, init } = useTopicEntry('manus')

onLoad((options = {}) => init(options))

// 超级智能体：GET /api/ai/manus/chat?message=&chatId=
function buildSseUrl(message, chatId) {
  return sseUrl(API.manusChat, { message, chatId })
}
</script>
