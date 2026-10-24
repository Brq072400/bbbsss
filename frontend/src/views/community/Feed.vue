<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">社区</h2>
        <p class="page-sub">看看大家的训练日常，也记录一下自己的</p>
      </div>
      <el-input
        v-model="userKeyword"
        placeholder="搜索用户昵称 / 用户名"
        clearable
        style="width: 220px"
        @keyup.enter="handleSearchUser"
        @clear="searchResult = []"
      >
        <template #append>
          <el-button @click="handleSearchUser">搜人</el-button>
        </template>
      </el-input>
    </div>

    <!-- 搜索用户结果 -->
    <el-card v-if="searchResult.length > 0" shadow="never" class="panel">
      <template #header><span class="panel-title">用户搜索结果</span></template>
      <div class="user-result">
        <div
          v-for="user in searchResult"
          :key="user.id"
          class="user-chip"
          @click="goUser(user.id)"
        >
          <el-avatar :size="28" :src="resolveAsset(user.avatar)">{{ firstChar(user.nickname || user.username) }}</el-avatar>
          <span class="user-chip-name">{{ user.nickname || user.username }}</span>
        </div>
      </div>
    </el-card>

    <!-- 发布动态 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <span class="panel-title">发布动态</span>
      </template>
      <el-input
        v-model="postForm.content"
        type="textarea"
        :rows="3"
        maxlength="500"
        show-word-limit
        placeholder="今天练了什么？有什么想说的？"
      />

      <!-- 已选图片 -->
      <div v-if="postForm.images.length > 0" class="image-list">
        <div v-for="(url, index) in postForm.images" :key="url" class="image-item">
          <el-image :src="resolveAsset(url)" fit="cover" class="image-thumb" />
          <span class="image-remove" @click="removeImage(index)">×</span>
        </div>
      </div>

      <div class="publish-bar">
        <el-upload
          :show-file-list="false"
          :http-request="handleUpload"
          accept="image/*"
          multiple
        >
          <el-button :loading="uploading" size="small">＋ 添加图片</el-button>
        </el-upload>
        <el-input v-model="postForm.topic" size="small" placeholder="话题，如 增肌日记" style="width: 170px" />
        <el-input v-model="postForm.location" size="small" placeholder="位置" style="width: 150px" />
        <div class="publish-spacer"></div>
        <el-button type="primary" :loading="publishing" @click="handlePublish">发布</el-button>
      </div>
    </el-card>

    <!-- 动态流切换 -->
    <div class="feed-head">
      <el-radio-group v-model="tab" size="default" @change="handleTabChange">
        <el-radio-button value="feed">关注</el-radio-button>
        <el-radio-button value="recommend">推荐</el-radio-button>
        <el-radio-button value="latest">最新</el-radio-button>
      </el-radio-group>
      <el-button size="small" :loading="listLoading" @click="loadPosts(true)">刷新</el-button>
    </div>

    <!-- 动态列表 -->
    <div v-loading="listLoading" class="post-list">
      <el-empty
        v-if="!listLoading && posts.length === 0"
        :description="emptyText"
        :image-size="90"
      />

      <el-card v-for="post in posts" :key="post.id" shadow="never" class="post-card">
        <div class="post-head">
          <el-avatar :size="38" :src="resolveAsset(post.user?.avatar)" @click="goUser(post.user_id)">
            {{ firstChar(authorName(post)) }}
          </el-avatar>
          <div class="post-author">
            <div class="post-author-name" @click="goUser(post.user_id)">
              {{ authorName(post) }}
              <el-tag v-if="post.is_top" size="small" type="danger" effect="plain">置顶</el-tag>
            </div>
            <div class="post-meta">
              {{ formatTime(post.created_at) }}
              <template v-if="post.topic"> · #{{ post.topic }}</template>
              <template v-if="post.location"> · 📍{{ post.location }}</template>
            </div>
          </div>
          <el-button
            v-if="isMine(post)"
            link
            type="danger"
            size="small"
            @click="handleDeletePost(post)"
          >
            删除
          </el-button>
        </div>

        <div class="post-content" @click="goPost(post.id)">{{ post.content }}</div>

        <!-- 图片 -->
        <div v-if="parseImages(post.images).length > 0" class="post-images">
          <el-image
            v-for="(url, index) in parseImages(post.images)"
            :key="url + index"
            :src="resolveAsset(url)"
            :preview-src-list="parseImages(post.images).map(resolveAsset)"
            :initial-index="index"
            fit="cover"
            class="post-image"
            preview-teleported
          />
        </div>

        <div class="post-actions">
          <span
            class="action"
            :class="{ active: isLiked(post) }"
            @click="handleToggleLike(post)"
          >
            {{ isLiked(post) ? '❤️' : '🤍' }} {{ post.like_count || 0 }}
          </span>
          <span class="action" @click="goPost(post.id)">
            💬 {{ post.comment_count || 0 }}
          </span>
          <span class="action muted">👁 {{ post.view_count || 0 }}</span>
          <span class="action muted" @click="goPost(post.id)">查看详情 →</span>
        </div>
      </el-card>

      <div v-if="tab === 'latest' && posts.length > 0" class="load-more">
        <el-button :loading="listLoading" :disabled="posts.length >= total" @click="loadMore">
          {{ posts.length >= total ? '没有更多了' : '加载更多' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { resolveAsset } from '@/api/request'
import {
  createPost,
  deletePost,
  getFeed,
  getPosts,
  getRecommend,
  likePost,
  parseImages,
  searchUsers,
  unlikePost,
  uploadImage
} from '@/api/community'

const router = useRouter()
const userStore = useUserStore()

const currentUserId = computed(() => userStore.user?.id ?? null)

/* ------------------------------------------------------------------ 用户搜索 */
const userKeyword = ref('')
const searchResult = ref([])

async function handleSearchUser() {
  if (!userKeyword.value) {
    ElMessage.warning('请输入要搜索的用户名')
    return
  }
  try {
    const data = await searchUsers(userKeyword.value)
    searchResult.value = Array.isArray(data) ? data : data?.items || []
    if (searchResult.value.length === 0) ElMessage.info('没有找到相关用户')
  } catch (error) {
    searchResult.value = []
    ElMessage.error(`搜索失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 发布动态 */
const postForm = ref({ content: '', images: [], topic: '', location: '' })
const publishing = ref(false)
const uploading = ref(false)

async function handleUpload(options) {
  uploading.value = true
  try {
    const data = await uploadImage(options.file)
    const url = data?.url || data?.data?.url || ''
    if (!url) throw new Error('上传返回中没有 url 字段')
    postForm.value.images.push(url)
    ElMessage.success('图片已上传')
    if (options.onSuccess) options.onSuccess(data)
  } catch (error) {
    ElMessage.error(`图片上传失败：${error.message}`)
    if (options.onError) options.onError(error)
  } finally {
    uploading.value = false
  }
}

function removeImage(index) {
  postForm.value.images.splice(index, 1)
}

async function handlePublish() {
  const content = (postForm.value.content || '').trim()
  if (!content) {
    ElMessage.warning('说点什么再发布吧')
    return
  }
  publishing.value = true
  try {
    await createPost({
      content,
      images: postForm.value.images,
      topic: postForm.value.topic || null,
      location: postForm.value.location || null
    })
    ElMessage.success('发布成功')
    postForm.value = { content: '', images: [], topic: '', location: '' }
    await loadPosts(true)
  } catch (error) {
    ElMessage.error(`发布失败：${error.message}`)
  } finally {
    publishing.value = false
  }
}

/* ------------------------------------------------------------------ 动态列表 */
const tab = ref('feed')
const posts = ref([])
const listLoading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const emptyText = computed(() => {
  if (tab.value === 'feed') return '关注的人还没发动态，去「推荐」或「最新」看看'
  if (tab.value === 'recommend') return '暂无推荐内容'
  return '社区还很安静，发布第一条动态吧'
})

async function loadPosts(reset = false) {
  if (reset) {
    page.value = 1
    posts.value = []
  }
  listLoading.value = true
  try {
    let data
    if (tab.value === 'feed') {
      data = await getFeed()
      posts.value = Array.isArray(data) ? data : data?.items || []
      total.value = posts.value.length
    } else if (tab.value === 'recommend') {
      data = await getRecommend()
      posts.value = Array.isArray(data) ? data : data?.items || []
      total.value = posts.value.length
    } else {
      data = await getPosts({ page: page.value, page_size: pageSize.value })
      const list = Array.isArray(data) ? data : data?.items || []
      posts.value = reset ? list : posts.value.concat(list)
      total.value = Array.isArray(data) ? posts.value.length : Number(data?.total) || posts.value.length
    }
  } catch (error) {
    if (reset) posts.value = []
    total.value = 0
    ElMessage.error(`动态加载失败：${error.message}`)
  } finally {
    listLoading.value = false
  }
}

function loadMore() {
  page.value += 1
  loadPosts(false)
}

function handleTabChange() {
  page.value = 1
  loadPosts(true)
}

/* ------------------------------------------------------------------ 点赞 / 删除 */
async function handleToggleLike(post) {
  if (!post) return
  const liked = isLiked(post)
  const before = Number(post.like_count) || 0
  // 乐观更新
  post.is_liked = !liked
  post.like_count = liked ? Math.max(before - 1, 0) : before + 1
  try {
    if (liked) await unlikePost(post.id)
    else await likePost(post.id)
  } catch (error) {
    // 失败回滚
    post.is_liked = liked
    post.like_count = before
    ElMessage.error(`${liked ? '取消点赞' : '点赞'}失败：${error.message}`)
  }
}

function isLiked(post) {
  if (!post) return false
  return Boolean(post.is_liked ?? post.liked ?? post.has_liked)
}

function isMine(post) {
  if (!post || !currentUserId.value) return false
  return Number(post.user_id) === Number(currentUserId.value)
}

async function handleDeletePost(post) {
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
    await deletePost(post.id)
    ElMessage.success('已删除')
    posts.value = posts.value.filter((item) => item.id !== post.id)
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 工具函数 */
function authorName(post) {
  const user = post?.user || {}
  return user.nickname || user.username || `用户${post?.user_id || ''}`
}

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

function goPost(id) {
  if (!id) return
  router.push(`/community/posts/${id}`)
}

function goUser(id) {
  if (!id) return
  router.push(`/community/users/${id}`)
}

onMounted(() => {
  loadPosts(true)
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
}
.page-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ft-text-sub);
}
.panel {
  margin-bottom: 14px;
  background: var(--ft-card);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
}
.user-result {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ft-border);
  cursor: pointer;
}
.user-chip:hover {
  border-color: rgba(255, 90, 31, 0.5);
}
.user-chip-name {
  font-size: 13px;
}
.image-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.image-item {
  position: relative;
  width: 76px;
  height: 76px;
  border-radius: var(--ft-radius-sm);
  overflow: hidden;
}
.image-thumb {
  width: 100%;
  height: 100%;
}
.image-remove {
  position: absolute;
  right: 2px;
  top: 2px;
  width: 18px;
  height: 18px;
  line-height: 16px;
  text-align: center;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
.publish-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.publish-spacer {
  flex: 1;
}
.feed-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.post-list {
  min-height: 160px;
}
.post-card {
  margin-bottom: 12px;
  background: var(--ft-card);
}
.post-card :deep(.el-card__body) {
  padding: 16px 18px;
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
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
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
  margin: 12px 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--ft-text);
  white-space: pre-wrap;
  word-break: break-word;
  cursor: pointer;
}
.post-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.post-image {
  width: 100%;
  height: 110px;
  border-radius: var(--ft-radius-sm);
  cursor: zoom-in;
}
.post-actions {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-top: 10px;
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
}
.load-more {
  display: flex;
  justify-content: center;
  padding: 8px 0 24px;
}
</style>
