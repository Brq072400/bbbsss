<template>
  <div class="ft-page">
    <div class="page-head">
      <el-button @click="goBack">← 返回社区</el-button>
      <el-button :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" class="load-error" />

    <div v-loading="loading">
      <el-empty v-if="!loading && !post" description="动态不存在或已被删除" :image-size="90" />

      <template v-if="post">
        <!-- 动态正文 -->
        <el-card shadow="never" class="panel">
          <div class="post-head">
            <el-avatar :size="42" :src="resolveAsset(post.user?.avatar)" @click="goUser(post.user_id)">
              {{ firstChar(authorName) }}
            </el-avatar>
            <div class="post-author">
              <div class="post-author-name" @click="goUser(post.user_id)">{{ authorName }}</div>
              <div class="post-meta">
                {{ formatTime(post.created_at) }}
                <template v-if="post.topic"> · #{{ post.topic }}</template>
                <template v-if="post.location"> · 📍{{ post.location }}</template>
              </div>
            </div>
            <el-button v-if="isMine" link type="danger" size="small" @click="handleDeletePost">删除动态</el-button>
          </div>

          <div class="post-content">{{ post.content }}</div>

          <div v-if="images.length > 0" class="post-images">
            <el-image
              v-for="(url, index) in images"
              :key="url + index"
              :src="resolveAsset(url)"
              :preview-src-list="images.map(resolveAsset)"
              :initial-index="index"
              fit="cover"
              class="post-image"
              preview-teleported
            />
          </div>

          <div class="post-actions">
            <span class="action" :class="{ active: liked }" @click="handleToggleLike">
              {{ liked ? '❤️' : '🤍' }} {{ post.like_count || 0 }}
            </span>
            <span class="action muted">💬 {{ post.comment_count || commentsTotal }}</span>
            <span class="action muted">👁 {{ post.view_count || 0 }}</span>
          </div>
        </el-card>

        <!-- 评论 -->
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">评论（{{ commentsTotal }}）</span>
              <span v-if="replyTarget" class="reply-hint">
                正在回复 {{ replyTarget.userName }}
                <el-button link type="info" size="small" @click="cancelReply">取消</el-button>
              </span>
            </div>
          </template>

          <!-- 发表评论 -->
          <div class="comment-form">
            <el-input
              v-model="commentContent"
              type="textarea"
              :rows="2"
              maxlength="300"
              show-word-limit
              :placeholder="replyTarget ? `回复 ${replyTarget.userName}：` : '说点什么鼓励一下…'"
            />
            <div class="comment-actions">
              <el-button type="primary" size="small" :loading="submitting" @click="handleSubmitComment">
                {{ replyTarget ? '发表回复' : '发表评论' }}
              </el-button>
            </div>
          </div>

          <!-- 评论列表 -->
          <el-empty v-if="!commentsLoading && comments.length === 0" description="还没有评论，来抢沙发" :image-size="70" />

          <div v-loading="commentsLoading" class="comment-list">
            <div v-for="comment in comments" :key="comment.id" class="comment-item">
              <el-avatar :size="32" :src="resolveAsset(comment.user?.avatar)" @click="goUser(comment.user_id)">
                {{ firstChar(commentUserName(comment)) }}
              </el-avatar>
              <div class="comment-main">
                <div class="comment-head">
                  <span class="comment-name" @click="goUser(comment.user_id)">{{ commentUserName(comment) }}</span>
                  <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
                </div>
                <div class="comment-text">{{ comment.content }}</div>
                <div class="comment-ops">
                  <el-button link type="primary" size="small" @click="startReply(comment)">回复</el-button>
                  <el-button
                    v-if="isCommentMine(comment)"
                    link
                    type="danger"
                    size="small"
                    @click="handleDeleteComment(comment)"
                  >
                    删除
                  </el-button>
                </div>

                <!-- 二级回复 -->
                <div v-if="comment.replies && comment.replies.length > 0" class="reply-list">
                  <div v-for="reply in comment.replies" :key="reply.id" class="reply-item">
                    <el-avatar :size="24" :src="resolveAsset(reply.user?.avatar)">
                      {{ firstChar(commentUserName(reply)) }}
                    </el-avatar>
                    <div class="reply-main">
                      <div class="comment-head">
                        <span class="comment-name" @click="goUser(reply.user_id)">{{ commentUserName(reply) }}</span>
                        <span class="comment-time">{{ formatTime(reply.created_at) }}</span>
                      </div>
                      <div class="comment-text">{{ reply.content }}</div>
                      <div class="comment-ops">
                        <el-button link type="primary" size="small" @click="startReply(comment, reply)">回复</el-button>
                        <el-button
                          v-if="isCommentMine(reply)"
                          link
                          type="danger"
                          size="small"
                          @click="handleDeleteComment(reply)"
                        >
                          删除
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { resolveAsset } from '@/api/request'
import {
  createComment,
  deleteComment,
  deletePost,
  getComments,
  getPostDetail,
  likePost,
  parseImages,
  unlikePost
} from '@/api/community'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const postId = computed(() => route.params.id || route.query.id || '')
const currentUserId = computed(() => userStore.user?.id ?? null)

