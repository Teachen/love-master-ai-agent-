<template>
  <view class="chat-page">
    <!-- 搜索框（吸顶；sticky 在 H5 / 小程序 / App 都支持，不支持也只是随页面滚动，不报错） -->
    <view class="search-wrap">
      <view class="search">
        <text class="search-icon">🔍</text>
        <input
          class="search-input"
          v-model="keyword"
          type="text"
          confirm-type="search"
          placeholder="搜索对话"
          placeholder-class="search-ph"
        />
        <text v-if="keyword" class="search-clear" @click="clearKeyword">✕</text>
      </view>
    </view>

    <!-- 会话列表 -->
    <view class="list">
      <!-- 空态 -->
      <view v-if="!filtered.length" class="empty">
        <text class="empty-emoji">{{ keyword ? '🔍' : '💬' }}</text>
        <text class="empty-title">{{ keyword ? '没有匹配的对话' : '还没有对话' }}</text>
        <text class="empty-tip">
          {{ keyword ? '换个关键词试试' : '点右下角 ＋ 找 AI 聊聊吧' }}
        </text>
        <view v-if="!keyword" class="empty-btn" hover-class="empty-btn-hover" @click="onNewChat">
          <text class="empty-btn-text">开始新对话</text>
        </view>
      </view>

      <!-- 会话行 -->
      <view
        v-for="item in filtered"
        :key="item.id"
        class="row"
        hover-class="row-hover"
        @click="openChat(item)"
        @longpress="onRowLongPress(item)"
      >
        <view class="avatar" :class="'avatar-' + (item.theme === 'manus' ? 'manus' : 'love')">
          <text class="avatar-emoji">{{ item.theme === 'manus' ? '🤖' : '❤' }}</text>
        </view>
        <view class="row-main">
          <view class="row-top">
            <text class="row-title">{{ item.title || '新对话' }}</text>
            <text class="row-time">{{ formatChatTime(item.updatedAt) }}</text>
          </view>
          <text class="row-preview">{{ item.preview || '（暂无内容）' }}</text>
        </view>
      </view>

      <!-- 列表尾部：清空入口放最下面，不干扰日常使用 -->
      <view v-if="filtered.length && !keyword" class="list-foot">
        <text class="foot-text">共 {{ sessions.length }} 个对话 · 长按可导出或删除</text>
      </view>
    </view>

    <!-- 新建对话悬浮按钮 -->
    <view class="fab" hover-class="fab-hover" @click="onNewChat">
      <text class="fab-icon">＋</text>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { loadIndexAsync, removeSessionAsync } from '@/utils/chatStore'
import { genChatId } from '@/utils/id'
import { exportSessionPdf, formatChatTime } from '@/utils/exportPdf'
import { APP_TITLE, IS_PROD } from '@/config'

const sessions = ref([])
const keyword = ref('')

/** 标题：非生产构建带环境后缀（pages.json 是静态 JSON，注入不了变量，只能运行时设） */
const appTitle = APP_TITLE

/** 按关键词过滤（标题 + 预览） */
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return sessions.value
  return sessions.value.filter((it) => {
    const hay = `${it.title || ''} ${it.preview || ''}`.toLowerCase()
    return hay.indexOf(kw) >= 0
  })
})

onLoad(() => {
  try {
    uni.setNavigationBarTitle({ title: appTitle })
  } catch (e) {
    /* 个别端不支持，忽略 */
  }
})

// onShow：从对话页返回时列表要刷新（标题 / 预览 / 时间都会变）
onShow(async () => {
  sessions.value = await loadIndexAsync()
})

function clearKeyword() {
  keyword.value = ''
}

/** 进入会话继续聊（按主题跳对应页面） */
function openChat(item) {
  const page = item.theme === 'manus' ? '/pages/manus/manus' : '/pages/love/love'
  uni.navigateTo({
    url: `${page}?chatId=${encodeURIComponent(item.id)}`,
    fail: () => uni.showToast({ title: '打开失败', icon: 'none' }),
  })
}

/**
 * 新建对话
 *
 * 注意这里会给页面显式传一个全新的 chatId。ChatRoom 侧对「传了 chatId 但本地
 * 查不到」的处理是「按该 id 开新会话」—— 早期版本会退回「恢复最近一次会话」，
 * 那样点「新建」反而续上了旧对话（已修）。
 */
function onNewChat() {
  uni.showActionSheet({
    itemList: ['AI 恋爱大师', 'AI 超级智能体'],
    success: (res) => {
      const theme = res.tapIndex === 1 ? 'manus' : 'love'
      const page = theme === 'manus' ? '/pages/manus/manus' : '/pages/love/love'
      uni.navigateTo({
        url: `${page}?chatId=${encodeURIComponent(genChatId(theme))}`,
        fail: () => uni.showToast({ title: '打开失败', icon: 'none' }),
      })
    },
  })
}

