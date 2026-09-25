<template>
  <view class="home">
    <!-- 顶部标题 -->
    <view class="header">
      <!-- 服务器设置入口：App 端电脑 IP 会变，允许运行时修改，免去反复重新打包 -->
      <view class="server-btn" hover-class="server-btn-hover" @click="openServerSetting">
        <text class="server-btn-icon">⚙</text>
      </view>
      <view class="logo">❤</view>
      <text class="title">恋爱大师</text>
      <text class="subtitle">AI 情感顾问 · 多端应用</text>
    </view>

    <!-- 应用列表 -->
    <view class="app-list">
      <view class="app-card love-card" hover-class="card-hover" @click="goLove">
        <view class="app-icon love-icon">
          <text class="app-icon-text">❤</text>
        </view>
        <view class="app-info">
          <text class="app-name">AI 恋爱大师</text>
          <text class="app-desc">贴心的情感顾问，倾听你的恋爱心事</text>
        </view>
        <text class="app-arrow">›</text>
      </view>

      <view class="app-card manus-card" hover-class="card-hover" @click="goManus">
        <view class="app-icon manus-icon">
          <text class="app-icon-text">🤖</text>
        </view>
        <view class="app-info">
          <text class="app-name">AI 超级智能体</text>
          <text class="app-desc">可自主调用工具的智能助手</text>
        </view>
        <text class="app-arrow">›</text>
      </view>
    </view>

    <!-- 服务器地址设置弹层 -->
    <view v-if="showServer" class="mask" @click="closeServerSetting">
      <view class="panel" @click.stop>
        <text class="panel-title">服务器地址</text>
        <text class="panel-tip">
          手机上的 localhost 指向手机自身，必须填电脑的局域网 IP（手机与电脑连同一 WiFi）。
        </text>
        <input
          class="panel-input"
          v-model="serverInput"
          placeholder="http://192.168.1.5:8000/api"
          placeholder-class="panel-input-ph"
        />
        <text class="panel-current">当前生效：{{ currentServer }}</text>
        <text class="panel-current">编译默认：{{ defaultServer }}</text>
        <view class="panel-actions">
          <view class="pbtn pbtn-ghost" hover-class="pbtn-hover" @click="resetServer">恢复默认</view>
          <view class="pbtn pbtn-primary" hover-class="pbtn-hover" @click="saveServer">保存并重连</view>
        </view>
      </view>
    </view>

    <!-- 底部 -->
    <view class="footer">
      <text class="footer-text">Powered by FastAPI + LangChain · SSE 实时对话</text>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { checkHealth } from '@/api'
import { getServerBase, setServerBase, DEFAULT_SERVER_BASE } from '@/config'

const showServer = ref(false)
const serverInput = ref('')
const currentServer = ref(getServerBase())
const defaultServer = DEFAULT_SERVER_BASE

onLoad(() => {
  // 启动时探测后端是否在线，离线给出提示
  probeBackend()
})

/** 探测后端是否在线 */
function probeBackend() {
  currentServer.value = getServerBase()
  checkHealth()
    .then(() => {
      uni.showToast({ title: '后端已连接', icon: 'none', duration: 1200 })
    })
    .catch(() => {
      uni.showToast({
        title: '后端未连接，可点右上角 ⚙ 修改服务器地址',
        icon: 'none',
        duration: 3000,
      })
    })
}

function openServerSetting() {
  serverInput.value = getServerBase()
  showServer.value = true
}

function closeServerSetting() {
  showServer.value = false
}

function saveServer() {
  const v = (serverInput.value || '').trim()
  if (v && !/^https?:\/\//i.test(v)) {
    uni.showToast({ title: '地址需以 http:// 或 https:// 开头', icon: 'none', duration: 2200 })
    return
  }
  currentServer.value = setServerBase(v)
  showServer.value = false
  probeBackend()
}

function resetServer() {
  currentServer.value = setServerBase('')
  serverInput.value = currentServer.value
  uni.showToast({ title: '已恢复默认地址', icon: 'none' })
}

function goLove() {
  uni.navigateTo({ url: '/pages/love/love' })
}

function goManus() {
  uni.navigateTo({ url: '/pages/manus/manus' })
}
</script>

<style lang="scss" scoped>
.home {
  min-height: 100vh;
  /* #ifdef H5 */
  /* 同 ChatRoom：H5 导航栏占文档流高度，需扣除，避免底部内容被顶出 */
  min-height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  box-sizing: border-box;
  /* #endif */
  background: linear-gradient(180deg, #ff8fa8 0%, #fff5f7 30%);
  padding: 0 32rpx;
}

/* 顶部 */
.header {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80rpx 0 60rpx;
}

/* 服务器设置入口（右上角） */
.server-btn {
  position: absolute;
  right: 0;
  top: 80rpx;
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
}
.server-btn-hover {
  opacity: 0.65;
}
.server-btn-icon {
  font-size: 34rpx;
  color: #fff;
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
.title {
  margin-top: 28rpx;
  font-size: 44rpx;
  font-weight: 700;
  color: #fff;
  letter-spacing: 4rpx;
}
.subtitle {
  margin-top: 12rpx;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.9);
}

/* 应用列表 */
.app-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
.app-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 24rpx;
  padding: 32rpx 28rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}
.card-hover {
  transform: scale(0.98);
  opacity: 0.9;
}
.app-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.love-icon {
  background: #ffe0e6;
}
.manus-icon {
  background: #e6e2ff;
}
.app-icon-text {
  font-size: 48rpx;
}
.app-info {
  flex: 1;
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
}
.app-name {
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
}
.app-desc {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #999;
}
.app-arrow {
  font-size: 48rpx;
  color: #ccc;
  flex-shrink: 0;
}

/* 底部 */
.footer {
  display: flex;
  justify-content: center;
  padding: 80rpx 0 40rpx;
}
.footer-text {
  font-size: 24rpx;
  color: #bbb;
}

/* ---------- 服务器地址设置弹层 ---------- */
.mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.panel {
  width: 600rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx 36rpx 32rpx;
  display: flex;
  flex-direction: column;
}
.panel-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #333;
}
.panel-tip {
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #999;
  line-height: 1.6;
}
.panel-input {
  margin-top: 24rpx;
  height: 88rpx;
  background: #f6f6f8;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  color: #333;
}
.panel-input-ph {
  color: #c0c0c6;
}
.panel-current {
  margin-top: 14rpx;
  font-size: 22rpx;
  color: #b5b5bb;
  word-break: break-all;
}
.panel-actions {
  margin-top: 32rpx;
  display: flex;
  gap: 20rpx;
}
.pbtn {
  flex: 1;
  height: 84rpx;
  border-radius: 12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
}
.pbtn-ghost {
  background: #f2f2f5;
  color: #666;
}
.pbtn-primary {
  background: #ff4d6d;
  color: #fff;
}
.pbtn-hover {
  opacity: 0.85;
}
</style>
