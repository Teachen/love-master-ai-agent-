<template>
  <view class="login">
    <!-- 品牌区 -->
    <view class="hero">
      <!-- 环境角标：仅非生产构建显示（预发/测试包一眼可辨） -->
      <view v-if="!isProd" class="env-badge">
        <text class="env-badge-text">{{ envLabel }}</text>
      </view>
      <view class="logo">❤</view>
      <text class="hero-title">{{ appTitle }}</text>
      <text class="hero-sub">
        {{ isLoggedIn ? '账号已登录，对话记录会同步到云端' : '登录后可跨设备同步对话记录' }}
      </text>
    </view>

    <!-- ========== 已登录：账号管理 ========== -->
    <view v-if="isLoggedIn" class="card">
      <view class="profile">
        <view class="avatar">
          <text class="avatar-text">{{ (user && user.nickname ? user.nickname : '❤').slice(0, 1) }}</text>
        </view>
        <view class="profile-info">
          <text class="profile-name">{{ user ? user.nickname || '未设置昵称' : '' }}</text>
          <text class="profile-phone">{{ user && user.phone ? user.phone : '未绑定手机号' }}</text>
        </view>
      </view>

      <view class="identity-box">
        <text class="identity-title">已绑定的登录方式</text>
        <view class="identity-list">
          <view v-for="(it, i) in identities" :key="i" class="identity-item">
            <text class="identity-name">{{ providerLabel(it.provider) }}</text>
            <text class="identity-time">{{ it.boundAt }}</text>
          </view>
          <text v-if="!identities.length" class="identity-empty">暂无</text>
        </view>
      </view>

      <!-- 未绑手机号时提示绑定：绑定后换设备也能找回账号 -->
      <view v-if="user && !user.hasPhone" class="bind-box">
        <text class="bind-title">绑定手机号</text>
        <text class="bind-tip">绑定后即使换手机、换设备，也能用手机号找回账号与记录。</text>
        <view class="bind-row">
          <input
            class="input bind-input"
            type="number"
            maxlength="11"
            v-model="bindForm.phone"
            placeholder="输入手机号"
            placeholder-class="ph"
          />
          <view
            class="code-btn"
            :class="{ 'code-btn-off': bindCountdown > 0 }"
            hover-class="code-btn-hover"
            @click="onSendBindCode"
          >
            <text class="code-btn-text">{{ bindCountdown > 0 ? bindCountdown + 's' : '获取验证码' }}</text>
          </view>
        </view>
        <input
          class="input"
          type="number"
          maxlength="6"
          v-model="bindForm.code"
          placeholder="输入验证码"
          placeholder-class="ph"
        />
        <view class="btn btn-primary" hover-class="btn-hover" @click="onBindPhone">
          <text class="btn-text">确认绑定</text>
        </view>
      </view>

      <view class="btn btn-ghost" hover-class="btn-hover" @click="onLogout">
        <text class="btn-text btn-text-ghost">退出登录</text>
      </view>
      <text class="logout-tip">退出后本机对话仍可查看，只是不再同步到账号</text>
    </view>

    <!-- ========== 未登录：登录表单 ========== -->
    <view v-else class="card">
      <view v-if="showWechat" class="tabs">
        <view class="tab" :class="{ 'tab-on': tab === 'phone' }" @click="tab = 'phone'">
          <text class="tab-text" :class="{ 'tab-text-on': tab === 'phone' }">手机号登录</text>
        </view>
        <view class="tab" :class="{ 'tab-on': tab === 'wechat' }" @click="tab = 'wechat'">
          <text class="tab-text" :class="{ 'tab-text-on': tab === 'wechat' }">微信一键登录</text>
        </view>
      </view>

      <!-- 手机号登录 -->
      <view v-if="tab === 'phone'" class="form">
        <input
          class="input"
          type="number"
          maxlength="11"
          v-model="form.phone"
          placeholder="请输入手机号"
          placeholder-class="ph"
        />
        <view class="code-row">
          <input
            class="input code-input"
            type="number"
            maxlength="6"
            v-model="form.code"
            placeholder="请输入验证码"
            placeholder-class="ph"
          />
          <view
            class="code-btn"
            :class="{ 'code-btn-off': countdown > 0 }"
            hover-class="code-btn-hover"
            @click="onSendCode"
          >
            <text class="code-btn-text">{{ countdown > 0 ? countdown + 's' : '获取验证码' }}</text>
          </view>
        </view>

        <!-- 开发模式：短信没真发，把验证码直接显示出来，方便联调 -->
        <view v-if="devCode" class="dev-tip" @click="fillDevCode">
          <text class="dev-tip-text">开发模式验证码：{{ devCode }}（点此填入）</text>
        </view>

        <view class="agree" @click="agreed = !agreed">
          <view class="checkbox" :class="{ 'checkbox-on': agreed }">
            <text v-if="agreed" class="checkbox-mark">✓</text>
          </view>
          <text class="agree-text">
            我已阅读并同意
            <text class="agree-link" @click.stop="showAgreement('user')">《用户协议》</text>
            和
            <text class="agree-link" @click.stop="showAgreement('privacy')">《隐私政策》</text>
          </text>
        </view>

        <view class="btn btn-primary" :class="{ 'btn-disabled': loading }" hover-class="btn-hover" @click="onLoginPhone">
          <text class="btn-text">{{ loading ? '登录中…' : '登录 / 注册' }}</text>
        </view>
        <text class="form-tip">未注册的手机号将自动创建账号</text>
      </view>

      <!-- 微信一键登录 -->
      <view v-else class="form">
        <text class="wx-title">用微信身份快速登录</text>
        <text class="wx-tip">
          无需填写手机号，点击后由微信返回你的身份标识（openid），
          我们不会获取你的微信昵称、头像和好友信息。
        </text>
        <view class="btn btn-wechat" hover-class="btn-hover" @click="onLoginWechat">
          <text class="btn-text">微信一键登录</text>
        </view>
        <text class="form-tip">登录后可在「我的」里补绑手机号，方便换设备找回</text>
      </view>
    </view>

    <!-- 账号服务未就绪时的提示（文案由 markServiceDown 按真实原因填写） -->
    <view v-if="serviceDown" class="warn">
      <text class="warn-text">{{ serviceDownText }}</text>
    </view>

    <view class="guest" hover-class="guest-hover" @click="goBack">
      <text class="guest-text">{{ isLoggedIn ? '返回首页' : '暂不登录，先逛逛 ›' }}</text>
    </view>

    <!-- 协议弹层 -->
    <view v-if="agreement" class="mask" @click="agreement = ''">
      <view class="panel" @click.stop>
        <text class="panel-title">{{ agreement === 'user' ? '用户协议' : '隐私政策' }}</text>
        <scroll-view class="panel-body" scroll-y>
          <text class="panel-text">{{ agreementText }}</text>
        </scroll-view>
        <view class="btn btn-primary" hover-class="btn-hover" @click="agreement = ''">
          <text class="btn-text">我知道了</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import {
  bindPhone as apiBindPhone,
  getAuthConfig,
  loginByPhone,
  loginByWechat,
  mergeGuest,
  sendSmsCode,
  fetchMe,
} from '@/api'
import {
  authState,
  clearLegacyFlag,
  clearSession,
  getGuestId,
  guestSpacesToMerge,
  providerLabel,
  setSession,
  updateUser,
  wechatLoginSupported,
} from '@/utils/authStore'
import { APP_TITLE, ENV_LABEL, IS_PROD, PAGE } from '@/config'

