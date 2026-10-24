/**
 * 饮食模块接口（食物库 + 每日饮食记录 + 摄入统计）
 */
import request from '@/api/request'

/** 食物分页列表：page / page_size / category / keyword */
export function getFoods(params) {
  return request.get('/api/diet/foods', { params })
}

/** 食物分类列表 */
export function getFoodCategories() {
  return request.get('/api/diet/foods/categories')
}

/** 食物详情 */
export function getFoodDetail(id) {
  return request.get(`/api/diet/foods/${id}`)
}

/** 新增自定义食物 */
export function createFood(data) {
  return request.post('/api/diet/foods', data)
}

/** 删除自定义食物 */
export function deleteFood(id) {
  return request.delete(`/api/diet/foods/${id}`)
}

/** 新增饮食记录 */
export function createDietRecord(data) {
  return request.post('/api/diet/records', data)
}

/** 饮食记录列表：date / start_date / end_date / meal_type */
export function getDietRecords(params) {
  return request.get('/api/diet/records', { params })
}

/** 某天的饮食汇总（按三餐分组 + 营养合计） */
export function getDietDay(params) {
  return request.get('/api/diet/records/day', { params })
}

/** 修改饮食记录 */
export function updateDietRecord(id, data) {
  return request.put(`/api/diet/records/${id}`, data)
}

/** 删除饮食记录 */
export function deleteDietRecord(id) {
  return request.delete(`/api/diet/records/${id}`)
}

/** 区间摄入统计 */
export function getDietStats(params) {
  return request.get('/api/diet/stats', { params })
}

/** 三餐枚举（顺序即展示顺序） */
export const MEAL_TYPES = [
  { value: 'breakfast', label: '早餐', icon: '🌅', color: '#f9b73c' },
  { value: 'lunch', label: '午餐', icon: '☀️', color: '#22c55e' },
  { value: 'dinner', label: '晚餐', icon: '🌙', color: '#38bdf8' },
  { value: 'snack', label: '加餐', icon: '🍎', color: '#f04b4b' }
]

/** meal_type 转中文 */
export function mealLabel(value) {
  const hit = MEAL_TYPES.find((item) => item.value === value)
  return hit ? hit.label : value || '其他'
}
