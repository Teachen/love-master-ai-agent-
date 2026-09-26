/**
 * 常用聊天话题（AI 助手页的快捷入口）
 *
 * 为什么需要：空白输入框对用户是「冷启动」—— 不知道能问什么，
 * 于是干脆不问。给几个具体的话题按钮，转化率差别很大
 * （主流 AI 产品都有这排「猜你想问」）。
 *
 * 约定：
 * - theme 决定点进去打开哪个 AI（love=恋爱大师 / manus=超级智能体）
 * - text 会作为第一条消息**直接发出去**，所以要写成完整可发送的句子，
 *   不能是「关于异地恋」这种需要用户补全的半截话
 */
export const CHAT_TOPICS = [
  // ---------- AI 恋爱大师 ----------
  {
    id: 'love-crush',
    theme: 'love',
    icon: '💔',
    text: '我暗恋一个人很久了，但不知道怎么开口，该怎么办？',
  },
  {
    id: 'love-quarrel',
    theme: 'love',
    icon: '😶',
    text: '我和对方吵架了，现在谁也不理谁，我想和好但不知道怎么做。',
  },
  {
    id: 'love-confess',
    theme: 'love',
    icon: '💌',
    text: '帮我写一段真诚又不油腻的表白话，不要太长。',
  },
  {
    id: 'love-signal',
    theme: 'love',
    icon: '🤔',
    text: '怎么判断一个人是不是对我有意思？有哪些细节可以观察？',
  },
  {
    id: 'love-awkward',
    theme: 'love',
    icon: '🥶',
    text: '和喜欢的人聊天总是冷场，怎么找话题才能聊下去？',
  },
  {
    id: 'love-longdistance',
    theme: 'love',
    icon: '✈️',
    text: '异地恋很难维持，有什么具体可做的办法吗？',
  },

  // ---------- AI 超级智能体 ----------
  {
    id: 'manus-trip',
    theme: 'manus',
    icon: '📅',
    text: '帮我规划一次周末两天一夜的短途旅行，预算 1500 元左右，从杭州出发。',
  },
  {
    id: 'manus-gift',
    theme: 'manus',
    icon: '🎁',
    text: '送女朋友生日礼物，预算 500 元，帮我列几个有诚意又不俗气的选项。',
  },
  {
    id: 'manus-rewrite',
    theme: 'manus',
    icon: '✍️',
    text: '帮我把一段话改得更得体、更有分寸，我会把原文发给你。',
  },
  {
    id: 'manus-date',
    theme: 'manus',
    icon: '🍜',
    text: '第一次约会适合去哪里、吃什么？帮我按稳妥不踩雷的思路推荐一下。',
  },
]

/** 按主题分组（AI 助手页要按 AI 分块展示，用户才知道话题会发给谁） */
export function topicsByTheme(theme) {
  return CHAT_TOPICS.filter((t) => t.theme === theme)
}

/** 按 id 取单条（话题入口跳转时用 id 传参，页面侧再还原成文案） */
export function findTopic(id) {
  if (!id) return null
  for (let i = 0; i < CHAT_TOPICS.length; i += 1) {
    if (CHAT_TOPICS[i].id === id) return CHAT_TOPICS[i]
  }
  return null
}
