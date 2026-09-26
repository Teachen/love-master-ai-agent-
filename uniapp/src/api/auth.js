/**
 * 账号接口封装（对应后端 app/api/auth.py）
 *
 * 约定：
 * - 登录成功返回 { token, tokenType, expiresIn, user }，调用方交给 authStore.setSession 落盘
 * - 登录态由 http.js 请求拦截器统一注入请求头，业务代码无需关心
 * - 后端在数据库不可用时，登录类接口返回 503，前端提示「账号服务未就绪」
 */
import http from './http'
import { API } from '@/config'

/** 登录能力开关（公开接口）；返回 { authEnabled, smsDevMode, wechatMiniAppLogin, ... } */
export function getAuthConfig() {
  return http.get(API.authConfig)
}

/**
 * 发送短信验证码
 * @param {string} phone 手机号
 * @param {'login'|'bind'} scene 场景：登录 / 绑定手机号
 * @returns {Promise<{ok:boolean, phone:string, expiresIn:number, resendAfter:number, devCode?:string}>}
 *   devCode 只在后端 SMS_PROVIDER=none（开发模式）时出现
 */
export function sendSmsCode(phone, scene = 'login') {
  return http.post(API.authSmsSend, { phone, scene })
}

/**
 * 手机号 + 验证码登录（未注册会自动注册）
 * @returns {Promise<{token:string, user:object}>}
 */
export function loginByPhone(phone, code) {
  return http.post(API.authLoginPhone, { phone, code })
}

/**
 * 微信小程序登录（wx.login / uni.login 拿到的 code）
 * @param {string} code 临时登录凭证
 * @param {string} [appId] 留空用服务端配置
 */
export function loginByWechat(code, appId = '') {
  return http.post(API.authLoginWechat, { code, appId })
}

/**
 * 给当前账号绑定手机号
 * @param {boolean} autoMerge 当前账号为空壳时是否自动并入手机号所属账号
 * @returns {Promise<{token:string, user:object, switched:boolean}>}
 *   注意：switched=true 表示登录态已切到另一个账号，必须用返回的 token 覆盖本地
 */
export function bindPhone(phone, code, autoMerge = true) {
  return http.post(API.authBindPhone, { phone, code, autoMerge })
}

/**
 * 把游客空间的对话历史迁到当前账号
 * @param {string} guestId 游客空间 ID（guest-xxx 或 default）
 * @returns {Promise<{ok:boolean, moved:number}>}
 */
export function mergeGuest(guestId) {
  return http.post(API.authMergeGuest, { guestId })
}

/** 当前账号信息（含已绑定的登录方式） */
export function fetchMe() {
  return http.get(API.authMe)
}

/**
 * 修改资料
 * @param {{nickname?:string, avatar?:string, gender?:string,
 *          birthday?:string, bio?:string, emotionStatus?:string}} data
 *   只传要改的字段；传空串表示清空该项（不传 = 不改）
 * @returns {Promise<object>} 更新后的完整用户信息
 */
export function updateProfile(data) {
  return http.post(API.authProfile, data)
}

/** 退出登录（服务端无状态，主要是统一调用口径） */
export function logout() {
  return http.post(API.authLogout)
}
