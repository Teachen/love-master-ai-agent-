<template>
  <view class="apps-page">
    <!-- 品牌区（原首页头部搬到这里：会话列表页要干净，品牌信息放在功能页更合适） -->
    <view class="hero">
      <view v-if="!isProd" class="env-badge">
        <text class="env-badge-text">{{ envLabel }}</text>
      </view>
      <view class="logo">❤</view>
      <text class="hero-title">{{ appTitle }}</text>
      <text class="hero-sub">AI 情感顾问 · 多端应用</text>
    </view>

    <!-- 两个 AI 入口 -->
    <view class="entry-list">
      <view class="entry entry-love" hover-class="entry-hover" @click="openTheme('love')">
        <view class="entry-icon entry-icon-love">
          <text class="entry-emoji">❤</text>
        </view>
        <view class="entry-main">
          <text class="entry-name">AI 恋爱大师</text>
          <text class="entry-desc">贴心的情感顾问，倾听你的恋爱心事</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>

      <view class="entry entry-manus" hover-class="entry-hover" @click="openTheme('manus')">
        <view class="entry-icon entry-icon-manus">
          <text class="entry-emoji">🤖</text>
        </view>
        <view class="entry-main">
          <text class="entry-name">AI 超级智能体</text>
          <text class="entry-desc">可自主调用工具的智能助手</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
    </view>

    <!-- 常用话题：解决空白输入框的「冷启动」——不知道能问什么就干脆不问 -->
    <view class="topic-sec">
      <view class="topic-head">
        <text class="topic-title">常用话题</text>
        <text class="topic-hint">点一下直接开问</text>
      </view>

      <view v-for="g in topicGroups" :key="g.theme" class="topic-card">
        <view class="topic-card-head">
          <text class="topic-card-emoji">{{ g.icon }}</text>
          <text class="topic-card-name">{{ g.name }}</text>
        </view>
        <view
          v-for="t in g.list"
          :key="t.id"
          class="topic-row"
          hover-class="topic-row-hover"
          @click="openTopic(t)"
        >
          <text class="topic-emoji">{{ t.icon }}</text>
          <text class="topic-text">{{ t.text }}</text>
          <text class="topic-arrow">›</text>
        </view>
      </view>
    </view>

    <!-- 次级入口 -->
    <view class="sub-group">
      <view class="sub-row" hover-class="sub-row-hover" @click="goHistory">
        <text class="sub-icon">🕘</text>
        <view class="sub-main">
          <text class="sub-name">对话记录管理</text>
          <text class="sub-desc">{{ remoteOn ? '云端存储，换设备也不丢' : '本地存储（后端未启用 MySQL）' }}</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
    </view>

    <view class="foot">
      <text class="foot-text">Powered by FastAPI + LangChain · SSE 实时对话</text>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { isRemoteOk, probeRemote } from '@/utils/chatStore'
import { topicsByTheme } from '@/config/topics'
import { APP_TITLE, ENV_LABEL, IS_PROD, PAGE } from '@/config'

const appTitle = APP_TITLE
const envLabel = ENV_LABEL
const isProd = IS_PROD
const remoteOn = ref(false)

// 话题按 AI 分组展示：用户得先知道这句话是发给谁的
// （发给恋爱大师和发给超级智能体，得到的回答完全不同）
const topicGroups = [
  { theme: 'love', name: 'AI 恋爱大师', icon: '❤', list: topicsByTheme('love') },
  { theme: 'manus', name: 'AI 超级智能体', icon: '🤖', list: topicsByTheme('manus') },
]

onShow(async () => {
  // 探测一次存储后端是否可用（结果会缓存，不会反复请求）
  await probeRemote()
  remoteOn.value = isRemoteOk()
})

/**
 * 进入某个 AI。
 * 不传 chatId —— 交给 ChatRoom 恢复该主题最近一次会话，
 * 符合「点开助手就是接着上次聊」的习惯；想开新的去「消息」页点 ＋。
 */
function openTheme(theme) {
  const page = theme === 'manus' ? PAGE.manus : PAGE.love
  uni.navigateTo({
    url: page,
    fail: () => uni.showToast({ title: '打开失败', icon: 'none' }),
  })
}

/**
 * 点话题：跳到对应 AI 页并带上话题 id。
 * 页面侧（utils/topicEntry.js）会开一条全新会话、把话题作为第一条消息发出去。
 *
 * 只传 id 不传全文 —— URL 里放中文要 encodeURIComponent，
 * 三端对 query 解码的行为不完全一致，传 id 最稳。
 */
