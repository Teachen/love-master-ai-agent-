<template>
  <view class="mine-page">
    <!-- 账号卡片：头像 + 名称 + 账号，点击进入资料编辑（未登录则去登录） -->
    <view class="account" hover-class="account-hover" @click="onAccountTap">
      <view class="avatar" :class="{ 'avatar-on': loggedIn }">
        <image
          v-if="avatarIsImage"
          class="avatar-img"
          :src="user.avatar"
          mode="aspectFill"
        />
        <text v-else class="avatar-text">{{ avatarText }}</text>
      </view>
      <view class="account-main">
        <text class="account-name">{{ accountName }}</text>
        <text class="account-desc">{{ accountDesc }}</text>
      </view>
      <view class="account-action">
        <text class="account-action-text">{{ loggedIn ? '编辑资料' : '去登录' }}</text>
        <text class="account-action-arrow">›</text>
      </view>
    </view>

    <!-- 账号与安全 -->
    <view class="group">
      <text class="group-title">账号</text>
      <view class="row row-first" hover-class="row-hover" @click="goLogin">
        <text class="row-label">{{ loggedIn ? '账号与登录方式' : '登录 / 注册' }}</text>
        <text class="row-value">{{ loggedIn ? loginWays : '手机号 · 微信小程序' }}</text>
        <text class="arrow">›</text>
      </view>
      <!-- 只有分组首行用 row-first（它负责抹掉上边线）；第二行若也标上，两行之间就没有分隔线了 -->
      <view class="row" hover-class="row-hover" @click="goProfile">
        <text class="row-label">个人资料</text>
        <text class="row-value">{{ loggedIn ? '头像 · 昵称 · 签名' : '登录后可编辑' }}</text>
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- 数据 -->
    <view class="group">
      <text class="group-title">数据</text>
      <view class="row row-first" hover-class="row-hover" @click="goHistory">
        <text class="row-label">对话记录管理</text>
        <text class="row-value">导出 PDF · 清理</text>
        <text class="arrow">›</text>
      </view>
      <view class="row" hover-class="row-hover" @click="clearAll">
        <text class="row-label row-danger">清空全部对话</text>
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- 关于 -->
    <view class="group">
      <text class="group-title">关于</text>
      <view class="row row-first">
        <text class="row-label">应用名称</text>
        <text class="row-value">{{ appTitle }}</text>
      </view>
      <view class="row">
        <text class="row-label">版本</text>
        <text class="row-value">{{ version }}</text>
      </view>
      <!--
        以下都是排查用的项，只在非生产构建出现。
        原来单独有一组「连接」（服务器地址 / 连接状态 / 对话存储）直接摊在页面中部，
        对用户是纯噪音 —— 现在整个删掉，服务器地址设置收进这里，生产包里一项都没有。
      -->
      <template v-if="!isProd">
        <view class="row" hover-class="row-hover" @click="openServerSetting">
          <text class="row-label">服务器地址</text>
          <text class="row-value">{{ currentServer }}</text>
          <text class="arrow">›</text>
        </view>
        <view class="row">
          <text class="row-label">连接状态</text>
          <view class="status">
            <view class="dot" :class="online ? 'dot-on' : 'dot-off'"></view>
            <text class="status-text">{{ online ? '正常' : '未连接' }}</text>
          </view>
        </view>
        <view class="row">
          <text class="row-label">对话存储</text>
          <text class="row-value">{{ remoteOn ? '云端 MySQL' : '本机' }}</text>
        </view>
        <view class="row">
          <text class="row-label">运行环境</text>
          <text class="row-value">{{ envLabel }}</text>
        </view>
        <view class="row">
          <text class="row-label">编译默认地址</text>
          <text class="row-value row-value-wrap">{{ defaultServer }}</text>
        </view>
      </template>
    </view>

    <!-- 退出登录 -->
    <view v-if="loggedIn" class="signout" hover-class="signout-hover" @click="onLogout">
      <text class="signout-text">退出登录</text>
    </view>

    <!--
      备案信息：居中，点击跳工信部备案系统。

      **只有 H5 需要**，所以用条件编译把整段剔除 —— 小程序 / App 的产物里
      根本不存在这个节点（不是靠 CSS 隐藏，也不是运行时不渲染），
      回归测试可以直接断言「小程序 / App 产物不含这段文案」。

      原因：备案针对的是「境内网站」，H5 就是网页；小程序与 App 走各自的主体
      资质审核流程。而且小程序内**没有任何接口能在应用内打开外部网页**
      （web-view 只加载「自己配置过业务域名的页面」，工信部网址配不了），
      放上去只会得到一个点了没反应的入口。详见 docs/界面结构说明.md。
    -->
    <!-- #ifdef H5 -->
    <view class="beian" hover-class="beian-hover" @click="onBeian">
      <text class="beian-text">{{ beianText }}</text>
      <text class="beian-sub">工信部备案查询 ›</text>
    </view>
    <!-- #endif -->

    <!-- 服务器地址设置弹层 -->
    <view v-if="showServer" class="mask" @click="closeServerSetting">
      <view class="panel" @click.stop>
        <text class="panel-title">服务器地址</text>
        <text class="panel-tip">
          正式环境填 https 域名（如微信云托管给的公网域名）；只有本地调试时才填电脑的
          局域网 IP，且手机与电脑要连同一 WiFi。注意手机上的 localhost 指手机自身，不能用。
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
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { checkHealth, fetchMe } from '@/api'
import {
  getServerBase,
  setServerBase,
  DEFAULT_SERVER_BASE,
  PAGE,
  APP_TITLE,
  ENV_LABEL,
  IS_PROD,
  BEIAN,
} from '@/config'
import { authState, clearSession, providerLabel } from '@/utils/authStore'
// 备案只在 H5 用到，条件编译剔除后小程序 / App 不会打进这段代码
// #ifdef H5
import { openBeian, warnIfPlaceholderBeian } from '@/utils/beian'
// #endif
import { isRemoteOk, probeRemote, loadIndexAsync, clearAllSessionsAsync } from '@/utils/chatStore'

