import request from './request'

/**
 * 课程相关接口：分类、列表、详情、视频、收藏、评分、评论与点赞
 */

/** 课程分类列表 */
export function getCourseCategories() {
  return request.get('/api/courses/categories')
}

/**
 * 课程列表（分页 + 筛选 + 搜索 + 排序）
 * @param {{page?: number, page_size?: number, category_id?: number|string,
 *          difficulty?: number|string, keyword?: string, sort?: string}} params
 */
export function getCourseList(params) {
  return request.get('/api/courses/list', { params })
}

/**
 * 课程详情
 * @param {number|string} id 课程 ID
 */
export function getCourseDetail(id) {
  return request.get(`/api/courses/${id}`)
}

/**
 * 获取课程视频播放信息（m3u8/mp4 地址）
 * @param {number|string} id 课程 ID
 */
export function getCourseVideo(id) {
  return request.get(`/api/courses/${id}/video`)
}

/**
 * 收藏课程
 * @param {number|string} id 课程 ID
 */
export function favoriteCourse(id) {
  return request.post(`/api/courses/${id}/favorite`)
}

/**
 * 取消收藏课程
 * @param {number|string} id 课程 ID
 */
export function unfavoriteCourse(id) {
  return request.delete(`/api/courses/${id}/favorite`)
}

/** 我收藏的课程列表 */
export function getFavoriteCourses() {
  return request.get('/api/courses/favorites')
}

/**
 * 课程打分（1-5 星）
 * @param {number|string} id 课程 ID
 * @param {{score: number}} data
 */
export function rateCourse(id, data) {
  return request.post(`/api/courses/${id}/rating`, data)
}

/**
 * 获取课程评分信息（平均分、评分人数、我的评分）
 * @param {number|string} id 课程 ID
 */
export function getCourseRating(id) {
  return request.get(`/api/courses/${id}/rating`)
}

/**
 * 发表评论（parent_id 不为空时是回复）
 * @param {number|string} id 课程 ID
 * @param {{content: string, parent_id?: number|string}} data
 */
export function commentCourse(id, data) {
  return request.post(`/api/courses/${id}/comment`, data)
}

/**
 * 评论列表（分页）
 * @param {number|string} id 课程 ID
 * @param {{page?: number, page_size?: number}} params
 */
export function getCourseComments(id, params) {
  return request.get(`/api/courses/${id}/comments`, { params })
}

/**
 * 删除评论
 * @param {number|string} commentId 评论 ID
 */
export function deleteCourseComment(commentId) {
  return request.delete(`/api/courses/comment/${commentId}`)
}

/**
 * 点赞评论
 * @param {number|string} commentId 评论 ID
 */
export function likeCourseComment(commentId) {
  return request.post(`/api/courses/comment/${commentId}/like`)
}

/**
 * 取消点赞评论
 * @param {number|string} commentId 评论 ID
 */
export function unlikeCourseComment(commentId) {
  return request.delete(`/api/courses/comment/${commentId}/like`)
}

/**
 * 相关推荐课程
 * @param {number|string} id 课程 ID
 */
export function getRelatedCourses(id) {
  return request.get(`/api/courses/${id}/related`)
}
