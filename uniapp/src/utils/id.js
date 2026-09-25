/**
 * 生成会话 ID（chatId），用于区分不同会话。
 * 格式：chat_<时间戳36进制>_<随机串>，可读且基本不重复。
 */
export function genChatId(prefix = 'chat') {
  const time = Date.now().toString(36)
  const rand = Math.random().toString(36).slice(2, 8)
  return `${prefix}_${time}_${rand}`
}