const VERSION = '1.0.0'

const appTitle = APP_TITLE
const envLabel = ENV_LABEL
const isProd = IS_PROD
const version = VERSION

const showServer = ref(false)
const serverInput = ref('')
const currentServer = ref(getServerBase())
const defaultServer = DEFAULT_SERVER_BASE
const online = ref(false)
const remoteOn = ref(false)
const identityCount = ref(0)
let probing = false

/* ----------------------------- 账号 ----------------------------- */
const loggedIn = computed(() => !!authState.token)
const user = computed(() => authState.user || {})

const accountName = computed(() => {
  if (!loggedIn.value) return '未登录'
  const u = user.value
  return u.nickname || u.phone || '已登录'
})

/** 头像可能是图片 URL（将来接了上传）或 emoji / 首字，这里区分渲染方式 */
const avatarIsImage = computed(() => {
  const a = loggedIn.value ? user.value.avatar : ''
  return typeof a === 'string' && /^(https?:|data:)/.test(a)
})

const avatarText = computed(() => {
  if (!loggedIn.value) return '👤'
  const u = user.value
  if (u.avatar) return u.avatar
  const n = u.nickname
  // 用 Array.from 取首字符：直接 [0] 遇到 emoji 会截出半个代理对
  return n ? Array.from(n)[0] : '❤'
})

const EMOTION_LABELS = {
  single: '单身',
  in_love: '恋爱中',
  married: '已婚',
  secret: '保密',
}

/** 副标题：账号 + 情感状态，让卡片一眼能认出是哪个账号 */
const accountDesc = computed(() => {
  if (!loggedIn.value) return '登录后可跨设备同步资料与对话'
  const u = user.value
  const acct = u.phone || (u.id ? `ID ${String(u.id).slice(0, 8)}` : '')
  const emo = EMOTION_LABELS[u.emotionStatus] || ''
  return [acct, emo].filter(Boolean).join(' · ') || '对话记录已同步到账号'
})

const loginWays = computed(() => {
  const n = identityCount.value
  if (!n) return '手机号'
  return `${n} 个方式已绑定`
})

// #ifdef H5
/**
 * 备案文案：主体名称 + 网站备案号（+ 公安备案号）。
 * 主体名称为空时只显示号码，避免出现「  闽ICP备…」这种前后空格。
 * 仅 H5 使用（模板里那段也是 #ifdef H5）。
 */
const beianText = computed(() => {
  const parts = []
  if (BEIAN.owner) parts.push(BEIAN.owner)
  parts.push(BEIAN.icp)
  if (BEIAN.police) parts.push(BEIAN.police)
  return parts.join('  ')
})
// #endif

onLoad(() => {
  // #ifdef H5
  warnIfPlaceholderBeian()
  // #endif
  probeBackend()
})

onShow(async () => {
  currentServer.value = getServerBase()
  await probeRemote()
  remoteOn.value = isRemoteOk()
  // 已登录时顺带刷一下已绑定的登录方式数量
  if (loggedIn.value) {
    try {
      const me = await fetchMe()
      identityCount.value = (me.identities || []).length
    } catch (e) {
      // 拉不到（未登录 / 后端未启）就按「仅手机号」显示，不影响页面其他内容
      identityCount.value = 0
    }
  }
})

/** 卡片点击：已登录 → 编辑资料；未登录 → 去登录 */
function onAccountTap() {
  if (loggedIn.value) goProfile()
  else goLogin()
}

function goProfile() {
  if (!loggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    goLogin()
    return
  }
  uni.navigateTo({ url: PAGE.profile })
}

function goLogin() {
  uni.navigateTo({ url: PAGE.login, fail: () => uni.showToast({ title: '打开失败', icon: 'none' }) })
}

function goHistory() {
  uni.navigateTo({ url: PAGE.history })
}

// #ifdef H5
function onBeian() {
  openBeian()
}
// #endif

/**
 * 探测后端是否在线
 *
 * 云托管最小实例数为 0 时首次请求要冷启动（导入 LangChain 全家桶可能超过 20s），
 * 所以超时放宽到 30s 并失败重试一次。
 */
