/**
 * 运动记录模块接口
 *
 * 约定：统一使用 @/api/request
 *   - request.get(url, { params }) / request.post(url, body)
 *   - 后端 {code, message, data} 外壳已在 request.js 拦截器中拆掉，这里拿到的就是 data
 */
import request from '@/api/request'

/** 新增一次运动记录（body 里可带 sets 组次明细数组） */
export function createRecord(data) {
  return request.post('/api/records', data)
}

/** 分页查询运动记录列表：page / page_size / start_date / end_date / workout_type */
export function getRecords(params) {
  return request.get('/api/records', { params })
}

/** 运动记录详情（含动作组次明细） */
export function getRecordDetail(id) {
  return request.get(`/api/records/${id}`)
}

/** 修改运动记录 */
export function updateRecord(id, data) {
  return request.put(`/api/records/${id}`, data)
}

/** 删除运动记录 */
export function deleteRecord(id) {
  return request.delete(`/api/records/${id}`)
}

/** 月度统计：/api/records/statistics/monthly?year=&month= */
export function getMonthlyStatistics(params) {
  return request.get('/api/records/statistics/monthly', { params })
}

/** 周统计：/api/records/statistics/weekly?weeks= */
export function getWeeklyStatistics(params) {
  return request.get('/api/records/statistics/weekly', { params })
}

/** 总览统计（累计训练次数、时长、消耗等） */
export function getSummaryStatistics() {
  return request.get('/api/records/statistics/summary')
}

/** 最近 N 天趋势：/api/records/statistics/trend?days= */
export function getTrendStatistics(params) {
  return request.get('/api/records/statistics/trend', { params })
}

/** 训练类型枚举（前端下拉用，和后端 workout_type 字段取值一致） */
export const WORKOUT_TYPES = [
  { value: 'strength', label: '力量训练', color: '#ff5a1f' },
  { value: 'cardio', label: '有氧训练', color: '#38bdf8' },
  { value: 'stretch', label: '拉伸放松', color: '#22c55e' },
  { value: 'hiit', label: 'HIIT', color: '#f9b73c' },
  { value: 'yoga', label: '瑜伽', color: '#a78bfa' }
]

/** 根据 value 取训练类型中文名 */
export function workoutTypeLabel(value) {
  const hit = WORKOUT_TYPES.find((item) => item.value === value)
  return hit ? hit.label : value || '训练'
}

/** 根据 value 取训练类型标签色 */
export function workoutTypeColor(value) {
  const hit = WORKOUT_TYPES.find((item) => item.value === value)
  return hit ? hit.color : '#8b93a7'
}
