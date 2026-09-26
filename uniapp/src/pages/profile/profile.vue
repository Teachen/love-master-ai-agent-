<template>
  <view class="profile-page">
    <!-- 未登录：资料属于账号，先引导登录 -->
    <view v-if="!isLoggedIn" class="need-login">
      <text class="need-emoji">🔒</text>
      <text class="need-title">请先登录</text>
      <text class="need-tip">个人资料保存在账号里，换设备也能同步</text>
      <view class="need-btn" hover-class="btn-hover" @click="goLogin">
        <text class="need-btn-text">去登录</text>
      </view>
    </view>

    <template v-else>
      <!-- 头像预览 -->
      <view class="avatar-block">
        <view class="avatar-preview">
          <text class="avatar-emoji">{{ form.avatar || '👤' }}</text>
        </view>
        <text class="avatar-hint">点头像或下方任一项即可替换</text>
      </view>

      <!-- 头像选择 -->
      <view class="group">
        <text class="group-title">选择头像</text>
        <view class="avatar-grid">
          <view
            v-for="a in AVATARS"
            :key="a"
            class="avatar-item"
            :class="{ 'avatar-item-on': form.avatar === a }"
            hover-class="avatar-item-hover"
            @click="pickAvatar(a)"
          >
            <text class="avatar-item-text">{{ a }}</text>
          </view>
        </view>
      </view>

      <!-- 基本信息 -->
      <view class="group">
        <text class="group-title">基本信息</text>

        <view class="row row-first">
          <text class="row-label">昵称</text>
          <input
            class="row-input"
            v-model="form.nickname"
            type="text"
            maxlength="24"
            placeholder="给自己起个名字"
            placeholder-class="ph"
          />
        </view>

        <view class="row">
          <text class="row-label">账号</text>
          <text class="row-value">{{ accountText }}</text>
        </view>

        <view class="row row-column">
          <text class="row-label">性别</text>
          <view class="seg">
            <view
              v-for="g in GENDERS"
              :key="g.value"
              class="seg-item"
              :class="{ 'seg-item-on': form.gender === g.value }"
              @click="form.gender = g.value"
            >
              <text class="seg-text" :class="{ 'seg-text-on': form.gender === g.value }">
                {{ g.label }}
              </text>
            </view>
          </view>
        </view>

        <!-- 生日用 picker 组件：跨端最稳（自己拼三个列在 App/小程序上表现不一致） -->
        <picker
          mode="date"
          :value="form.birthday || TODAY"
          start="1900-01-01"
          :end="TODAY"
          @change="onBirthdayChange"
        >
          <view class="row">
            <text class="row-label">生日</text>
            <text class="row-value" :class="{ 'row-value-empty': !form.birthday }">
              {{ form.birthday || '未设置' }}
            </text>
            <text class="arrow">›</text>
          </view>
        </picker>

        <view class="row row-column">
          <text class="row-label">情感状态</text>
          <view class="seg seg-wrap">
            <view
              v-for="e in EMOTIONS"
              :key="e.value"
              class="seg-item"
              :class="{ 'seg-item-on': form.emotionStatus === e.value }"
              @click="form.emotionStatus = e.value"
            >
              <text class="seg-text" :class="{ 'seg-text-on': form.emotionStatus === e.value }">
                {{ e.label }}
              </text>
            </view>
          </view>
        </view>

        <view class="row row-column row-last">
          <view class="row-head">
            <text class="row-label">个性签名</text>
            <!-- 用 Array.from 数字符：直接 .length 会把 emoji 算成 2，计数和字数会显得很奇怪 -->
            <text class="count" :class="{ 'count-warn': bioLen > 60 }">{{ bioLen }}/60</text>
          </view>
          <textarea
            class="bio-input"
            v-model="form.bio"
            maxlength="60"
            placeholder="写点什么，让 AI 更懂你"
            placeholder-class="ph"
            :auto-height="true"
          />
        </view>
      </view>

      <!-- 保存 -->
      <view
        class="save-btn"
        :class="{ 'save-btn-off': saving }"
        hover-class="btn-hover"
        @click="onSave"
      >
        <text class="save-text">{{ saving ? '保存中…' : '保存' }}</text>
      </view>

      <view class="foot-tip">
        <text class="foot-text">资料保存在账号里，登录后各端自动同步</text>
      </view>
    </template>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { fetchMe, updateProfile } from '@/api'
import { authState, updateUser } from '@/utils/authStore'
import { PAGE } from '@/config'