const PHONE_RE = /^1[3-9]\d{9}$/

/* 环境标识：标题与角标随构建模式变化（生产包不显示角标） */
const appTitle = APP_TITLE
const envLabel = ENV_LABEL
const isProd = IS_PROD

const tab = ref('phone')
const agreed = ref(false)
const loading = ref(false)
const serviceDown = ref(false)
/** 「账号服务不可用」时的说明文案，由 markServiceDown() 按真实原因填写 */
const serviceDownText = ref('')
const devCode = ref('')
const devCodeScene = ref('login') // 'login' | 'bind'
const agreement = ref('')
const showWechat = ref(false)
const identityList = ref([])

const form = reactive({ phone: '', code: '' })
const bindForm = reactive({ phone: '', code: '' })

const countdown = ref(0)
const bindCountdown = ref(0)
/** 倒计时秒数：优先用后端返回的 resendAfter，保证前后端限频口径一致 */
const tickInterval = ref(60)
let timer = null
let bindTimer = null

const isLoggedIn = computed(() => authState.token !== '')
const user = computed(() => authState.user)
const identities = computed(() => identityList.value)

/* ----------------------------- 生命周期 ----------------------------- */
onLoad(async () => {
  // 小程序端是否展示「微信一键登录」由后端开关 + 平台能力共同决定
  try {
    const cfg = await getAuthConfig()
    showWechat.value = wechatLoginSupported() && !!cfg.wechatMiniAppLogin
    if (cfg.smsInterval) {
      // 用后端配置的间隔做倒计时，避免前后端不一致导致 429
      tickInterval.value = cfg.smsInterval
    }
  } catch (e) {
    markServiceDown(e)
    showWechat.value = false
  }
  if (isLoggedIn.value) await refreshMe()
})

