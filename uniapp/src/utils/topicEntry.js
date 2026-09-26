/**
 * 「常用话题」入口的公共逻辑（love / manus 两个页面共用）。
 *
 * 为什么抽出来：两个 AI 页除了 theme 与 SSE 地址外完全一致，
 * 话题解析 + 新会话生成 + 标题设置的代码若各写一份，将来改规则必然漏一个。
 *
 * 传参约定（由 AI 助手页拼接）：
 *   pages/love/love?topic=love-crush      常用话题入口 → 开新会话并自动发送
 *   pages/love/love?chatId=love_xxx       会话列表 / 历史入口 → 恢复指定会话
 *   pages/love/love                       无参 → 恢复该主题最近一次会话
 *
 * 话题只传 id 不传全文：URL 里塞中文需要 encodeURIComponent，
 * 三端对 query 的解码行为不完全一致，传 id 最稳。
 */
import { ref } from 'vue'
import { findTopic } from '@/config/topics'
import { genChatId } from '@/utils/id'

/**
 * @param {string} theme 'love' | 'manus'
 * @returns {{ chatId: import('vue').Ref<string>, readonly: import('vue').Ref<boolean>,
 *            initialMessage: import('vue').Ref<string>, init: (options?: object) => void }}
 */
export function useTopicEntry(theme) {
  const chatId = ref('')
  const readonly = ref(false)
  const initialMessage = ref('')

  function init(options = {}) {
    readonly.value = options.readonly === '1'

    const topic = findTopic(options.topic)
    if (topic) {
      // 话题 = 想开一段新对话，所以生成全新 chatId；
      // ChatRoom 拿到查不到的 id 会开空会话，随后把 initialMessage 发出去。
      chatId.value = genChatId(theme)
      initialMessage.value = topic.text
      applyTitle(topic.text)
      return
    }

    // 普通入口：带 chatId 就恢复该会话，不带就交给 ChatRoom 恢复最近一次
    chatId.value = options.chatId || ''
  }

  return { chatId, readonly, initialMessage, init }
}

/**
 * 用话题文案当标题，让用户知道这条会话是从哪个问题开始的。
 * 截断按「字符」而不是 length —— emoji 占两个 UTF-16 码元，直接 slice 会截出半个代理对。
 */
function applyTitle(text) {
  const chars = Array.from(text)
  const title = chars.length > 12 ? `${chars.slice(0, 12).join('')}…` : text
  try {
    uni.setNavigationBarTitle({ title })
  } catch (e) {
    // 个别平台早期版本不支持动态改标题，忽略即可
  }
}
