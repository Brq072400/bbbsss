/**
 * 动作库模块接口
 */
import request from '@/api/request'

/** 动作分类列表 */
export function getExerciseCategories() {
  return request.get('/api/exercises/categories')
}

/** 动作分页列表：page / page_size / category_id / equipment / difficulty / keyword / sort */
export function getExercises(params) {
  return request.get('/api/exercises', { params })
}

/** 关键词搜索动作（供训练记录里远程选择动作使用） */
export function searchExercises(keyword) {
  return request.get('/api/exercises/search', { params: { keyword } })
}

/** 筛选项选项值（器械、难度等） */
export function getExerciseFilterOptions() {
  return request.get('/api/exercises/filter/options')
}

/** 动作详情（讲解 / 发力要点 / 易错提醒） */
export function getExerciseDetail(id) {
  return request.get(`/api/exercises/${id}`)
}

/** 相似动作推荐 */
export function getRelatedExercises(id) {
  return request.get(`/api/exercises/${id}/related`)
}

/** 按分类 slug 分页取动作 */
export function getExercisesByCategory(slug, params) {
  return request.get(`/api/exercises/category/${slug}`, { params })
}

/** 难度 1-5 的可读文案 */
export function difficultyLabel(level) {
  const map = { 1: '入门', 2: '初级', 3: '中级', 4: '高级', 5: '大神' }
  return map[Number(level)] || '未知'
}
