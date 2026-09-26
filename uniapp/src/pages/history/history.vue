<template>
  <view class="history-page">
    <!-- 存储模式提示 -->
    <view class="storage-tip">
      <text class="tip-text">
        {{ remoteOn ? '已启用 MySQL 云端存储，换设备也不丢' : '后端未启用 MySQL，当前为本地存储' }}
      </text>
    </view>

    <!-- 列表 -->
    <scroll-view class="list" scroll-y :enhanced="true" :show-scrollbar="false">
      <view v-if="sessions.length === 0" class="empty">
        <text class="empty-icon">💬</text>
        <text class="empty-text">还没有对话记录</text>
        <text class="empty-tip">去和 AI 聊聊天，记录会自动保存在这里</text>
      </view>

      <view v-for="item in sessions" :key="item.id" class="card">
        <view class="card-main" @click="open(item)">
          <view class="card-head">
            <text class="card-title">{{ item.title }}</text>
            <text class="card-badge" :class="'badge-' + item.theme">
              {{ item.theme === 'manus' ? '智能体' : '恋爱大师' }}
            </text>
          </view>
          <text class="card-preview">{{ item.preview || '（暂无内容）' }}</text>
          <view class="card-foot">
            <text class="card-time">{{ item.updatedAt }}</text>
            <text class="card-count">{{ item.msgCount || 0 }} 轮对话</text>
          </view>
        </view>

        <view class="card-actions">
          <view class="act" hover-class="act-hover" @click="open(item)">
            <text class="act-text">查看</text>
          </view>
          <view class="act" hover-class="act-hover" @click="exportSessionPdf(item)">
            <text class="act-text act-primary">导出 PDF</text>
          </view>
          <view class="act" hover-class="act-hover" @click="remove(item)">
            <text class="act-text act-danger">删除</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 底部操作 -->
    <view v-if="sessions.length" class="footer">
      <view class="clear-btn" hover-class="clear-btn-hover" @click="clearAll">
        <text class="clear-text">清空全部记录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import {
  loadIndexAsync,
  removeSessionAsync,
  clearAllSessionsAsync,
  isRemoteOk,
} from '@/utils/chatStore'
import { exportSessionPdf } from '@/utils/exportPdf'

const sessions = ref([])
const remoteOn = ref(false) // 后端存储是否可用

// 用 onShow 而非 onLoad：从会话页返回时列表要刷新（标题 / 预览 / 时间都会变）
onShow(async () => {
  sessions.value = await loadIndexAsync()
  remoteOn.value = isRemoteOk()
})

/** 进入会话继续聊（按主题跳对应页面） */
function open(item) {
  const page = item.theme === 'manus' ? '/pages/manus/manus' : '/pages/love/love'
  uni.navigateTo({ url: `${page}?chatId=${encodeURIComponent(item.id)}` })
}

function remove(item) {
  uni.showModal({
    title: '删除记录',
    content: `确定删除「${item.title}」吗？删除后无法恢复。`,
    success: async (res) => {
      if (!res.confirm) return
      sessions.value = await removeSessionAsync(item.id)
      remoteOn.value = isRemoteOk()
      uni.showToast({ title: '已删除', icon: 'none' })
    },
  })
}

function clearAll() {
  uni.showModal({
    title: '清空全部',
    content: '将删除所有对话记录，确定吗？',
    success: async (res) => {
      if (!res.confirm) return
      await clearAllSessionsAsync()
      sessions.value = []
      uni.showToast({ title: '已清空', icon: 'none' })
    },
  })
}

</script>

<style lang="scss" scoped>
.history-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  /* #ifdef H5 */
  min-height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
  background: #fff5f7;
}

/* 存储模式提示 */
.storage-tip {
  padding: 16rpx 24rpx 0;
}
.tip-text {
  display: block;
  font-size: 22rpx;
  color: #999;
  background: #fff;
  padding: 12rpx 20rpx;
  border-radius: 12rpx;
}

.list {
  flex: 1;
  padding: 24rpx;
}

/* 空态 */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 160rpx 40rpx;
}
.empty-icon {
  font-size: 80rpx;
  margin-bottom: 24rpx;
}
.empty-text {
  font-size: 30rpx;
  color: #666;
}
.empty-tip {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #bbb;
}

/* 会话卡片 */
.card {
  background: #fff;
  border-radius: 20rpx;
  margin-bottom: 24rpx;
  overflow: hidden;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);
}
.card-main {
  padding: 24rpx 28rpx 16rpx;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title {
  flex: 1;
  font-size: 30rpx;
  color: #333;
  font-weight: 600;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin-right: 16rpx;
}
.card-badge {
  flex-shrink: 0;
  font-size: 20rpx;
  color: #ff4d6d;
  background: #ffe9ee;
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
}
.badge-manus {
  color: #6c5ce7;
  background: #e9e6ff;
}
.card-preview {
  display: block;
  margin-top: 14rpx;
  font-size: 25rpx;
  color: #888;
  line-height: 1.5;
  /* 最多两行 */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.card-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 16rpx;
}
.card-time {
  font-size: 22rpx;
  color: #bbb;
}
.card-count {
  font-size: 22rpx;
  color: #bbb;
}

/* 卡片操作区 */
.card-actions {
  display: flex;
  border-top: 1rpx solid #f2f2f2;
}
.act {
  flex: 1;
  height: 76rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.act-hover {
  background: #fafafa;
}
.act-text {
  font-size: 26rpx;
  color: #666;
}
.act-primary {
  color: #ff4d6d;
}
.act-danger {
  color: #ef4444;
}

/* 底部 */
.footer {
  padding: 16rpx 24rpx calc(24rpx + env(safe-area-inset-bottom));
}
.clear-btn {
  height: 84rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 42rpx;
}
.clear-btn-hover {
  background: #fafafa;
}
.clear-text {
  font-size: 28rpx;
  color: #ef4444;
}
</style>