/** 长按会话行：主流聊天程序的习惯——操作收在长按菜单里，不占列表空间 */
function onRowLongPress(item) {
  uni.showActionSheet({
    itemList: ['继续对话', '导出 PDF', '删除这条对话'],
    itemColor: ['#333333', '#ff4d6d', '#ef4444'],
    success: (res) => {
      if (res.tapIndex === 0) openChat(item)
      else if (res.tapIndex === 1) exportSessionPdf(item)
      else if (res.tapIndex === 2) remove(item)
    },
  })
}

function remove(item) {
  uni.showModal({
    title: '删除对话',
    content: `确定删除「${item.title || '新对话'}」吗？删除后无法恢复。`,
    confirmColor: '#ef4444',
    success: async (res) => {
      if (!res.confirm) return
      sessions.value = await removeSessionAsync(item.id)
      uni.showToast({ title: '已删除', icon: 'none' })
    },
  })
}

// 保留引用：模板里没用 IS_PROD，但调试时需要它判断（避免被 tree-shake 掉时误判）
void IS_PROD
</script>

<style lang="scss" scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  /* #ifdef H5 */
  /* H5 的导航栏 / tabBar 占文档流高度，需扣除，否则底部会被顶出可视区 */
  height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
  /* 整体白底：会话列表往下延伸到底，不会在最后一行下方留出一块灰底 */
  background: #fff;
}

/* ---------- 搜索框 ---------- */
.search-wrap {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 20rpx 28rpx;
  background: #f6f6f8;
}
.search {
  display: flex;
  align-items: center;
  height: 72rpx;
  padding: 0 22rpx;
  background: #fff;
  border-radius: 36rpx;
}
.search-icon {
  font-size: 26rpx;
  margin-right: 14rpx;
  opacity: 0.55;
}
.search-input {
  flex: 1;
  height: 72rpx;
  font-size: 28rpx;
  color: #191919;
}
.search-ph {
  color: #b8b8bd;
}
.search-clear {
  width: 44rpx;
  text-align: center;
  font-size: 26rpx;
  color: #c0c0c6;
}

/* ---------- 会话列表 ---------- */
.list {
  flex: 1;
  min-height: 0;
  background: #fff;
  padding-bottom: 40rpx;
  /* #ifdef H5 */
  /* H5 的 tabBar 占掉视口底部，给最后一行留出空间 */
  padding-bottom: calc(40rpx + var(--window-bottom, 0px));
  /* #endif */
}.row {
  display: flex;
  align-items: center;
  padding: 24rpx 28rpx;
  /* 分隔线只从内容处开始（微信的做法），不用整条 1px 线 */
  border-bottom: 1rpx solid #f2f2f4;
}
.row-hover {
  background: #f7f7f9;
}
.avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-love {
  background: linear-gradient(135deg, #ffe0e6 0%, #ffd0da 100%);
}
.avatar-manus {
  background: linear-gradient(135deg, #e9e6ff 0%, #ddd7ff 100%);
}
.avatar-emoji {
  font-size: 46rpx;
  line-height: 1;
}
.row-main {
  flex: 1;
  min-width: 0;
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
}
.row-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.row-title {
  flex: 1;
  min-width: 0;
  font-size: 31rpx;
  font-weight: 600;
  color: #191919;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin-right: 16rpx;
}
.row-time {
  flex-shrink: 0;
  font-size: 23rpx;
  color: #b2b2b8;
}
.row-preview {
  margin-top: 10rpx;
  font-size: 26rpx;
  color: #9a9aa0;
  line-height: 1.4;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* ---------- 空态 ---------- */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 180rpx 60rpx 60rpx;
}
.empty-emoji {
  font-size: 96rpx;
  opacity: 0.35;
}
.empty-title {
  margin-top: 28rpx;
  font-size: 30rpx;
  color: #666;
  font-weight: 500;
}
.empty-tip {
  margin-top: 12rpx;
  font-size: 25rpx;
  color: #b0b0b6;
}
.empty-btn {
  margin-top: 48rpx;
  height: 80rpx;
  padding: 0 56rpx;
  border-radius: 40rpx;
  background: #ff4d6d;
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-btn-hover {
  opacity: 0.85;
}
.empty-btn-text {
  font-size: 28rpx;
  color: #fff;
  font-weight: 500;
}

/* ---------- 列表尾部 ---------- */
.list-foot {
  display: flex;
  justify-content: center;
  padding: 44rpx 0 20rpx;
}
.foot-text {
  font-size: 22rpx;
  color: #c2c2c8;
}

/* ---------- 新建对话悬浮按钮 ---------- */
.fab {
  position: fixed;
  right: 40rpx;
  bottom: 48rpx;
  /* #ifdef H5 */
  /* fixed 是相对视口定位的，H5 下必须自己让开 tabBar 的高度，否则会被压在 tabBar 底下 */
  bottom: calc(48rpx + var(--window-bottom, 0px));
  /* #endif */
  width: 104rpx;
  height: 104rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff6b85 0%, #ff4d6d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10rpx 28rpx rgba(255, 77, 109, 0.42);
  z-index: 20;
}
.fab-hover {
  transform: scale(0.94);
  opacity: 0.92;
}
.fab-icon {
  font-size: 56rpx;
  color: #fff;
  line-height: 1;
  margin-top: -4rpx;
}
</style>
