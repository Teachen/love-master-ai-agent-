#!/usr/bin/env node
/**
 * 依赖修复脚本
 *
 * 解决 npm 安装被中断后留下的两类问题（在 Windows + 文件被占用的环境下常见）：
 *
 * 1. `.DELETE.<hash>` 残留文件
 *    npm 删除文件时会先改名成 `xxx.DELETE.<hash>` 再删。若安装过程被打断
 *    （例如 esbuild 的 postinstall 报 EBUSY），最后的清理没跑完，
 *    原文件就永远停在 `.DELETE` 状态，导致 `Cannot find module ...`。
 *    本脚本把它们改回原名。
 *
 * 2. optionalDependencies 的平台包缺失
 *    npm 的已知 bug（npm/cli#4828）会导致 esbuild / rollup 的
 *    `@esbuild/win32-x64`、`@rollup/rollup-win32-x64-msvc` 等平台包漏装，
 *    表现为 `Cannot find module @rollup/rollup-win32-x64-msvc`。
 *    本脚本只做检测并给出修复命令。
 *
 * 用法：
 *   node scripts/fix-deps.js            # 在当前目录修复
 *   node scripts/fix-deps.js <项目目录>
 */
const fs = require('fs')
const path = require('path')

const projectDir = path.resolve(process.argv[2] || '.')
const nm = path.join(projectDir, 'node_modules')

if (!fs.existsSync(nm)) {
  console.error(`未找到 node_modules：${nm}`)
  console.error('请先执行 npm install')
  process.exit(1)
}

/* ---------- 1. 恢复 .DELETE 残留 ---------- */
let restored = 0
let failed = 0
const restoredList = []

function walk(dir) {
  let entries
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true })
  } catch (e) {
    return
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      walk(full)
    } else if (/\.DELETE\.[a-z0-9]+$/i.test(entry.name)) {
      const target = full.replace(/\.DELETE\.[a-z0-9]+$/i, '')
      try {
        fs.renameSync(full, target)
        restored++
        restoredList.push(path.relative(projectDir, target))
      } catch (e) {
        failed++
        console.error(`  ✗ 恢复失败: ${path.relative(projectDir, full)} — ${e.message}`)
      }
    }
  }
}

console.log('扫描 .DELETE 残留文件...')
walk(nm)

if (restored) {
  console.log(`✓ 已恢复 ${restored} 个文件：`)
  restoredList.forEach((f) => console.log(`    ${f}`))
} else {
  console.log('✓ 未发现 .DELETE 残留')
}
if (failed) console.log(`✗ ${failed} 个文件恢复失败（可能被占用，请关闭相关进程后重试）`)

/* ---------- 2. 检查平台特定包 ---------- */
const platformChecks = [
  { pkg: '@esbuild/win32-x64', for: 'esbuild' },
  { pkg: '@rollup/rollup-win32-x64-msvc', for: 'rollup' },
]

const missing = platformChecks.filter((c) => !fs.existsSync(path.join(nm, c.pkg)))

console.log('\n检查平台特定包...')
if (!missing.length) {
  console.log('✓ 平台包齐全')
} else {
  missing.forEach((m) => console.log(`  ✗ 缺失 ${m.pkg}（${m.for} 需要）`))
  console.log('\n修复命令（请用与安装时一致的 node 版本执行）：')
  missing.forEach((m) => {
    const version = readVersion(nm, m.for)
    console.log(`  npm install ${m.pkg}@${version} --no-save`)
  })
}

/* ---------- 3. 结论 ---------- */
function readVersion(nodeModules, name) {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(nodeModules, name, 'package.json'), 'utf8')
    ).version
  } catch (e) {
    return '<version>'
  }
}

console.log('')
if (!restored && !missing.length) {
  console.log('依赖状态正常，无需修复。')
} else {
  console.log('修复完成，建议重新执行构建验证：npm run build:h5')
}