function openTopic(t) {
  const page = t.theme === 'manus' ? PAGE.manus : PAGE.love
  uni.navigateTo({
    url: `${page}?topic=${encodeURIComponent(t.id)}`,
    fail: () => uni.showToast({ title: '打开失败', icon: 'none' }),
  })
}

function goHistory() {
  uni.navigateTo({
    url: PAGE.history,
    fail: () => uni.showToast({ title: '打开失败', icon: 'none' }),
  })
}
</script>

<style lang="scss" scoped>
.apps-page {
  min-height: 100vh;
  /* #ifdef H5 */
  min-height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
  box-sizing: border-box;
  padding: 0 32rpx 60rpx;
  background: linear-gradient(180deg, #ff8fa8 0%, #fff5f7 34%);
}

/* ---------- 品牌区 ---------- */
.hero {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64rpx 0 56rpx;
}
.env-badge {
  position: absolute;
  left: 0;
  top: 24rpx;
  height: 44rpx;
  padding: 0 18rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.env-badge-text {
  font-size: 22rpx;
  color: #fff;
  letter-spacing: 1rpx;
}
.logo {
  width: 140rpx;
  height: 140rpx;
  border-radius: 36rpx;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 72rpx;
  box-shadow: 0 8rpx 24rpx rgba(255, 77, 109, 0.25);
}
.hero-title {
  margin-top: 28rpx;
  font-size: 42rpx;
  font-weight: 700;
  color: #fff;
  letter-spacing: 4rpx;
}
.hero-sub {
  margin-top: 12rpx;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.92);
}

/* ---------- 入口卡片 ---------- */
.entry-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
.entry {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 24rpx;
  padding: 32rpx 28rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}
.entry-hover {
  transform: scale(0.98);
  opacity: 0.92;
}
.entry-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.entry-icon-love {
  background: linear-gradient(135deg, #ffe0e6 0%, #ffd0da 100%);
}
.entry-icon-manus {
  background: linear-gradient(135deg, #e9e6ff 0%, #ddd7ff 100%);
}
.entry-emoji {
  font-size: 48rpx;
  line-height: 1;
}
.entry-main {
  flex: 1;
  min-width: 0;
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
}
.entry-name {
  font-size: 32rpx;
  font-weight: 600;
  color: #191919;
}
.entry-desc {
  margin-top: 8rpx;
  font-size: 25rpx;
  color: #9a9aa0;
}
.entry-arrow {
  font-size: 48rpx;
  color: #ccc;
  flex-shrink: 0;
}

/* ---------- 常用话题 ---------- */
.topic-sec {
  margin-top: 40rpx;
}
.topic-head {
  display: flex;
  align-items: baseline;
  padding: 0 8rpx 20rpx;
}
.topic-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #191919;
}
.topic-hint {
  margin-left: 14rpx;
  font-size: 23rpx;
  color: #9a9aa0;
}
.topic-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 8rpx 0 4rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.05);
  overflow: hidden;
}
.topic-card-head {
  display: flex;
  align-items: center;
  padding: 24rpx 28rpx 14rpx;
}
.topic-card-emoji {
  font-size: 30rpx;
  line-height: 1;
}
.topic-card-name {
  margin-left: 12rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: #ff4d6d;
}
.topic-row {
  display: flex;
  align-items: center;
  padding: 24rpx 28rpx;
  border-top: 1rpx solid #f5f5f7;
}
.topic-row-hover {
  background: #fafafa;
}
.topic-emoji {
  font-size: 30rpx;
  line-height: 1;
  flex-shrink: 0;
}
.topic-text {
  flex: 1;
  min-width: 0;
  margin: 0 16rpx;
  font-size: 27rpx;
  color: #4a4a52;
  /* 一句话全展示会把卡片拉得很高，超出省略；进对话后仍是完整原句 */
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.topic-arrow {
  font-size: 40rpx;
  color: #ccc;
  flex-shrink: 0;
}

/* ---------- 次级入口 ---------- */
.sub-group {
  margin-top: 32rpx;
  background: #fff;
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.05);
}
.sub-row {
  display: flex;
  align-items: center;
  padding: 28rpx;
}
.sub-row-hover {
  background: #fafafa;
}
.sub-icon {
  width: 96rpx;
  text-align: center;
  font-size: 44rpx;
  flex-shrink: 0;
}
.sub-main {
  flex: 1;
  min-width: 0;
  margin-left: 12rpx;
  display: flex;
  flex-direction: column;
}
.sub-name {
  font-size: 31rpx;
  font-weight: 600;
  color: #191919;
}
.sub-desc {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #9a9aa0;
}

/* ---------- 底部 ---------- */
.foot {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 70rpx 0 20rpx;
}
.foot-text {
  font-size: 23rpx;
  color: #c2c2c8;
}
</style>
