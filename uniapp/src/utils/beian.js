/**
 * ICP 备案信息展示与跳转
 *
 * 法规要求：境内运营的**网站**需在显著位置标注备案号，并链接到工信部
 * 备案管理系统（https://beian.miit.gov.cn）。
 *
 * ⚠️ 目前只有 H5 会展示备案号（判定见 config/index.js 的 SHOW_BEIAN）。
 *    小程序与 App 走各自的主体资质审核流程，不在页面上展示，因此下面的
 *    MP / APP-PLUS 分支当前**不会被走到** —— 保留是为了将来若重新开启分端展示，
 *    跳转逻辑可以直接用，不必再踩一遍「小程序打不开外链」的坑。
 *
 * 各平台打开外部链接的能力差别很大，这里统一收口：
 *   H5    window.open 新标签页打开
 *   App   plus.runtime.openURL 交给系统浏览器
 *   小程序 **没有任何接口能在应用内打开外部网页**：
 *         web-view 只加载「自己配置过业务域名的页面」，工信部网址配不了；
 *         所以退化为「复制链接 + 提示到浏览器打开」——这是唯一合规且可用的做法。
 */
import { BEIAN } from '@/config'

/** 要打开的备案系统地址 */
export const BEIAN_URL = 'https://beian.miit.gov.cn'

/**
 * 打开工信部备案查询页
 * @returns {Promise<boolean>} 是否成功唤起（小程序端为「已复制」）
 */
export function openBeian() {
  // #ifdef H5
  window.open(BEIAN_URL, '_blank', 'noopener')
  return Promise.resolve(true)
  // #endif

  // #ifdef APP-PLUS
  try {
    plus.runtime.openURL(BEIAN_URL)
    return Promise.resolve(true)
  } catch (e) {
    uni.showToast({ title: '打开失败', icon: 'none' })
    return Promise.resolve(false)
  }
  // #endif

  // #ifdef MP
  // 小程序不能直接打开外部网址：复制后引导用户去浏览器
  return new Promise((resolve) => {
    uni.setClipboardData({
      data: BEIAN_URL,
      success: () => {
        uni.showModal({
          title: '备案信息查询',
          content: `备案网址已复制：\n${BEIAN_URL}\n\n小程序内无法直接打开外部网页，请在浏览器中粘贴访问。`,
          showCancel: false,
          confirmText: '我知道了',
        })
        resolve(true)
      },
      fail: () => {
        uni.showToast({ title: '复制失败，请手动访问 beian.miit.gov.cn', icon: 'none' })
        resolve(false)
      },
    })
  })
  // #endif
}

/** 备案是否还是占位值（非生产构建时在控制台提醒一下，避免忘了换真号） */
export function warnIfPlaceholderBeian() {
  if (BEIAN.isPlaceholder) {
    console.warn(
      '[备案] 尚未配置真实备案号（VITE_BEIAN_ICP / VITE_BEIAN_OWNER），' +
        '当前展示的是占位文案。上线前请在各 uniapp/.env.<mode> 里填写。'
    )
  }
}
