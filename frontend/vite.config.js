import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 6 配置：固定 5173 端口，直接请求 http://127.0.0.1:8000（后端已开启 CORS，因此不需要配置 proxy）
export default defineConfig({
  plugins: [vue()],
  resolve: {
    // 用 @ 指向 src，方便深层目录的引入
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
    // npm 扁平安装无需解析软链接，跳过 realpath 解析（Windows 上更快，也避免触发 net use 探测）
    preserveSymlinks: true
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
    open: false
  },
  build: {
    outDir: 'dist',
    // 生产构建不生成 sourcemap，减小产物体积
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // 简单分包：把大依赖拆开，避免单个 chunk 过大
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
            return 'vendor'
          }
        }
      }
    }
  }
})
