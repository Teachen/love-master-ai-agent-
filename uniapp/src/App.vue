<script setup>
import { onLaunch, onShow } from '@dcloudio/uni-app'

onLaunch(() => {
  console.log('[恋爱大师] App 启动')
})

onShow(() => {
  console.log('[恋爱大师] App 进入前台')
})
</script>

<style>
/* 全局样式（uni-app 会作用到所有页面） */
page {
  background-color: #fff5f7;
  color: #333;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

view,
text,
input,
textarea,
scroll-view {
  box-sizing: border-box;
}

/* 通用：一行省略 */
.ellipsis {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