onUnload(() => stopTimer())

/* ----------------------------- 工具 ----------------------------- */

/**
 * 判定「账号服务不可用」并给出**对得上真实原因**的提示。
 *
 * 以前不管什么错都写「后端数据库未就绪」，但 404 和 503 是两件完全不同的事：
 *   404 → 后端根本没有 /api/auth 这些路由（部署的是旧版本，或没部署账号模块）
 *   503 → 后端有新代码，但数据库/短信通道没配好
 * 报错方向指错了，排查就会往错误的地方走（实测踩过：本地 8000 跑的是旧进程，
 * 提示却让人去查数据库配置）。
 */
function markServiceDown(e) {
  const status = (e && e.status) || 0
  const message = String((e && e.message) || '')

  if (status === 404) {
    serviceDownText.value =
      '后端未部署账号服务（/api/auth 不存在，通常是后端版本过旧）。' +
      '请更新并重启后端；你依然可以以游客身份使用全部对话功能。'
    serviceDown.value = true
    return true
  }
  if (status === 503 || message.indexOf('未就绪') >= 0 || message.indexOf('未配置') >= 0) {
    serviceDownText.value =
      '账号服务暂时不可用（' + (message || '后端数据库未就绪') +
      '）。你依然可以以游客身份使用全部对话功能。'
    serviceDown.value = true
    return true
  }
  return false
}

function stopTimer() {
  if (timer) clearInterval(timer)
  if (bindTimer) clearInterval(bindTimer)
  timer = null
  bindTimer = null
}

function startCountdown(refObj, timerSetter, seconds) {
  refObj.value = seconds
  const t = setInterval(() => {
    refObj.value -= 1
    if (refObj.value <= 0) {
      clearInterval(t)
      refObj.value = 0
    }
  }, 1000)
  timerSetter(t)
}

function toast(title, icon = 'none') {
  uni.showToast({ title, icon, duration: 2200 })
}

function fillDevCode() {
  if (!devCode.value) return
  if (devCodeScene.value === 'login') form.code = devCode.value
  else bindForm.code = devCode.value
  toast('已填入验证码')
}

/* ----------------------------- 发送验证码 ----------------------------- */
async function onSendCode() {
  if (countdown.value > 0) return
  const phone = (form.phone || '').trim()
  if (!PHONE_RE.test(phone)) return toast('请输入正确的手机号')

  try {
    const res = await sendSmsCode(phone, 'login')
    devCode.value = res.devCode || ''
    devCodeScene.value = 'login'
    startCountdown(countdown, (t) => (timer = t), res.resendAfter || tickInterval.value)
    toast(res.devCode ? `验证码：${res.devCode}` : '验证码已发送')
  } catch (e) {
    markServiceDown(e)
    toast(e.message || '发送失败')
  }
}

async function onSendBindCode() {
  if (bindCountdown.value > 0) return
  const phone = (bindForm.phone || '').trim()
  if (!PHONE_RE.test(phone)) return toast('请输入正确的手机号')

  try {
    const res = await sendSmsCode(phone, 'bind')
    devCode.value = res.devCode || ''
    devCodeScene.value = 'bind'
    startCountdown(bindCountdown, (t) => (bindTimer = t), res.resendAfter || tickInterval.value)
    toast(res.devCode ? `验证码：${res.devCode}` : '验证码已发送')
  } catch (e) {
    toast(e.message || '发送失败')
  }
}

