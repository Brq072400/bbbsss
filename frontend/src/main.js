import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

// 样式：Element Plus 基础样式 + 官方深色变量 + 项目自定义深色健身风
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '@/styles/main.css'

import App from './App.vue'
import router from './router'

// 全局启用 Element Plus 深色模式（配合 main.css 中的 html.dark 变量覆盖）
document.documentElement.classList.add('dark')

const app = createApp(App)

// 先安装 pinia，保证路由守卫里可以安全使用 store
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