const post = ref(null)
const loading = ref(false)
const loadError = ref('')
const liked = ref(false)
const images = computed(() => parseImages(post.value?.images))

const isMine = computed(() => {
  if (!post.value || !currentUserId.value) return false
  return Number(post.value.user_id) === Number(currentUserId.value)
})

const authorName = computed(() => {
  const user = post.value?.user || {}
  return user.nickname || user.username || `用户${post.value?.user_id || ''}`
})

/* ------------------------------------------------------------------ 加载 */
async function loadPost() {
  if (!postId.value) {
    loadError.value = '缺少动态 ID'
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const data = await getPostDetail(postId.value)
    if (!data) {
      post.value = null
      loadError.value = '动态不存在或已被删除'
      return
    }
    post.value = data
    liked.value = Boolean(data.is_liked ?? data.liked ?? data.has_liked)
  } catch (error) {
    post.value = null
    loadError.value = `加载失败：${error.message}`
  } finally {
    loading.value = false
  }
}

/* ------------------------------------------------------------------ 评论 */
const comments = ref([])
const commentsLoading = ref(false)
const commentsTotal = ref(0)
const commentContent = ref('')
const submitting = ref(false)
const replyTarget = ref(null)

function commentUserName(comment) {
  const user = comment?.user || {}
  return user.nickname || user.username || `用户${comment?.user_id || ''}`
}

/** 把评论列表整理成「父评论 + replies」结构 */
function buildTree(rawList) {
  const list = rawList.map((item) => ({
    ...item,
    replies: Array.isArray(item.replies) ? [...item.replies] : Array.isArray(item.children) ? [...item.children] : []
  }))
  const hasNested = list.some((item) => item.replies.length > 0)
  if (hasNested) {
    return list.filter((item) => !item.parent_id)
  }
  const byId = new Map(list.map((item) => [item.id, item]))
  const roots = []
  list.forEach((item) => {
    const parent = item.parent_id ? byId.get(item.parent_id) : null
    if (parent && parent !== item) parent.replies.push(item)
    else roots.push(item)
  })
  return roots
}

async function loadComments() {
  if (!postId.value) return
  commentsLoading.value = true
  try {
    const data = await getComments(postId.value)
    const list = Array.isArray(data) ? data : data?.items || data?.comments || []
    comments.value = buildTree(list)
    commentsTotal.value = Number(data?.total) || list.length
  } catch (error) {
    comments.value = []
    commentsTotal.value = 0
    ElMessage.error(`评论加载失败：${error.message}`)
  } finally {
    commentsLoading.value = false
  }
}

function startReply(parentComment, targetComment) {
  const target = targetComment || parentComment
  replyTarget.value = {
    parentId: parentComment.id,
    userName: commentUserName(target)
  }
}

function cancelReply() {
  replyTarget.value = null
}