/* ----------------------------- 登录 ----------------------------- */
/** 登录成功后：合并游客数据 → 刷新账号信息 → 通知其他页面 */
async function afterLogin(payload) {
  setSession(payload)
  // 把本机游客数据（含旧版本写在 default 里的）迁到账号名下
  for (const gid of guestSpacesToMerge()) {
    try {
      const r = await mergeGuest(gid)
      if (r && r.moved > 0) console.log(`[login] 已合并游客空间 ${gid}：${r.moved} 条会话`)
    } catch (e) {
      console.warn('[login] 合并游客数据失败（不影响登录）', e)
    }
  }
  clearLegacyFlag()
  await refreshMe()
  uni.$emit('auth:changed', { loggedIn: true })
}

async function onLoginPhone() {
  if (loading.value) return
  const phone = (form.phone || '').trim()
  const code = (form.code || '').trim()
  if (!PHONE_RE.test(phone)) return toast('请输入正确的手机号')
  if (!/^\d{4,6}$/.test(code)) return toast('请输入收到的验证码')
  if (!agreed.value) return toast('请先阅读并同意用户协议与隐私政策')

  loading.value = true
  try {
    const payload = await loginByPhone(phone, code)
    await afterLogin(payload)
    toast('登录成功', 'success')
    setTimeout(goBack, 600)
  } catch (e) {
    markServiceDown(e)
    toast(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function onLoginWechat() {
  if (loading.value) return
  if (!agreed.value) return toast('请先阅读并同意用户协议与隐私政策')

  // 平台守卫：只有微信小程序能拿到 code。
  //
  // ⚠️ 不能只靠「隐藏按钮」来限定平台 —— 按钮隐藏了，函数体照样会被编译进
  //    H5 / App 产物。而这两个平台的 uni.login({provider:'weixin'}) 都不可用：
  //      H5  端走的是微信网页授权，需要公众号 AppID，没配必然失败；
  //      App 端需要开放平台移动应用资质 + manifest 里配置登录模块。
  //    所以这里用 #ifdef 把原生调用整段包起来，让产物里根本不存在这段代码。
  //
  // 写法上刻意不用「块内 return」，改为往外层赋值再统一判断 ——
  // uni-app 对 #ifdef 块内的 return 处理不可靠，赋值式在各端都稳定。
  let code = ''
  let errMsg = ''
  // #ifdef MP-WEIXIN
  try {
    const loginRes = await new Promise((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: resolve,
        fail: (err) => reject(new Error(err.errMsg || '微信登录失败')),
      })
    })
    if (loginRes && loginRes.code) code = loginRes.code
    else errMsg = '未获取到微信登录凭证'
  } catch (e) {
    errMsg = e.message || '微信登录失败'
  }
  // #endif

  if (errMsg) return toast(errMsg)
  // 非微信小程序：产物里 code 恒为空串，走到这里给出明确提示
  if (!code) return toast('当前平台暂不支持微信一键登录，请使用手机号登录')

  loading.value = true
  try {
    const payload = await loginByWechat(code)
    await afterLogin(payload)
    toast('登录成功', 'success')
    setTimeout(goBack, 600)
  } catch (e) {
    toast(e.message || '微信登录失败')
  } finally {
    loading.value = false
  }
}

/* ----------------------------- 账号管理 ----------------------------- */
async function refreshMe() {
  try {
    const me = await fetchMe()
    identityList.value = me.identities || []
    // 后端返回的是脱敏手机号，直接当作展示字段用
    updateUser(me)
  } catch (e) {
    console.warn('[login] 拉取账号信息失败', e)
    if (String(e.message).indexOf('登录') >= 0) clearSession()
  }
}

async function onBindPhone() {
  const phone = (bindForm.phone || '').trim()
  const code = (bindForm.code || '').trim()
  if (!PHONE_RE.test(phone)) return toast('请输入正确的手机号')
  if (!/^\d{4,6}$/.test(code)) return toast('请输入收到的验证码')

  try {
    const res = await apiBindPhone(phone, code, true)
    // switched=true 表示后端把当前空账号并入了手机号账号，登录态必须换成新的
    setSession(res)
    await refreshMe()
    uni.$emit('auth:changed', { loggedIn: true })
    toast(res.switched ? '已合并到手机号账号' : '绑定成功', 'success')
  } catch (e) {
    const msg = String(e.message || '')
    if (msg.indexOf('已注册过账号') >= 0) {
      uni.showModal({
        title: '该手机号已注册',
        content: '这个手机号已经是另一个账号了。建议退出后用手机号直接登录，即可看到该账号下的对话记录。',
        showCancel: false,
      })
    } else {
      toast(e.message || '绑定失败')
    }
  }
}

function onLogout() {
  uni.showModal({
    title: '退出登录',
    content: '退出后本机仍可查看对话记录，但不会再同步到账号。',
    success: (r) => {
      if (!r.confirm) return
      clearSession()
      identityList.value = []
      uni.$emit('auth:changed', { loggedIn: false })
      toast('已退出登录')
      setTimeout(goBack, 500)
    },
  })
}

/* ----------------------------- 其他 ----------------------------- */
const agreementText = computed(() =>
  agreement.value === 'user'
    ? '本服务为 AI 情感咨询演示应用。你需对使用本服务过程中的言行负责，不得输入违法、侵权或涉及他人的隐私信息。AI 生成内容仅供参考，不构成专业心理或法律建议。'
    : '我们仅在你主动登录时收集必要的账号信息（手机号或微信 openid），用于：① 识别账号身份；② 同步你的对话记录。我们不会出售你的个人信息，也不会在未授权的情况下读取你的微信昵称、头像与好友列表。你可以随时在账号页退出登录，或联系我们删除账号数据。'
)

function showAgreement(type) {
  agreement.value = type
}

function goBack() {
  const pages = getCurrentPages()
  // 有上一页就回退；否则（直接以登录页为入口，如扫码/直达链接）回首页。
  // 首页是 tab 页，要用 switchTab —— reLaunch 虽然也能到 tab 页，
  // 但会重建整个页面栈，体验上不如 switchTab。
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: PAGE.index })
}
</script>

