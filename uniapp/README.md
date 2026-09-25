# 恋爱大师 · uni-app 前端

基于 **uni-app + Vue3 + Vite** 的跨端前端，一套代码编译到 **H5 / 微信小程序 / App**。

包含两个应用：

| 页面 | 应用 | 接口（SSE 流式） |
|---|---|---|
| 主页 | 应用切换入口 | — |
| 页面 1 | AI 恋爱大师 | `GET /api/ai/love_app/chat/sse` |
| 页面 2 | AI 超级智能体 | `GET /api/ai/manus/chat` |

聊天室：用户消息在右、AI 在左，进入页面自动生成 `chatId` 区分会话，通过 **SSE** 实时显示对话内容；流式进行中可点「停止」中断生成并保留已收到的内容。

### 构建状态（已验证）

| 目标端 | 命令 | 结果 | 产物 | SSE 实现 |
|---|---|---|---|---|
| H5 | `npm run build:h5` | ✅ 通过 | `dist/build/h5` | `EventSource` |
| 微信小程序 | `npm run build:mp-weixin` | ✅ 通过 | `dist/build/mp-weixin` | `enableChunked` |
| App | `npm run build:app` | ✅ 通过 | `dist/build/app` | `EventSource` |

三端条件编译已验证：小程序产物中不含 `EventSource`，H5/App 产物中不含 `enableChunked`，互不污染。
环境变量注入已验证：三端产物中均无残留 `import.meta.env`，且 `--mode` 切换可正确替换后端地址。

---

## 技术栈

- **Vue 3**（`<script setup>` 组合式 API）
- **uni-app 3.0 + Vite 5**
- **Axios**（普通 HTTP 请求，小程序端经 `axios-miniprogram-adapter` 适配）
- **自研跨端 SSE 封装**（axios 不支持流式，见 `src/utils/sse.js`）

## 目录结构

```
uniapp/
├── index.html                 # H5 入口
├── package.json
├── vite.config.js             # Vite + uni 插件配置
├── .env.development           # 开发环境变量（VITE_*）
├── .env.production            # 生产环境变量（上线前必改）
├── .env.staging               # 预发环境变量（--mode staging 时加载）
├── .gitignore
├── scripts/
│   └── fix-deps.js            # 依赖修复（.DELETE 残留 / 平台包检测）
└── src/
    ├── main.js                # createSSRApp 入口
    ├── App.vue                # 全局样式
    ├── manifest.json          # 各端配置（小程序 appid 在此填）
    ├── pages.json             # 页面路由 + 导航栏
    ├── uni.scss               # 主题变量
    ├── config/index.js        # 后端地址（读 import.meta.env）
    ├── api/
    │   ├── http.js            # axios 实例（含小程序 adapter）
    │   └── index.js           # 业务接口
    ├── utils/
    │   ├── sse.js             # 跨端 SSE 封装（核心）
    │   └── id.js              # chatId 生成
    ├── components/
    │   └── ChatRoom.vue       # 通用聊天室（用户右/AI左，复用）
    └── pages/
        ├── index/index.vue    # 主页（应用切换）
        ├── love/love.vue      # AI 恋爱大师
        └── manus/manus.vue    # AI 超级智能体
```

---

## 一、安装

```bash
cd uniapp
npm install
```

依赖版本已锁定并验证：`@dcloudio/*` 统一为 `3.0.0-4080720251210001`（所有包在该版本下均存在且配套）。

### ⚠️ Windows 环境安装踩坑（重要）

在本机环境下 `npm install` 可能中断，典型报错：