/** 内置头像库：用 emoji 而不是图片上传 —— 三端零依赖、能随账号同步 */
const AVATARS = [
  '❤️', '🌸', '🌙', '⭐', '🍀', '🌈',
  '🐱', '🐰', '🐻', '🦊', '🐼', '🦋',
  '🌻', '🍃', '☕', '🎵', '📚', '🎈',
  '🌊', '💎', '🕊️', '🍰', '☀️', '🔥',
]

const GENDERS = [
  { value: 'male', label: '男' },
  { value: 'female', label: '女' },
  { value: 'secret', label: '保密' },
]

const EMOTIONS = [
  { value: 'single', label: '单身' },
  { value: 'in_love', label: '恋爱中' },
  { value: 'married', label: '已婚' },
  { value: 'secret', label: '保密' },
]

const TODAY = new Date().toISOString().slice(0, 10)

const isLoggedIn = computed(() => !!authState.token)
const saving = ref(false)

const form = reactive({
  nickname: '',
  avatar: '',
  gender: '',
  birthday: '',
  emotionStatus: '',
  bio: '',
})

/** 字数按「字符」算而不是 UTF-16 单元，否则 emoji 会被算成 2 个 */
const bioLen = computed(() => Array.from(form.bio || '').length)

/**
 * 账号展示：优先手机号（后端已脱敏），没有手机号则显示用户 ID 前 8 位。
 * 不再展示完整 ID —— 那是内部标识，对用户没有意义。
 */
const accountText = computed(() => {
  const u = authState.user
  if (!u) return '-'
  if (u.phone) return u.phone
  return u.id ? `ID ${String(u.id).slice(0, 8)}` : '-'
})

onLoad(async () => {
  fillFromUser(authState.user)
  // 拉一次最新的：可能刚在别的设备改过资料
  if (isLoggedIn.value) {
    try {
      const me = await fetchMe()
      updateUser(me)
      fillFromUser(me)
    } catch (e) {
      // 拉取失败就用本地缓存的资料，不阻塞编辑
      console.warn('[profile] 拉取账号信息失败，使用本地缓存', e)
    }
  }
})

function fillFromUser(u) {
  if (!u) return
  form.nickname = u.nickname || ''
  form.avatar = u.avatar || ''
  form.gender = u.gender || ''
  form.birthday = u.birthday || ''
  form.emotionStatus = u.emotionStatus || ''
  form.bio = u.bio || ''
}

function pickAvatar(a) {
  // 再点一次同一个 = 取消选择（避免选了就换不掉）
  form.avatar = form.avatar === a ? '' : a
}

function onBirthdayChange(e) {
  form.birthday = e.detail.value || ''
}

function goLogin() {
  uni.navigateTo({ url: PAGE.login })
}

async function onSave() {
  if (saving.value) return

  const nickname = (form.nickname || '').trim()
  if (!nickname) {
    uni.showToast({ title: '昵称不能为空', icon: 'none' })
    return
  }
  if (nickname.length > 24) {
    uni.showToast({ title: '昵称最长 24 个字符', icon: 'none' })
    return
  }
  if (bioLen.value > 60) {
    uni.showToast({ title: '个性签名最长 60 个字符', icon: 'none' })
    return
  }

  saving.value = true
  try {
    // 全量提交（而不是 diff）：这是「保存」按钮，语义就是保存当前表单
    const updated = await updateProfile({
      nickname,
      avatar: form.avatar || '',
      gender: form.gender || '',
      birthday: form.birthday || '',
      bio: (form.bio || '').trim(),
      emotionStatus: form.emotionStatus || '',
    })
    updateUser(updated)
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => {
      const pages = getCurrentPages()
      if (pages.length > 1) uni.navigateBack()
      else uni.switchTab({ url: PAGE.mine })
    }, 700)
  } catch (e) {
    uni.showToast({ title: (e && e.message) || '保存失败', icon: 'none', duration: 2600 })
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.profile-page {
  min-height: 100vh;
  /* #ifdef H5 */
  /* H5 的导航栏是文档流内的真实元素，不扣掉会多出一截可滚动空白 */
  min-height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
  box-sizing: border-box;
  padding: 28rpx 28rpx 60rpx;
  background: #f6f6f8;
}

/* ---------- 未登录 ---------- */
.need-login {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 200rpx 60rpx 60rpx;
}
.need-emoji {
  font-size: 96rpx;
  opacity: 0.4;
}
.need-title {
  margin-top: 28rpx;
  font-size: 32rpx;
  color: #333;
  font-weight: 600;
}
.need-tip {
  margin-top: 12rpx;
  font-size: 25rpx;
  color: #b0b0b6;
  text-align: center;
}
.need-btn {
  margin-top: 48rpx;
  height: 84rpx;
  padding: 0 72rpx;
  border-radius: 42rpx;
  background: #ff4d6d;
  display: flex;
  align-items: center;
  justify-content: center;
}
.need-btn-text {
  font-size: 30rpx;
  color: #fff;
  font-weight: 500;
}

/* ---------- 头像预览 ---------- */
.avatar-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24rpx 0 36rpx;
}
.avatar-preview {
  width: 168rpx;
  height: 168rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff7d92 0%, #ff4d6d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10rpx 26rpx rgba(255, 77, 109, 0.3);
}
.avatar-emoji {
  font-size: 84rpx;
  line-height: 1;
}
.avatar-hint {
  margin-top: 20rpx;
  font-size: 23rpx;
  color: #b0b0b6;
}