async function probeBackend() {
  if (probing) return
  probing = true
  online.value = false
  for (let i = 0; i < 2; i++) {
    try {
      await checkHealth(30000)
      online.value = true
      probing = false
      return
    } catch (e) {
      if (i === 0) await new Promise((r) => setTimeout(r, 1500))
    }
  }
  probing = false
}

/* ----------------------------- 服务器地址 ----------------------------- */
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
  uni.showToast({ title: '已保存', icon: 'none' })
}

function resetServer() {
  currentServer.value = setServerBase('')
  serverInput.value = currentServer.value
  uni.showToast({ title: '已恢复默认地址', icon: 'none' })
}

/* ----------------------------- 数据 ----------------------------- */
function clearAll() {
  uni.showModal({
    title: '清空全部对话',
    content: '将删除所有对话记录，确定吗？此操作无法撤销。',
    confirmColor: '#ef4444',
    success: async (res) => {
      if (!res.confirm) return
      await clearAllSessionsAsync()
      await loadIndexAsync()
      uni.showToast({ title: '已清空', icon: 'none' })
    },
  })
}

function onLogout() {
  uni.showModal({
    title: '退出登录',
    content: '退出后本机对话仍保留，但不再同步到账号。',
    success: (res) => {
      if (!res.confirm) return
      clearSession()
      identityCount.value = 0
      uni.showToast({ title: '已退出', icon: 'none' })
    },
  })
}

// providerLabel 供将来展示登录方式明细时使用（当前用 identityCount 汇总）
void providerLabel
</script>

<style lang="scss" scoped>
.mine-page {
  min-height: 100vh;
  /* #ifdef H5 */
  min-height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
  box-sizing: border-box;
  padding: 28rpx 28rpx 60rpx;
  background: #f6f6f8;
}

/* ---------- 账号卡片 ---------- */
.account {
  display: flex;
  align-items: center;
  background: linear-gradient(135deg, #ff7d92 0%, #ff4d6d 100%);
  border-radius: 24rpx;
  padding: 36rpx 30rpx;
  box-shadow: 0 8rpx 22rpx rgba(255, 77, 109, 0.28);
}
.account-hover {
  opacity: 0.92;
}
.avatar {
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}
.avatar-on {
  background: #fff;
}
.avatar-img {
  width: 108rpx;
  height: 108rpx;
}
.avatar-text {
  font-size: 48rpx;
  color: #fff;
  font-weight: 600;
}
.avatar-on .avatar-text {
  color: #ff4d6d;
}
.account-main {
  flex: 1;
  min-width: 0;
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
}
.account-name {
  font-size: 34rpx;
  font-weight: 700;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.account-desc {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.86);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.account-action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 8rpx 0 8rpx 16rpx;
}
.account-action-text {
  font-size: 25rpx;
  color: rgba(255, 255, 255, 0.95);
}
.account-action-arrow {
  font-size: 38rpx;
  color: rgba(255, 255, 255, 0.85);
}

/* ---------- 分组 ---------- */
.group {
  margin-top: 32rpx;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
}
.group-title {
  display: block;
  padding: 22rpx 28rpx 10rpx;
  font-size: 24rpx;
  color: #9a9aa0;
}
.row {
  display: flex;
  align-items: center;
  min-height: 96rpx;
  padding: 20rpx 28rpx;
  border-top: 1rpx solid #f2f2f4;
}
/* 分组首行不画上边线（否则标题和首行之间会多一道线） */
.row-first {
  border-top: none;
}
.row-hover {
  background: #fafafa;
}
.row-label {
  font-size: 30rpx;
  color: #191919;
  flex-shrink: 0;
}
.row-danger {
  color: #ef4444;
}
.row-value {
  flex: 1;
  min-width: 0;
  margin-left: 24rpx;
  font-size: 26rpx;
  color: #9a9aa0;
  text-align: right;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
/* 很长的地址（域名）允许换行，否则截断到看不出指向哪 */
.row-value-wrap {
  white-space: normal;
  word-break: break-all;
  line-height: 1.5;
}
.arrow {
  flex-shrink: 0;
  margin-left: 12rpx;
  font-size: 40rpx;
  color: #ccc;
}

/* ---------- 连接状态 ---------- */
.status {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  margin-right: 12rpx;
}
.dot-on {
  background: #22c55e;
}
.dot-off {
  background: #ef4444;
}
.status-text {
  font-size: 26rpx;
  color: #9a9aa0;
}

/* ---------- 退出登录 ---------- */
.signout {
  margin-top: 32rpx;
  height: 96rpx;
  background: #fff;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.signout-hover {
  background: #fafafa;
}
.signout-text {
  font-size: 30rpx;
  color: #ef4444;
}

/* ---------- 备案信息（底部居中） ---------- */
.beian {
  margin-top: 56rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16rpx;
}
.beian-hover {
  opacity: 0.6;
}
.beian-text {
  font-size: 22rpx;
  color: #a8a8ae;
  text-align: center;
  line-height: 1.6;
}
.beian-sub {
  margin-top: 8rpx;
  font-size: 21rpx;
  color: #bdbdc3;
}

/* ---------- 服务器地址弹层 ---------- */
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