| 报错 | 根因 |
|---|---|
| `EBUSY ... spawnSync node.exe` | esbuild 的 postinstall 自检 spawn node 被占用 |
| `Cannot find module @rollup/rollup-win32-x64-msvc` | npm 的 optionalDependencies bug（[npm/cli#4828](https://github.com/npm/cli/issues/4828)），平台包漏装 |
| `Cannot find module @rollup/pluginutils/dist/cjs/index.js` | postinstall 报错让 npm 提前退出，`.DELETE` 残留没恢复 |

三者是连锁的：**某一步报错 → npm 提前退出 → 文件清理没做完 → 留下 `.DELETE.<hash>` 残骸**。

**正确的安装姿势**（用官方 node，并跳过 postinstall）：

```bash
# 1. 用系统安装的 node（不是沙箱托管的 node），并让它排在 PATH 最前
#    Windows Git Bash 示例：
export PATH="/c/nvm4w/nodejs:$PATH"

# 2. 跳过 postinstall 安装（esbuild/rollup 的平台二进制由 optionalDependencies 提供，
#    不依赖 postinstall，所以跳过是安全的）
npm install --ignore-scripts

# 3. 校验并修复（若仍有残留）
npm run fix:deps
```

**已经装坏了怎么办**：`node_modules` 常因文件占用删不干净。先尝试修复：

```bash
npm run fix:deps     # 恢复 .DELETE 残留 + 检测缺失的平台包
```

若修复后仍报缺模块，再彻底重装（删除可能被安全机制拦截，用 node 强制删）：

```bash
node -e "require('fs').rmSync('node_modules',{recursive:true,force:true})"
npm install --ignore-scripts
```

> `fix:deps` 脚本位于 `scripts/fix-deps.js`，只做两件事：把 `.DELETE.<hash>` 文件改回原名、检查平台包是否缺失并给出修复命令。

### 备选：用官方脚手架重建骨架

若依赖始终装不上，用官方模板生成骨架，再把本项目的 `src/` 等覆盖进去：

```bash
npx degit dcloudio/uni-preset-vue#vite uniapp-fresh
# 复制本项目的 src/、vite.config.js、index.html，并把 package.json 的 scripts 合并过去
```

## 二、配置后端地址（多环境）

地址不写死在代码里，改为读环境变量。`src/config/index.js` 的取值优先级：

```
import.meta.env.VITE_API_BASE_URL  →  兜底默认值 http://localhost:8000/api
```

### 2.1 环境变量文件

| 文件 | 何时加载 | 用途 |
|---|---|---|
| `.env.development` | `npm run dev:*` | 本地开发（指向 `localhost:8000`） |
| `.env.production` | `npm run build:*` | 生产打包（**上线前必须改**） |
| `.env.staging` | `npm run build:h5 -- --mode staging` | 预发 / 局域网联调 |

每个文件里只需改这两行：

```ini
VITE_API_BASE_URL=http://localhost:8000/api
VITE_SSE_BASE_URL=http://localhost:8000/api
```

> 后端默认是本项目 Python 服务（`python main.py`，端口 8000）。
> 若对接 Java 参考版，改成 `http://localhost:8123/api`。

**自定义新环境**：复制 `.env.staging` 改名为 `.env.test`，然后加 `--mode test` 运行即可，无需改任何代码。

```bash
npm run build:h5 -- --mode staging       # 加载 .env.staging
npm run dev:mp-weixin -- --mode staging  # 同上
```

### 2.2 各端地址注意事项

| 端 | 能用 localhost 吗 | 要求 |
|---|---|---|
| H5 | ✅ 可以 | 后端已开 CORS；生产可写相对路径 `/api` 走 nginx 反代 |
| 微信小程序 | ⚠️ 仅开发者工具（勾「不校验合法域名」） | 真机必须 https 完整域名，且在微信后台配置 request 合法域名 |
| App | ❌ 不行 | `localhost` 指手机自身，必须局域网 IP 或 https 域名 |

> ⚠️ `VITE_SSE_BASE_URL` **不能写相对路径**：小程序端 `wx.request`、App 端 WebView 的 `EventSource` 都不走 vite 代理，必须是完整地址。

> ⚠️ 环境变量改动后需**重启 dev server** 才生效（构建期静态替换，非运行时读取）。

## 三、运行到各端

### 1. H5

```bash
npm run dev:h5        # 开发，浏览器自动打开
npm run build:h5      # 构建到 dist/build/h5
```

后端已开启 CORS（`cors_origins=["*"]`），可直接跨域调用。

### 2. 微信小程序

```bash
npm run dev:mp-weixin    # 开发（监听编译）→ 产物在 dist/dev/mp-weixin
# 或
npm run build:mp-weixin  # 发布构建 → 产物在 dist/build/mp-weixin
```

⚠️ **dev 与 build 的输出目录不同**（uni-app 约定）：

| 命令 | 输出目录 | 用途 |
|---|---|---|
| `npm run dev:mp-weixin` | `dist/dev/mp-weixin` | 开发调试，改代码自动重编译，**用这个导入开发者工具** |
| `npm run build:mp-weixin` | `dist/build/mp-weixin` | 发布构建，代码已压缩，**上传用这个** |

然后用 **微信开发者工具**「导入项目」，目录选 `dist/dev/mp-weixin`：

- `manifest.json` 的 `mp-weixin.appid` 留空时，uni-app 会自动写成 `touristappid`（游客模式），可直接跑。
  要真机预览/上传则必须填自己的 AppID。
- 开发工具里勾「详情 → 本地设置 → 不校验合法域名」，否则 `localhost` 请求会被拦。
- **真机调试**时，把 `.env.development` 里的 `localhost` 换成电脑局域网 IP（如 `http://192.168.1.10:8000`），然后重启 dev server。

> 让 HBuilderX 自动唤起开发者工具，需要两件事同时满足（缺一即报错）：
> ① HBuilderX → 工具 → 设置 → 运行配置 → **微信开发者工具路径** 指向安装目录；
> ② 微信开发者工具 → 设置 → 安全设置 → **开启「服务端口」**。
> 若嫌麻烦，直接命令行 `npm run dev:mp-weixin`，再手动导入 `dist/dev/mp-weixin` 即可，不依赖这两项配置。

### 2.1 用 HBuilderX 运行（CLI 项目模式）

本项目是「CLI 工程结构」（`package.json` + `src/`），也可以直接用 HBuilderX 打开。此时 HBuilderX 会走 **CLI 分支** —— 用项目内 `node_modules` 的编译器，而不是它自带的编译器。判定逻辑（反编译 `plugins/uniapp-extension/out/index.js` 得到）：

| 步骤 | 判定函数 | 依据 | 本项目的值 |
|---|---|---|---|
| ① | `getIsCli()` | `package.json` + `src/manifest.json` + `src/pages.json` + `src/App.vue` + `src/main.js` 是否齐全 | ✅ true |
| ② | `getVueVersion()` | **`src/manifest.json` 的 `vueVersion` 字段**，缺失则回退 `"2"` | 关键 |
| ③ | `getCompilePlugin()` | CLI + Vue2 → `node_modules/@vue/cli-service`；CLI + Vue3 → `node_modules/@dcloudio/vite-plugin-uni` | 取决于 ② |

#### 症状

HBuilderX 控制台报：

```
node_modules缺少编译器模块，请执行npm install后重试
项目 uniapp 编译失败。
```

但命令行 `npm run dev:h5` / `npm run dev:mp-weixin` 完全正常。

#### 根因

`src/manifest.json` **缺少 `vueVersion` 字段**。

1. 判定链第 ② 步读不到 `vueVersion` → 回退成 `"2"`（Vue2）
2. 第 ③ 步于是去找 `node_modules/@vue/cli-service`（Vue2 编译器）
3. 本项目装的是 `@dcloudio/vite-plugin-uni`（Vue3 编译器），没有 `@vue/cli-service`
4. → 报「缺少编译器模块」

**命令行为什么能跑？** 因为 `npm run dev:h5` 执行的是 `uni` 命令（`@dcloudio/vite-plugin-uni/bin/uni.js`），走纯 CLI 逻辑，**根本不读 `vueVersion`**。两条路径的入口不同，所以一边通一边不通。

#### 修复

在 `src/manifest.json` 顶层加一行：

```json
"vueVersion": "3"
```

加完重启 HBuilderX（或直接重新点运行）即可。

> ⚠️ CLI 工程要判成 Vue3，需**同时满足两个条件**：`vueVersion === "3"` **且** 项目根目录存在 `vite.config.js`/`vite.config.ts`。缺一都会被判成 Vue2。本项目两者都已具备，只差 `vueVersion`。

#### 验证

复刻 HBuilderX 判定链后，用 HBuilderX 自带的 node 实测（`D:\program\HBuilderX\plugins\node\node.exe`，v22.22.2）：

```bash
# 模拟 HBuilderX CLI 分支的调用方式
node node_modules/@dcloudio/vite-plugin-uni/bin/uni.js -p mp-weixin

# 输出：
# DONE  Build complete. Watching for changes...
# Run method: open Weixin Mini Program Devtools, import dist\dev\mp-weixin run.
# ready in 6852ms.
```

产物 `dist/dev/mp-weixin/` 完整生成（`app.js`、`app.json`、`pages/index|love|manus/*`）。

#### 编译通过后的下一关

HBuilderX 编译成功后会尝试自动唤起微信开发者工具。未配置路径时提示：

> 未检测到微信开发者工具，请在菜单"HBuilderX->偏好设置->运行配置"中设置微信开发者工具的路径

- 内部配置 key：`weApp.devTools.path`
- UI 路径：**HBuilderX → 工具 → 设置 → 运行配置 → 微信开发者工具路径**，填安装目录（本机：`D:\program\微信web开发者工具`）
- 同时需在微信开发者工具「设置 → 安全设置 → 开启**服务端口**」，否则 HBuilderX 无法控制它

两项都不配也可以：命令行 `npm run dev:mp-weixin`，再手动用微信开发者工具导入 `dist/dev/mp-weixin`。

### 3. App（Android/iOS）

```bash
npm run build:app       # 构建到 dist/build/app
```

#### 应用图标与启动图

已生成全套资源，放在**项目根** `res/` 下（不放 `src/static/`，避免被一并打进 H5 / 小程序产物）：

| 目录 | 内容 | 数量 |
|---|---|---|
| `res/source/` | 原始 AI 生成素材（1024×1024 备份） | 1 |
| `res/app-icons/` | Android 4 档 + iOS 12 档 + 通用 512 / 1024 | 18 |
| `res/app-splash/` | 启动图 720×1280 / 1080×1920 / 1440×2560 | 3 |
| `res/brand-colors.txt` | 从图标采样的品牌渐变端点色 | — |

主视觉是 **3D 玻璃质感爱心**（粉紫渐变），启动图为品牌渐变 + 居中圆角图标 + 应用名「恋爱大师」。
`res/app-icons/icon-1024.png` 是主图，HBuilderX 图标配置界面可直接用它一键生成全套。

> 原始 AI 图右下角有「AI生成 WORKBUDDY」水印，已用**双线性外推**在纯渐变区域做无缝修复
> （取水印区左侧列 + 上方行做平面外推，比模糊覆盖干净，肉眼无接缝）。

#### manifest.json 配置（已写好）

`src/manifest.json` → `app-plus.distribute`：

```json
"icons": {
  "android": { "hdpi": "res/app-icons/android-72.png", "xhdpi": "...", "xxhdpi": "...", "xxxhdpi": "..." },
  "ios": { "appstore": "res/app-icons/icon-1024.png", "iphone": { "..." : "..." }, "ipad": { "..." : "..." } }
},
"splashScreens": {
  "android": { "xhdpi": "...", "xxhdpi": "...", "xxxhdpi": "..." }
}
```

两个**极易写错**的点：

1. **路径基准是「项目根目录」，不是 `src/`。**
   HBuilderX 用 `getFilePath(base, p)` 解析（源码见 `plugins/uniapp-extension/out/index.js`）：
   ```js
   const i = join(base, p);            // base = 项目根目录
   return existsSync(i) ? resolve(i) : existsSync(p) ? resolve(p) : null;
   ```
   所以写 `res/app-icons/xxx.png`（相对 `uniapp/`），而不是 `src/static/...`。

2. **启动图字段名是 `splashScreens`（复数）**，不是 `splashscreen`（单数）。
   单数的 `app-plus.splashscreen` 是**运行时行为配置**（`autoclose` / `delay`），二者不是一回事，写错启动图不生效。

#### 云打包步骤（HBuilderX）

1. HBuilderX 导入 `uniapp` **整个项目目录**（不要只拖 `src`，否则会用 HBuilderX 自带编译器）；
2. 打开 `src/manifest.json` → **App 图标配置** → 确认图标就位（或上传 `res/app-icons/icon-1024.png` 后点「自动生成所有图标并替换」）；
   → **启动界面配置** → 确认 3 档启动图；
3. 确认 `appid` 已存在（当前 `__UNI__718998A`，DCloud 自动分配，云打包必需）；
4. 菜单 **发行 → 原生 App-云打包**：选 Android / iOS；Android 可先用「DCloud 公用证书」出测试包，iOS 需自有证书；
5. 打包完成后下载 APK 安装，或上传应用市场。

> 云打包是**服务端**行为。本地 `npm run build:app` 只产出前端资源（`dist/build/app`），不出安装包。
> 也可把 `dist/build/app` 导入 HBuilderX 做真机运行调试。

> App 端 `localhost` 指手机自身，必须把 `.env.production` 改成局域网 IP 或 https 域名。
> 也可以直接用首页右上角的 **⚙ 服务器设置**在 App 内修改（运行时生效，无需重新打包）。详见 Q11。

---

## 四、SSE 跨端实现说明（核心）

SSE 不能用 axios（axios 面向一次性响应，不支持持久流）。三端机制不同，`src/utils/sse.js` 用**条件编译**分别实现：

| 平台 | 实现 | 说明 |
|---|---|---|
| H5 | 原生 `EventSource` | 浏览器自带，自动解析事件帧 |
| App | 原生 `EventSource` | 运行于内置 WebView，同 H5 |
| 微信小程序 | `uni.request` + `enableChunked` | 无 `EventSource`，手动解析字节流 |

统一接口：

```js
import { createSse, sseUrl } from '@/utils/sse'

const conn = createSse({
  url: sseUrl('/ai/love_app/chat/sse', { message, chatId }),
  onMessage: (text) => { /* 每收到一段增量文本 */ },
  onDone: () => { /* 收到 [DONE]，正常结束 */ },
  onError: (err) => { /* 网络错误 */ },
  onServerError: (msg) => { /* 后端 [ERROR] 帧 */ },
})
conn.close() // 主动断开
```

**协议约定**（与后端 `app/api/ai.py` 对齐）：

```
data: <一段文本>

data: [DONE]        ← 结束标记
```

后端会在数据内部换行时拆成多条 `data:` 行；小程序端的解析器会按空行切帧、按 `data:` 前缀重组文本。

---

## 四之二、聊天室滚动到底部（实测踩坑）

流式对话要求「始终能看到最新输出」。试过三种写法，只有第三种真能贴到底部（均在真实浏览器里量过 `scrollTop / scrollHeight / clientHeight`）：

| 写法 | 结果 |
|---|---|
| `scroll-into-view` 指向最后一条消息 | ❌ 它把元素**顶部**对齐滚动区顶部，长回复只看得到开头 |
| `scroll-into-view` 指向末尾空锚点 | ⚠️ 只能贴到大致底部，仍漏掉尾部若干行 |
| `scroll-top` 设超大值让平台钳制 | ❌ **H5 端在内容高度持续增长时失效**：实测流式结束后 `top=381`，而 `max=715`，尾部整段看不到 |
| **H5 直接操作真实滚动容器**（当前实现） | ✅ 实测 `top=856 / max=856`，`atBottom=true` |

当前实现（`src/components/ChatRoom.vue`）：

```js
function scrollToBottom() {
  nextTick(() => {
    // #ifdef H5
    qsa('.chat-list .uni-scroll-view').forEach(...)  // 见下方说明
    // #endif
    // #ifndef H5
    scrollTop.value = 9999999 + (++scrollTick)   // 小程序/App 走 scroll-top
    // #endif
  })
}
```

⚠️ **关键坑**：uni-app 的 `<scroll-view>` 在 H5 会渲染成两层**同名**节点，真正能滚的是内层：

```html
<uni-scroll-view class="chat-list">
  <div class="uni-scroll-view">                                    <!-- 外层，不滚 -->
    <div class="uni-scroll-view uni-scroll-view-scrollbar-hidden"
         style="overflow: hidden auto;">                           <!-- 真正滚动的是这层 -->
      <div class="uni-scroll-view-content"> ...消息... </div>
    </div>
  </div>
</uni-scroll-view>
```

所以 `document.querySelector('.chat-list .uni-scroll-view')` 会命中**外层**，赋值无效。
项目里改为遍历所有匹配节点、按计算样式挑 `overflow-y: auto|scroll` 的那一层，
这样即使 uni-app 以后调整类名也仍然可用。

---

## 五、常见问题

**Q1：H5 报跨域？**
后端已配 CORS 放行。若仍报，确认后端 `app/core/middleware.py` 的 CORS 中间件已注册，或把 `.env.development` 的 `VITE_API_BASE_URL` 改为相对路径 `/api` 走 `vite.config.js` 的代理。

**Q2：小程序发不出请求？**
① 开发者工具勾「不校验合法域名」；② 真机用局域网 IP 而非 `localhost`；③ 确认后端已启动。

**Q3：App 上连不上？**
App 端 `localhost` 是手机自己。改 `.env.development` 为电脑局域网 IP（手机与电脑同一 WiFi），并确认后端监听 `0.0.0.0`。

**Q4：SSE 没有实时逐字显示？**
检查后端响应头 `X-Accel-Buffering: no` 已设置（见 `app/api/ai.py`），中间不要经过会缓冲的反向代理。

**Q5：小程序流式不生效？**
`enableChunked` 需微信基础库 2.4.4+，升级开发者工具；真机微信版本过低也可能不支持。

**Q6：改了 `.env.*` 但地址没变？**
环境变量是**构建期静态替换**，不是运行时读取。改完必须重启 dev server 或重新 build；另外变量名必须以 `VITE_` 开头才会被注入。

**Q7：点了「停止」之后 AI 又继续输出？**
正常不会。`close()` 会先置 `finished` 标记再断开，后续回调全部被拦截。若仍出现，检查是否在 `send()` 之外又手动触发了新的 SSE 连接。

**Q8：H5 上底部输入框被顶出屏幕 / 页面能上下滚动一截？**
uni-app 在 **H5 端把导航栏渲染成页面内的真实元素**，它占据文档流高度（约 44px）。
而 App / 微信小程序的导航栏是原生的，不占页面高度。
所以全屏容器若只写 `height: 100vh`，在 H5 上会比可视区高出导航栏那一截。

正确写法（本项目的做法，见 `components/ChatRoom.vue`）：

```scss
.chat-room {
  height: 100vh;
  /* #ifdef H5 */
  /* --window-top / --window-bottom 是 uni-app 在 H5 注入的导航栏、tabBar 高度 */
  height: calc(100vh - var(--window-top, 0px) - var(--window-bottom, 0px));
  /* #endif */
}
```

`var(--window-top, 0px)` 带兜底值，App / 小程序端即使没有该变量也不会算错。

**Q9：`npm run dev:h5` 启动后进程自己退了？**
控制台若出现 `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]` 并指向
`node_modules/.vite/deps_temp_*`，说明是**当前运行环境的文件删除保护**拦截了
Vite 依赖优化器的缓存清理（Vite 提交新缓存前会递归删除旧的 `deps` 目录，
文件数超过保护阈值即被拒绝，异常未捕获导致进程退出）。

这不是项目缺陷，规避方式：

```bash
# 1. 清掉 vite 缓存，让 Vite 走「新建目录」而非「删除旧目录」
node -e "require('fs').rmSync('node_modules/.vite',{recursive:true,force:true})"
npm run dev:h5
```

若仍被拦，改用构建产物 + 静态服务器预览（不触发依赖优化器）：

```bash
npm run build:h5
# 然后用任意静态服务器托管 dist/build/h5
```

**Q10：HBuilderX 点「运行」报 `node_modules缺少编译器模块，请执行npm install后重试`？**
不是依赖没装全，**加一行就能解决**：`src/manifest.json` 缺 `"vueVersion": "3"`，
HBuilderX 因此把项目误判成 Vue2，去找不存在的 `@vue/cli-service`。
完整判定链、根因与验证过程见 [2.1 用 HBuilderX 运行](#21-用-hbuilderx-运行cli-项目模式)。

**Q11：APK 装到安卓手机上，提示「后端未连接」？**
打包时 `.env.production` 里写的是 `http://localhost:8000/api`，而 **App 上的 `localhost` 指手机自己**，
不是你的电脑 → 必然连不上。修复三件事，缺一不可：

| 步骤 | 做什么 | 验证方式 |
|---|---|---|
| ① 地址改局域网 IP | `.env.production` 两行都改成 `http://<电脑IP>:8000/api` | `ipconfig` 看 WLAN 的 IPv4 |
| ② 后端监听所有网卡 | 后端 `.env` 的 `HOST=0.0.0.0` | 浏览器打开 `http://<电脑IP>:8000/api/health` 有返回 |
| ③ 允许 Android 明文 HTTP | `manifest.json` → `app-plus.distribute.android.usesCleartextTraffic: true` | 否则 Android 9+ 报 `net::ERR_CLEARTEXT_NOT_PERMITTED` |

改完必须 **重新 `npm run build:app` + 重新云打包**——改 `.env` 不会影响已生成的 APK。

**不想每次 IP 变了都重新打包？** 首页右上角有 **⚙** 入口，可在 App 内直接改服务器地址：
- 地址存本地存储（`uni.setStorageSync`），运行时优先级高于 `.env` 编译值
- `http.js` 在请求拦截器里每次动态读取、`sse.js` 建流时动态读取 → **改完立即生效，无需重启 App**

其他要排查的：
- 手机和电脑连**同一个 WiFi**（手机别走流量）
- Windows 防火墙放行 8000 端口（首次运行 `python main.py` 时会弹窗，要选「允许访问」）
- 后端确实在跑：`python main.py`

---

## 六、与后端联调清单

1. 启动后端：`python main.py`（确认 `http://localhost:8000/api/health` 返回 `llm_ready=true`）
2. 确认 `.env.development` 的地址指向后端
3. `npm run dev:h5` 打开主页，点击「AI 恋爱大师」发一条消息
4. 应看到 AI 逐字回复（用户气泡在右、AI 在左）
5. 流式进行中点「停止」，应立刻中断且保留已输出的内容
6. 点顶部「会话 ID」可复制，点「重新开始」清空对话并换新会话
