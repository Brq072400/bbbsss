/**
 * 数据统计模块接口（体测 / BMI / 趋势 / 卡路里收支 / 训练频率 / 看板）
 */
import request from '@/api/request'

/** 录入身体数据（每人每天一条，重复提交即覆盖） */
export function createBodyMetric(data) {
  return request.post('/api/stats/body', data)
}

/** 身体数据分页列表 */
export function getBodyMetrics(params) {
  return request.get('/api/stats/body', { params })
}

/** 最新一条身体数据 */
export function getLatestBodyMetric() {
  return request.get('/api/stats/body/latest')
}

/** 删除身体数据 */
export function deleteBodyMetric(id) {
  return request.delete(`/api/stats/body/${id}`)
}

/** 计算 BMI：/api/stats/bmi?weight=&height= */
export function calcBmi(params) {
  return request.get('/api/stats/bmi', { params })
}

/** BMI 历史记录 */
export function getBmiRecords() {
  return request.get('/api/stats/bmi/records')
}

/** 体重趋势：/api/stats/trend/weight?days= */
export function getWeightTrend(params) {
  return request.get('/api/stats/trend/weight', { params })
}

/** 体脂率趋势：/api/stats/trend/body-fat?days= */
export function getBodyFatTrend(params) {
  return request.get('/api/stats/trend/body-fat', { params })
}

/** 某天的卡路里收支：/api/stats/calories/balance?date= */
export function getCaloriesBalance(params) {
  return request.get('/api/stats/calories/balance', { params })
}

/** 某月卡路里收支：/api/stats/calories/balance/month?year=&month= */
export function getCaloriesBalanceMonth(params) {
  return request.get('/api/stats/calories/balance/month', { params })
}

/** 训练频率：/api/stats/frequency?weeks= */
export function getFrequency(params) {
  return request.get('/api/stats/frequency', { params })
}

/** 统计看板总览 */
export function getStatsDashboard() {
  return request.get('/api/stats/dashboard')
}

/** 根据 BMI 数值给出中文等级（与常见国标一致） */
export function bmiLevel(bmi) {
  const value = Number(bmi)
  if (!value || Number.isNaN(value)) return { text: '暂无数据', color: '#8b93a7' }
  if (value < 18.5) return { text: '偏瘦', color: '#38bdf8' }
  if (value < 24) return { text: '正常', color: '#22c55e' }
  if (value < 28) return { text: '超重', color: '#f9b73c' }
  return { text: '肥胖', color: '#f04b4b' }
}
