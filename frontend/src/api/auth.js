import request from './request'

/**
 * 认证相关接口
 * 统一响应外壳由 request.js 拆解，这里拿到的都是真实 data
 */

/**
 * 用户注册
 * @param {{username: string, password: string, nickname?: string, phone?: string, email?: string}} data
 * @returns {Promise<{token: string, token_type: string, expires_in: number, user: object}>}
 */
export function register(data) {
  return request.post('/api/auth/register', data)
}

/**
 * 登录（account 支持用户名 / 手机号）
 * @param {{account: string, password: string}} data
 * @returns {Promise<{token: string, token_type: string, expires_in: number, user: object}>}
 */
export function login(data) {
  return request.post('/api/auth/login', data)
}

/** 退出登录（让后端作废当前 token） */
export function logout() {
  return request.post('/api/auth/logout')
}

/** 获取当前登录用户信息 */
export function getMe() {
  return request.get('/api/auth/me')
}

/**
 * 请求重置密码验证码
 * @param {{phone?: string, email?: string}} data 手机号或邮箱二选一
 */
export function requestPasswordReset(data) {
  return request.post('/api/auth/password/reset/request', data)
}

/**
 * 确认重置密码
 * @param {{code: string, new_password: string, phone?: string, email?: string}} data
 */
export function confirmPasswordReset(data) {
  return request.post('/api/auth/password/reset/confirm', data)
}

/**
 * 修改密码（登录状态）
 * @param {{old_password: string, new_password: string}} data
 */
export function changePassword(data) {
  return request.put('/api/auth/password/change', data)
}

/**
 * 请求绑定手机号验证码
 * @param {{phone: string}} data
 */
export function requestPhoneBind(data) {
  return request.post('/api/auth/phone/bind/request', data)
}

/**
 * 确认绑定手机号
 * @param {{phone: string, code: string}} data
 */
export function confirmPhoneBind(data) {
  return request.post('/api/auth/phone/bind/confirm', data)
}