/* ---------- 分组 ---------- */
.group {
  margin-bottom: 28rpx;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
}
.group-title {
  display: block;
  padding: 22rpx 28rpx 12rpx;
  font-size: 24rpx;
  color: #9a9aa0;
}

/* ---------- 头像选择网格 ---------- */
.avatar-grid {
  display: flex;
  flex-wrap: wrap;
  padding: 4rpx 20rpx 24rpx;
}
.avatar-item {
  width: 96rpx;
  height: 96rpx;
  margin: 10rpx;
  border-radius: 50%;
  background: #f6f6f8;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3rpx solid transparent;
}
.avatar-item-on {
  background: #ffe9ee;
  border-color: #ff4d6d;
}
.avatar-item-hover {
  opacity: 0.75;
}
.avatar-item-text {
  font-size: 44rpx;
  line-height: 1;
}

/* ---------- 行 ---------- */
.row {
  display: flex;
  align-items: center;
  min-height: 96rpx;
  padding: 20rpx 28rpx;
  border-top: 1rpx solid #f2f2f4;
}
.row-first {
  border-top: none;
}
.row-last {
  border-bottom: none;
}
.row-column {
  flex-direction: column;
  align-items: stretch;
}
.row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.row-label {
  font-size: 30rpx;
  color: #191919;
  flex-shrink: 0;
}
.row-input {
  flex: 1;
  min-width: 0;
  margin-left: 24rpx;
  height: 60rpx;
  font-size: 30rpx;
  color: #191919;
  text-align: right;
}
.row-value {
  flex: 1;
  min-width: 0;
  margin-left: 24rpx;
  font-size: 28rpx;
  color: #9a9aa0;
  text-align: right;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.row-value-empty {
  color: #c5c5cb;
}
.arrow {
  flex-shrink: 0;
  margin-left: 10rpx;
  font-size: 40rpx;
  color: #ccc;
}
.ph {
  color: #c5c5cb;
}

/* ---------- 分段选择 ---------- */
.seg {
  display: flex;
  margin-top: 18rpx;
}
.seg-wrap {
  flex-wrap: wrap;
}
.seg-item {
  min-width: 132rpx;
  height: 64rpx;
  padding: 0 26rpx;
  margin: 0 16rpx 16rpx 0;
  border-radius: 32rpx;
  background: #f4f4f7;
  display: flex;
  align-items: center;
  justify-content: center;
}
.seg-item-on {
  background: #ffe9ee;
}
.seg-text {
  font-size: 27rpx;
  color: #666;
}
.seg-text-on {
  color: #ff4d6d;
  font-weight: 600;
}

/* ---------- 个性签名 ---------- */
.count {
  font-size: 23rpx;
  color: #c2c2c8;
}
.count-warn {
  color: #ef4444;
}
.bio-input {
  margin-top: 16rpx;
  width: 100%;
  min-height: 108rpx;
  font-size: 28rpx;
  color: #191919;
  line-height: 1.5;
}

/* ---------- 保存 ---------- */
.save-btn {
  margin-top: 40rpx;
  height: 96rpx;
  border-radius: 48rpx;
  background: linear-gradient(135deg, #ff6b85 0%, #ff4d6d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10rpx 24rpx rgba(255, 77, 109, 0.3);
}
.save-btn-off {
  opacity: 0.6;
}
.btn-hover {
  opacity: 0.88;
}
.save-text {
  font-size: 32rpx;
  color: #fff;
  font-weight: 600;
}

.foot-tip {
  display: flex;
  justify-content: center;
  padding: 28rpx 0 10rpx;
}
.foot-text {
  font-size: 22rpx;
  color: #c2c2c8;
}
</style>
