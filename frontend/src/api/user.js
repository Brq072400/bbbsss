import request from './request'

/**
 * 用户中心相关接口：资料、头像、等级、签到、通知、实名认证
 */

/** 获取个人资料（含等级、签到概况） */
export function getProfile() {
  return request.get('/api/users/profile')
}

/**
 * 更新个人资料
 * @param {{nickname?: string, gender?: number, birthday?: string, height?: number,
 *          target_weight?: number, signature?: string, city?: string, email?: string}} data
 */
export function updateProfile(data) {
  return request.put('/api/users/profile', data)
}

/**
 * 上传头像（multipart，字段名 file）
 * @param {File} file 图片文件
 * @returns {Promise<{url: string, avatar: string, filename: string, size: number}>}
 */
export function uploadAvatar(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/api/users/avatar', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/** 获取当前用户等级详情（积分、进度、下一等级） */
export function getLevel() {
  return request.get('/api/users/level')
}

/** 获取等级规则（各等级门槛 + 签到积分规则） */
export function getLevelRules() {
  return request.get('/api/users/level/rules')
}

/** 每日签到 */
export function checkin() {
  return request.post('/api/users/checkin')
}

/**
 * 获取签到日历
 * @param {{year: number, month: number}} params
 */
export function getCheckinCalendar(params) {
  return request.get('/api/users/checkin/calendar', { params })
}

/** 获取签到统计（连续天数 / 累计天数 / 本月天数） */
export function getCheckinStats() {
  return request.get('/api/users/checkin/stats')
}

/**
 * 获取通知列表（分页）
 * @param {{page?: number, page_size?: number, only_unread?: boolean}} params
 */
export function getNotifications(params) {
  return request.get('/api/users/notifications', { params })
}

/**
 * 标记单条通知为已读
 * @param {number|string} id 通知 ID
 */
export function readNotification(id) {
  return request.post(`/api/users/notifications/${id}/read`)
}

/** 全部标记为已读 */
export function readAllNotifications() {
  return request.post('/api/users/notifications/read-all')
}

/**
 * 删除通知
 * @param {number|string} id 通知 ID
 */
export function deleteNotification(id) {
  return request.delete(`/api/users/notifications/${id}`)
}

/** 获取未读通知数量 */
export function getUnreadCount() {
  return request.get('/api/users/notifications/unread-count')
}

/**
 * 提交实名认证
 * @param {{real_name: string, id_card: string}} data
 */
export function submitRealName(data) {
  return request.post('/api/users/realname', data)
}

/** 查询实名认证状态 */
export function getRealName() {
  return request.get('/api/users/realname')
}

/**
 * 重新提交实名认证（被驳回后）
 * @param {{real_name: string, id_card: string}} data
 */
export function resubmitRealName(data) {
  return request.post('/api/users/realname/resubmit', data)
}
