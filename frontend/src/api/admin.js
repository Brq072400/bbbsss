/**
 * 后台管理模块接口
 *
 * 注意：管理员令牌和普通用户令牌是两套体系，管理员 token 存在 localStorage 的
 * `fittrack_admin_token` 里。这里**不复用** @/api/request（它的拦截器只认用户 token），
 * 而是单独建一个 axios 实例，保证后台任何页面、任何请求都自带管理员 Bearer 头。
 */
import axios from 'axios'
import { API_BASE } from '@/api/request'

export const ADMIN_TOKEN_KEY = 'fittrack_admin_token'
export const ADMIN_INFO_KEY = 'fittrack_admin_info'

/** 读取管理员 token */
export function getAdminToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY) || ''
}

/** 保存管理员 token 与信息 */
export function saveAdminAuth(token, admin) {
  if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token)
  if (admin) localStorage.setItem(ADMIN_INFO_KEY, JSON.stringify(admin))
}

/** 读取本地保存的管理员信息 */
export function getAdminInfo() {
  try {
    return JSON.parse(localStorage.getItem(ADMIN_INFO_KEY) || 'null')
  } catch (error) {
    return null
  }
}

/** 清空后台登录态 */
export function clearAdminAuth() {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  localStorage.removeItem(ADMIN_INFO_KEY)
}

/** 是否已登录后台 */
export function hasAdminLogin() {
  return Boolean(getAdminToken())
}

// 后台专用 axios 实例：baseURL 与用户端一致（VITE_API_BASE 兜底 127.0.0.1:8000）
const adminRequest = axios.create({ baseURL: API_BASE, timeout: 20000 })

// 请求拦截：自动带上管理员 token
adminRequest.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：拆 {code, message, data} 外壳，0 视为成功；401/40100 视为登录失效
adminRequest.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code === 0) return payload.data
      if (payload.code === 40100) clearAdminAuth()
      return Promise.reject(new Error(payload.message || '请求失败'))
    }
    return payload
  },
  (error) => {
    const status = error && error.response ? error.response.status : 0
    if (status === 401) clearAdminAuth()
    const payload = error && error.response ? error.response.data : null
    let message = '网络异常，请稍后再试'
    if (payload && typeof payload === 'object') {
      message = payload.message || payload.detail || message
    } else if (error && error.message) {
      message = error.message
    }
    if (typeof message !== 'string') message = '请求失败'
    return Promise.reject(new Error(message))
  }
)

/** 管理员登录 → { token, admin } */
export function adminLogin(data) {
  return adminRequest.post('/api/admin/login', data)
}

/** 当前管理员资料 */
export function getAdminProfile() {
  return adminRequest.get('/api/admin/profile')
}

/** 后台数据看板 */
export function getAdminDashboard() {
  return adminRequest.get('/api/admin/dashboard')
}

/** 用户列表：page / page_size / keyword / is_disabled */
export function getAdminUsers(params) {
  return adminRequest.get('/api/admin/users', { params })
}

/** 修改用户资料 */
export function updateAdminUser(id, data) {
  return adminRequest.put(`/api/admin/users/${id}`, data)
}

/** 封禁 / 解封用户：{ disabled: bool } */
export function setUserDisabled(id, disabled) {
  return adminRequest.post(`/api/admin/users/${id}/disable`, { disabled })
}

/** 重置用户密码：{ new_password } */
export function resetUserPassword(id, newPassword) {
  return adminRequest.post(`/api/admin/users/${id}/reset-password`, { new_password: newPassword })
}

/** 删除用户 */
export function deleteAdminUser(id) {
  return adminRequest.delete(`/api/admin/users/${id}`)
}

/** 课程列表 */
export function getAdminCourses(params) {
  return adminRequest.get('/api/admin/courses', { params })
}

/** 新增课程 */
export function createAdminCourse(data) {
  return adminRequest.post('/api/admin/courses', data)
}

/** 编辑课程 */
export function updateAdminCourse(id, data) {
  return adminRequest.put(`/api/admin/courses/${id}`, data)
}

/** 删除课程 */
export function deleteAdminCourse(id) {
  return adminRequest.delete(`/api/admin/courses/${id}`)
}

/** 上架 / 下架课程：{ is_published: bool } */
export function publishAdminCourse(id, isPublished) {
  return adminRequest.post(`/api/admin/courses/${id}/publish`, { is_published: isPublished })
}

/** 课程评论列表：page / page_size / status / course_id */
export function getAdminComments(params) {
  return adminRequest.get('/api/admin/comments', { params })
}

/** 审核评论：action = approve | reject */
export function auditAdminComment(id, action) {
  return adminRequest.post(`/api/admin/comments/${id}/audit`, { action })
}

/** 删除评论 */
export function deleteAdminComment(id) {
  return adminRequest.delete(`/api/admin/comments/${id}`)
}

/** 社区动态列表 */
export function getAdminPosts(params) {
  return adminRequest.get('/api/admin/posts', { params })
}

/** 隐藏 / 恢复动态：{ is_visible: bool } */
export function setAdminPostVisibility(id, isVisible) {
  return adminRequest.post(`/api/admin/posts/${id}/visibility`, { is_visible: isVisible })
}

/** 训练计划列表 */
export function getAdminPlans(params) {
  return adminRequest.get('/api/admin/plans', { params })
}

/** 实名认证列表：page / page_size / status */
export function getAdminRealnames(params) {
  return adminRequest.get('/api/admin/realnames', { params })
}

/** 审核实名认证：action / reject_reason */
export function auditAdminRealname(id, action, rejectReason) {
  return adminRequest.post(`/api/admin/realnames/${id}/audit`, { action, reject_reason: rejectReason })
}

export default adminRequest
