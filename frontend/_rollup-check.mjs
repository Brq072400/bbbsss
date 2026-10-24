/**
 * 纯 Rollup 打包（rollup + @vitejs/plugin-vue + node-resolve），不经过 esbuild，
 * 用于在沙箱内验证整个应用能否被完整打包（等价于 vite build 的 rollup 阶段）。
 * CSS/静态资源做空模块占位，define 用字符串替换模拟 Vite 的 define 插件。
 */
import path from 'node:path'
import fs from 'node:fs'
import { rollup } from 'rollup'
import vue from '@vitejs/plugin-vue'
import { nodeResolve } from '@rollup/plugin-node-resolve'
import commonjs from '@rollup/plugin-commonjs'

const root = process.cwd()
const srcDir = path.join(root, 'src')
const warnings = []

/** 尝试补全扩展名，返回真实存在的文件 */
function resolveWithExt(base) {
  const candidates = [
    base,
    `${base}.js`,
    `${base}.mjs`,
    `${base}.vue`,
    `${base}/index.js`,
    `${base}/index.vue`
  ]
  return candidates.find((p) => {
    try {
      return fs.statSync(p).isFile()
    } catch (e) {
      return false
    }
  })
}

/** @ → src 别名 */
const aliasPlugin = {
  name: 'ft-alias',
  resolveId(source) {
    if (source.startsWith('@/')) return resolveWithExt(path.join(srcDir, source.slice(2))) || null
    return null
  }
}

/** CSS / 静态资源占位 */
const assetPlugin = {
  name: 'ft-assets',
  resolveId(source) {
    // 交给 plugin-vue 自己处理 SFC 子请求（?vue&type=style...）
    if (source.includes('?vue&')) return null
    if (/\.(css|scss|sass|less|styl)(\?.*)?$/.test(source)) return `\0asset:${source}`
    if (/\.(svg|png|jpe?g|gif|webp|woff2?|ttf|eot|ico)(\?.*)?$/.test(source)) return `\0asset:${source}`
    return null
  },
  load(id) {
    if (id.startsWith('\0asset:')) return 'export default {}'
    return null
  },
  // 在 plugin-vue 之前拦下样式子请求，避免把 CSS 当 JS 解析
  transform(code, id) {
    if (id.includes('?vue&type=style')) return 'export default {}'
    if (/\.(css|scss|sass|less|styl)($|\?)/.test(id)) return 'export default {}'
    return null
  }
}

/** 模拟 Vite define 插件 */
const definePlugin = {
  name: 'ft-define',
  transform(code, id) {
    const clean = id.split('?')[0]
    if (!/\.(js|mjs|cjs|vue|ts)$/.test(clean)) return null
    let out = code
    out = out.replaceAll('import.meta.env.VITE_API_BASE', JSON.stringify('http://127.0.0.1:8000'))
    out = out.replace(
      /import\.meta\.env\.(DEV|PROD|SSR|MODE|BASE_URL)/g,
      (m, key) =>
        JSON.stringify(key === 'MODE' ? 'production' : key === 'BASE_URL' ? '/' : key === 'DEV' || key === 'SSR' ? false : true)
    )
    out = out.replaceAll('import.meta.env', '({ VITE_API_BASE: "http://127.0.0.1:8000" })')
    out = out.replaceAll('process.env.NODE_ENV', JSON.stringify('production'))
    out = out.replaceAll('__VUE_OPTIONS_API__', 'true')
    out = out.replaceAll('__VUE_PROD_DEVTOOLS__', 'false')
    out = out.replaceAll('__VUE_PROD_HYDRATION_MISMATCH_DETAILS__', 'false')
    return { code: out, map: null }
  }
}

const started = Date.now()
const bundle = await rollup({
  input: path.join(srcDir, 'main.js'),
  plugins: [
    assetPlugin,
    aliasPlugin,
    vue(),
    nodeResolve({ browser: true, preferBuiltins: false, extensions: ['.mjs', '.js', '.json', '.vue'] }),
    commonjs({ include: /node_modules/, transformMixedEsModules: true }),
    definePlugin
  ],
  onwarn(warning, warn) {
    if (warning.code === 'CIRCULAR_DEPENDENCY') return
    warnings.push(`[${warning.code}] ${warning.message}`)
  }
})

const outDir = 'D:/d/bbbsss/.tmp/rollup-dist'
await bundle.write({
  dir: outDir,
  format: 'es',
  entryFileNames: 'main.js',
  chunkFileNames: 'chunk-[hash].js'
})
await bundle.close()

const elapsed = Date.now() - started
console.log(`✅ Rollup 打包成功，用时 ${elapsed} ms，输出目录：${outDir}`)
if (warnings.length) {
  console.log(`\n⚠️ 告警 ${warnings.length} 条：`)
  warnings.slice(0, 15).forEach((w) => console.log('  - ' + w))
}
