/**
 * 社区模块接口（动态 / 点赞 / 评论 / 关注 / 用户主页 / 图片上传）
 */
import request from '@/api/request'

/** 发布动态：content, images(URL 数组), topic, location */
export function createPost(data) {
  return request.post('/api/community/posts', data)
}

/** 动态分页列表：page / page_size / sort */
export function getPosts(params) {
  return request.get('/api/community/posts', { params })
}

/** 动态详情 */
export function getPostDetail(id) {
  return request.get(`/api/community/posts/${id}`)
}

/** 删除自己的动态 */
export function deletePost(id) {
  return request.delete(`/api/community/posts/${id}`)
}

/** 关注流 */
export function getFeed() {
  return request.get('/api/community/feed')
}

/** 推荐流 */
export function getRecommend() {
  return request.get('/api/community/recommend')
}

/** 点赞 */
export function likePost(id) {
  return request.post(`/api/community/posts/${id}/like`)
}

/** 取消点赞 */
export function unlikePost(id) {
  return request.delete(`/api/community/posts/${id}/like`)
}

/** 评论动态：content, parent_id? */
export function createComment(id, data) {
  return request.post(`/api/community/posts/${id}/comment`, data)
}

/** 动态评论列表 */
export function getComments(id) {
  return request.get(`/api/community/posts/${id}/comments`)
}

/** 删除评论 */
export function deleteComment(commentId) {
  return request.delete(`/api/community/comment/${commentId}`)
}

/** 关注用户 */
export function followUser(userId) {
  return request.post(`/api/community/users/${userId}/follow`)
}

/** 取消关注 */
export function unfollowUser(userId) {
  return request.delete(`/api/community/users/${userId}/follow`)
}

/** 用户主页信息 */
export function getCommunityUser(userId) {
  return request.get(`/api/community/users/${userId}`)
}

/** 某用户发布的动态 */
export function getUserPosts(userId) {
  return request.get(`/api/community/users/${userId}/posts`)
}

/** 某用户的粉丝 */
export function getUserFollowers(userId) {
  return request.get(`/api/community/users/${userId}/followers`)
}

/** 某用户关注的人 */
export function getUserFollowing(userId) {
  return request.get(`/api/community/users/${userId}/following`)
}

/** 搜索用户：/api/community/search/users?keyword= */
export function searchUsers(keyword) {
  return request.get('/api/community/search/users', { params: { keyword } })
}

/**
 * 上传一张图片，返回 { url }
 * 后端字段名固定为 file，这里用 FormData 走 multipart
 */
export function uploadImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/api/uploads/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/** 把后端 "a.jpg,b.jpg" 形式的 images 字段拆成数组 */
export function parseImages(images) {
  if (!images) return []
  if (Array.isArray(images)) return images.filter(Boolean)
  return String(images)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}
