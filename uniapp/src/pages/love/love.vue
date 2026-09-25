<template>
  <ChatRoom
    theme="love"
    ai-avatar="❤"
    placeholder="向恋爱大师倾诉..."
    welcome-text="你好呀，我是恋爱大师 ❤ 有什么情感上的困惑，都可以跟我说～"
    :build-sse-url="buildSseUrl"
  />
</template>

<script setup>
import ChatRoom from '@/components/ChatRoom.vue'
import { sseUrl } from '@/utils/sse'
import { API } from '@/config'

// 恋爱大师：GET /api/ai/love_app/chat/sse?message=&chatId=
function buildSseUrl(message, chatId) {
  return sseUrl(API.loveChatSse, { message, chatId })
}
</script>