<style lang="scss" scoped>
.login {
  min-height: 100vh;
  /* #ifdef H5 */
  min-height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  box-sizing: border-box;
  /* #endif */
  background: linear-gradient(180deg, #ff8fa8 0%, #fff5f7 32%);
  padding: 0 40rpx 60rpx;
}

/* 品牌区 */
.hero {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 72rpx 0 48rpx;
}
/* 环境角标：非生产构建才渲染，让预发/测试包一眼可辨 */
.env-badge {
  position: absolute;
  left: 0;
  top: 24rpx;
  height: 44rpx;
  padding: 0 18rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.28);
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
  width: 132rpx;
  height: 132rpx;
  border-radius: 34rpx;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 68rpx;
  box-shadow: 0 8rpx 24rpx rgba(255, 77, 109, 0.25);
}
.hero-title {
  margin-top: 24rpx;
  font-size: 42rpx;
  font-weight: 700;
  color: #fff;
  letter-spacing: 4rpx;
}
.hero-sub {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.92);
}

/* 卡片 */
.card {
  background: #fff;
  border-radius: 28rpx;
  padding: 40rpx 36rpx;
  box-shadow: 0 6rpx 24rpx rgba(0, 0, 0, 0.07);
}

/* Tab */
.tabs {
  display: flex;
  margin-bottom: 36rpx;
  background: #f6f6f8;
  border-radius: 16rpx;
  padding: 6rpx;
}
.tab {
  flex: 1;
  height: 76rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12rpx;
}
.tab-on {
  background: #fff;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.06);
}
.tab-text {
  font-size: 28rpx;
  color: #888;
}
.tab-text-on {
  color: #ff4d6d;
  font-weight: 600;
}

/* 表单 */
.form {
  display: flex;
  flex-direction: column;
}
.input {
  height: 92rpx;
  background: #f6f6f8;
  border-radius: 14rpx;
  padding: 0 24rpx;
  font-size: 30rpx;
  color: #333;
  margin-bottom: 24rpx;
}
.ph {
  color: #c0c0c6;
}
.code-row {
  display: flex;
  align-items: flex-start;
}
.code-input {
  flex: 1;
  margin-right: 18rpx;
}
.code-btn {
  width: 216rpx;
  height: 92rpx;
  border-radius: 14rpx;
  background: #ffe4ea;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.code-btn-off {
  background: #f2f2f5;
}
.code-btn-hover {
  opacity: 0.8;
}
.code-btn-text {
  font-size: 26rpx;
  color: #ff4d6d;
}
.code-btn-off .code-btn-text {
  color: #aaa;
}

