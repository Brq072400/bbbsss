import request from './request'

/**
 * 训练计划相关接口：计划 CRUD、模板库、分享、收藏、打卡、统计、提醒
 */

/**
 * 发布（新建）计划
 * @param {{name: string, description?: string, goal?: string, cycle_type?: string,
 *          cycle_days?: number, cover?: string, is_public?: boolean, items?: Array<object>}} data
 */
export function publishPlan(data) {
  return request.post('/api/plans/publish', data)
}

/**
 * 我的计划列表（分页）
 * @param {{page?: number, page_size?: number, status?: string}} params status: active/archived
 */
export function getMyPlans(params) {
  return request.get('/api/plans/my', { params })
}

/**
 * 计划详情
 * @param {number|string} id 计划 ID
 */
export function getPlanDetail(id) {
  return request.get(`/api/plans/${id}`)
}

/**
 * 更新计划
 * @param {number|string} id
 * @param {object} data
 */
export function updatePlan(id, data) {
  return request.put(`/api/plans/${id}`, data)
}

/**
 * 删除计划
 * @param {number|string} id
 */
export function deletePlan(id) {
  return request.delete(`/api/plans/${id}`)
}

/**
 * 为计划新增一条动作明细
 * @param {number|string} id 计划 ID
 * @param {{exercise_id?: number, day_index?: number, sort_order?: number, sets?: number,
 *          reps?: number, weight?: number, rest_seconds?: number, duration_min?: number, note?: string}} data
 */
export function addPlanItem(id, data) {
  return request.post(`/api/plans/${id}/item`, data)
}

/**
 * 修改计划中的动作明细
 * @param {number|string} id 计划 ID
 * @param {number|string} itemId 明细 ID
 * @param {object} data
 */
export function updatePlanItem(id, itemId, data) {
  return request.put(`/api/plans/${id}/item/${itemId}`, data)
}

/**
 * 删除计划中的动作明细
 * @param {number|string} id 计划 ID
 * @param {number|string} itemId 明细 ID
 */
export function deletePlanItem(id, itemId) {
  return request.delete(`/api/plans/${id}/item/${itemId}`)
}

/**
 * 模板库列表（分页 + 筛选）
 * @param {{page?: number, page_size?: number, category?: string, goal?: string, difficulty?: number}} params
 */
export function getTemplates(params) {
  return request.get('/api/plans/templates', { params })
}

/**
 * 模板详情
 * @param {number|string} id 模板 ID
 */
export function getTemplateDetail(id) {
  return request.get(`/api/plans/templates/${id}`)
}

/**
 * 使用模板生成我的计划
 * @param {number|string} id 模板 ID
 * @param {string} [name] 可选的自定义计划名（后端以 query 参数接收）
 */
export function useTemplate(id, name) {
  return request.post(`/api/plans/templates/${id}/use`, null, {
    params: name ? { name } : {}
  })
}

/**
 * 生成计划分享码
 * @param {number|string} id 计划 ID
 * @param {{expires_hours?: number}} [data] 可选有效期（小时），不传表示永久
 */
export function sharePlan(id, data) {
  return request.post(`/api/plans/${id}/share`, data || {})
}

/**
 * 通过分享码查看计划（无需登录也能看）
 * @param {string} code 分享码
 */
export function getSharedPlan(code) {
  return request.get(`/api/plans/share/${code}`)
}

/**
 * 通过分享码导入计划到自己的账号
 * @param {string} code 分享码
 */
export function importSharedPlan(code) {
  return request.post(`/api/plans/share/${code}/import`)
}

/**
 * 收藏计划
 * @param {number|string} id 计划 ID
 */
export function favoritePlan(id) {
  return request.post(`/api/plans/${id}/favorite`)
}

/**
 * 取消收藏计划
 * @param {number|string} id 计划 ID
 */
export function unfavoritePlan(id) {
  return request.delete(`/api/plans/${id}/favorite`)
}

/** 我收藏的计划列表 */
export function getFavoritePlans() {
  return request.get('/api/plans/favorites')
}

/**
 * 计划打卡
 * @param {number|string} id 计划 ID
 * @param {{day_index?: number, note?: string}} data
 */
export function checkinPlan(id, data) {
  return request.post(`/api/plans/${id}/checkin`, data || {})
}

/**
 * 计划的打卡记录
 * @param {number|string} id 计划 ID
 */
export function getPlanCheckinRecords(id) {
  return request.get(`/api/plans/${id}/checkin/records`)
}

/**
 * 计划的完成统计（完成天数、连续天数、完成率等）
 * @param {number|string} id 计划 ID
 */
export function getPlanStats(id) {
  return request.get(`/api/plans/${id}/stats`)
}

/** 今日需要执行的计划 / 打卡情况 */
export function getTodayCheckin() {
  return request.get('/api/plans/checkin/today')
}

/**
 * 新增计划提醒
 * @param {number|string} id 计划 ID
 * @param {{remind_time: string, weekdays?: string, enabled?: boolean}} data
 */
export function createPlanReminder(id, data) {
  return request.post(`/api/plans/${id}/reminder`, data)
}

/**
 * 查询计划提醒列表
 * @param {number|string} id 计划 ID
 */
export function getPlanReminders(id) {
  return request.get(`/api/plans/${id}/reminder`)
}

/**
 * 删除计划提醒
 * @param {number|string} id 计划 ID
 * @param {number|string} rid 提醒 ID
 */
export function deletePlanReminder(id, rid) {
  return request.delete(`/api/plans/${id}/reminder/${rid}`)
}