async function handleSubmitComment() {
  const content = (commentContent.value || '').trim()
  if (!content) {
    ElMessage.warning('请先输入评论内容')
    return
  }
  submitting.value = true
  try {
    const payload = { content }
    if (replyTarget.value?.parentId) payload.parent_id = replyTarget.value.parentId
    await createComment(postId.value, payload)
    ElMessage.success(replyTarget.value ? '回复成功' : '评论成功')
    commentContent.value = ''
    replyTarget.value = null
    await loadComments()
    if (post.value) post.value.comment_count = commentsTotal.value
  } catch (error) {
    ElMessage.error(`评论失败：${error.message}`)
  } finally {
    submitting.value = false
  }
}

function isCommentMine(comment) {
  if (!comment || !currentUserId.value) return false
  return Number(comment.user_id) === Number(currentUserId.value)
}

async function handleDeleteComment(comment) {
  try {
    await ElMessageBox.confirm('确定删除这条评论吗？', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteComment(comment.id)
    ElMessage.success('已删除')
    await loadComments()
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 点赞 / 删除动态 */
async function handleToggleLike() {
  if (!post.value) return
  const before = Number(post.value.like_count) || 0
  const wasLiked = liked.value
  liked.value = !wasLiked
  post.value.like_count = wasLiked ? Math.max(before - 1, 0) : before + 1
  try {
    if (wasLiked) await unlikePost(post.value.id)
    else await likePost(post.value.id)
  } catch (error) {
    liked.value = wasLiked
    post.value.like_count = before
    ElMessage.error(`${wasLiked ? '取消点赞' : '点赞'}失败：${error.message}`)
  }
}

async function handleDeletePost() {
  try {
    await ElMessageBox.confirm('确定删除这条动态吗？删除后不可恢复。', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deletePost(post.value.id)
    ElMessage.success('已删除')
    router.push('/community')
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 工具 */
function firstChar(name) {
  if (!name) return 'U'
  return String(name).slice(0, 1)
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}`
}

function goBack() {
  router.push('/community')
}

function goUser(id) {
  if (!id) return
  router.push(`/community/users/${id}`)
}

function loadAll() {
  loadPost()
  loadComments()
}

onMounted(loadAll)
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.load-error {
  margin-bottom: 12px;
}
.panel {
  margin-bottom: 12px;
  background: var(--ft-card);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
}
.reply-hint {
  font-size: 12px;
  color: var(--ft-primary);
}
.post-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.post-author {
  flex: 1;
  min-width: 0;
}
.post-author-name {
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.post-author-name:hover {
  color: var(--ft-primary);
}
.post-meta {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 2px;
}
.post-content {
  margin: 14px 0;
  font-size: 15px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
.post-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.post-image {
  width: 100%;
  height: 120px;
  border-radius: var(--ft-radius-sm);
  cursor: zoom-in;
}
.post-actions {
  display: flex;
  align-items: center;
  gap: 22px;
  padding-top: 12px;
  border-top: 1px solid var(--ft-border);
}
.action {
  font-size: 13px;
  color: var(--ft-text-sub);
  cursor: pointer;
  user-select: none;
}
.action:hover {
  color: var(--ft-primary);
}
.action.active {
  color: #f04b4b;
}
.action.muted {
  color: var(--ft-text-dim);
  cursor: default;
}
.comment-form {
  margin-bottom: 16px;
}
.comment-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
.comment-list {
  min-height: 60px;
}
.comment-item {
  display: flex;
  gap: 10px;
  padding: 12px 0;
  border-top: 1px solid var(--ft-border);
}
.comment-item:first-child {
  border-top: none;
}
.comment-main {
  flex: 1;
  min-width: 0;
}
.comment-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.comment-name {
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.comment-name:hover {
  color: var(--ft-primary);
}
.comment-time {
  font-size: 12px;
  color: var(--ft-text-dim);
}
.comment-text {
  font-size: 14px;
  line-height: 1.7;
  margin-top: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
.comment-ops {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}
.reply-list {
  margin-top: 10px;
  padding-left: 12px;
  border-left: 2px solid var(--ft-border);
}
.reply-item {
  display: flex;
  gap: 8px;
  padding: 8px 0;
}
.reply-main {
  flex: 1;
  min-width: 0;
}
</style>