/* 协议勾选 */
.agree {
  display: flex;
  align-items: flex-start;
  margin: 4rpx 0 28rpx;
}
.checkbox {
  width: 34rpx;
  height: 34rpx;
  border-radius: 8rpx;
  border: 2rpx solid #d0d0d6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2rpx;
}
.checkbox-on {
  background: #ff4d6d;
  border-color: #ff4d6d;
}
.checkbox-mark {
  font-size: 22rpx;
  color: #fff;
  line-height: 1;
}
.agree-text {
  margin-left: 14rpx;
  font-size: 23rpx;
  color: #999;
  line-height: 1.6;
}
.agree-link {
  color: #ff4d6d;
}

/* 按钮 */
.btn {
  height: 94rpx;
  border-radius: 14rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-hover {
  opacity: 0.88;
}
.btn-primary {
  background: #ff4d6d;
  box-shadow: 0 6rpx 18rpx rgba(255, 77, 109, 0.28);
}
.btn-disabled {
  opacity: 0.6;
}
.btn-wechat {
  background: #07c160;
  box-shadow: 0 6rpx 18rpx rgba(7, 193, 96, 0.28);
  margin-top: 32rpx;
}
.btn-ghost {
  background: #f2f2f5;
  margin-top: 32rpx;
}
.btn-text {
  font-size: 30rpx;
  color: #fff;
  font-weight: 600;
}
.btn-text-ghost {
  color: #666;
  font-weight: 400;
}
.form-tip {
  margin-top: 20rpx;
  font-size: 22rpx;
  color: #b5b5bb;
  text-align: center;
}

/* 开发模式提示 */
.dev-tip {
  background: #fff8e1;
  border-radius: 12rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 24rpx;
}
.dev-tip-text {
  font-size: 23rpx;
  color: #b7791f;
  line-height: 1.5;
}

/* 微信登录说明 */
.wx-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}
.wx-tip {
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #999;
  line-height: 1.7;
}

/* 已登录：资料卡 */
.profile {
  display: flex;
  align-items: center;
}
.avatar {
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  background: #ffe4ea;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-text {
  font-size: 44rpx;
  color: #ff4d6d;
  font-weight: 700;
}
.profile-info {
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
}
.profile-name {
  font-size: 34rpx;
  font-weight: 600;
  color: #333;
}
.profile-phone {
  margin-top: 10rpx;
  font-size: 25rpx;
  color: #999;
}

.identity-box {
  margin-top: 36rpx;
  padding-top: 28rpx;
  border-top: 2rpx solid #f2f2f5;
}
.identity-title {
  font-size: 26rpx;
  color: #666;
  font-weight: 600;
}
.identity-list {
  margin-top: 16rpx;
}
.identity-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 0;
}
.identity-name {
  font-size: 26rpx;
  color: #333;
}
.identity-time {
  font-size: 22rpx;
  color: #bbb;
}
.identity-empty {
  font-size: 24rpx;
  color: #bbb;
}

/* 绑定手机号 */
.bind-box {
  margin-top: 32rpx;
  padding: 28rpx 24rpx;
  background: #fff7f9;
  border-radius: 18rpx;
}
.bind-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
}
.bind-tip {
  display: block;
  margin-top: 10rpx;
  margin-bottom: 22rpx;
  font-size: 23rpx;
  color: #999;
  line-height: 1.6;
}
.bind-row {
  display: flex;
  align-items: flex-start;
}
.bind-input {
  flex: 1;
  margin-right: 18rpx;
  background: #fff;
}

/* 服务不可用提示 */
.warn {
  margin-top: 28rpx;
  background: #fff4e5;
  border-radius: 16rpx;
  padding: 22rpx 26rpx;
}
.warn-text {
  font-size: 24rpx;
  color: #b45309;
  line-height: 1.6;
}

/* 游客入口 */
.guest {
  margin-top: 44rpx;
  display: flex;
  justify-content: center;
}
.guest-hover {
  opacity: 0.7;
}
.guest-text {
  font-size: 27rpx;
  color: #888;
}

/* 协议弹层 */
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
  width: 620rpx;
  max-height: 76vh;
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
.panel-body {
  margin: 24rpx 0 28rpx;
  max-height: 46vh;
}
.panel-text {
  font-size: 25rpx;
  color: #666;
  line-height: 1.8;
}
</style>
