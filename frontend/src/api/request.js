import axios from 'axios'
import { ElMessage } from 'element-plus'

/** localStorage 中存放 token 的键名（与后端约定一致） */
export const TOKEN_KEY = 'fittrack_token'

/** 后端基础地址：优先读取 .env 中的 VITE_API_BASE，兜底 127.0.0.1:8000 */
export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(/\/+$/, '')

/** 读取本地 token */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

/** 写入本地 token */
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
}

/** 清空本地 token */
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** 是否正在跳登录页，避免并发请求重复跳转 / 重复弹提示 */
let redirecting = false

/**
 * 登录失效统一处理：清掉 token 并跳转登录页（保留当前地址便于登录后回跳）
 * 注意：这里不 import router，避免 request -> router -> views -> api 的循环依赖
 */
function redirectToLogin(message) {
  clearToken()
  if (redirecting) return
  const path = window.location.pathname + window.location.search
  if (path.startsWith('/login')) return
  redirecting = true
  if (message) ElMessage.warning(message)
  window.location.replace(`/login?redirect=${encodeURIComponent(path)}`)
}

/**
 * 把后端返回的相对资源路径（如 /uploads/avatars/a.png）拼成可访问的绝对地址
 * 已经是 http(s)/data/blob 开头的地址原样返回
 * @param {string} url 原始地址
 * @returns {string} 可访问地址
 */
export function resolveAsset(url) {
  if (!url) return ''
  if (/^(https?:)?\/\//i.test(url) || /^(data|blob):/i.test(url)) return url
  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`
}

/** 把 FastAPI 的 422 校验错误（detail 数组）压成一句可读文案 */
function formatValidationDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .slice(0, 3)
      .map((item) => {
        const loc = Array.isArray(item?.loc) ? item.loc.filter((p) => p !== 'body').join('.') : ''
        return loc ? `${loc}: ${item.msg}` : item.msg
      })
      .join('；')
  }
  return typeof detail === 'string' ? detail : ''
}

/** axios 实例：统一 baseURL、超时、token 与响应外壳拆解 */
const request = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' }
})

// ---------------- 请求拦截器：自动附加 Bearer token ----------------
request.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ---------------- 响应拦截器：拆 { code, message, data } 外壳 ----------------
request.interceptors.response.use(
  (response) => {
    // 文件流（如下载）直接返回原始数据
    if (response.config?.responseType === 'blob') return response.data

    const body = response.data
    // 非统一外壳（例如静态文件、第三方接口）时原样返回
    if (!body || typeof body !== 'object' || !Object.prototype.hasOwnProperty.call(body, 'code')) {
      return body
    }
    // code === 0 表示业务成功，直接返回真实 data
    if (body.code === 0) return body.data

    const message = body.message || '请求失败'
    if (body.code === 401) {
      redirectToLogin('登录状态已失效，请重新登录')
    } else if (!response.config?.silent) {
      ElMessage.error(message)
    }
    const err = new Error(message)
    err.code = body.code
    err.data = body.data
    return Promise.reject(err)
  },
  (error) => {
    // 请求被主动取消时静默
    if (axios.isCancel?.(error)) return Promise.reject(error)

    const response = error.response
    const status = response?.status
    const payload = response?.data
    let message = payload?.message || payload?.detail || error.message || '网络请求失败'
    message = formatValidationDetail(message) || '网络请求异常'

    if (status === 401) {
      redirectToLogin('登录状态已失效，请重新登录')
    } else if (status === 403) {
      message = message || '没有权限执行该操作'
      ElMessage.error(message)
    } else if (status === 404) {
      ElMessage.error(message || '接口不存在')
    } else if (status === 422) {
      ElMessage.error(message || '提交的内容不符合要求')
    } else if (status >= 500) {
      ElMessage.error(`服务端异常（${status}），请稍后再试`)
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请检查网络后重试')
    } else if (!error.response) {
      ElMessage.error('无法连接服务器，请确认后端已启动')
    } else {
      ElMessage.error(message)
    }

    const err = new Error(message)
    err.status = status
    err.data = payload
    return Promise.reject(err)
  }
)

export default request
