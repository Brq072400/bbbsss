<template>
  <div class="ft-page">
    <div class="page-head">
      <el-button @click="goBack">← 返回社区</el-button>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" class="load-error" />

    <div v-loading="profileLoading">
      <el-empty v-if="!profileLoading && !user" description="用户不存在" :image-size="90" />

      <template v-if="user">
        <!-- 用户信息卡 -->
        <el-card shadow="never" class="panel profile-card">
          <div class="profile">
            <el-avatar :size="72" :src="resolveAsset(user.avatar)">
              {{ firstChar(displayName) }}
            </el-avatar>
            <div class="profile-info">
              <div class="profile-name">
                {{ displayName }}
                <el-tag v-if="user.is_verified" size="small" type="success" effect="plain">已实名</el-tag>
                <el-tag size="small" type="warning" effect="plain">Lv.{{ user.level || 1 }}</el-tag>
                <el-tag v-if="user.is_disabled" size="small" type="danger" effect="plain">已封禁</el-tag>
              </div>
              <div class="profile-account">@{{ user.username || '未知' }}</div>
              <div class="profile-sign">{{ user.signature || '这个人很懒，什么都没留下' }}</div>
              <div class="profile-stats">
                <span><b>{{ user.posts_count ?? postCount }}</b> 动态</span>
                <span><b>{{ user.followers_count ?? followersCount }}</b> 粉丝</span>
                <span><b>{{ user.following_count ?? followingCount }}</b> 关注</span>
                <span v-if="user.city">📍{{ user.city }}</span>
              </div>
            </div>
            <div class="profile-action">
              <el-button
                v-if="!isSelf"
                :type="isFollowing ? 'default' : 'primary'"
                :loading="followLoading"
                @click="handleToggleFollow"
              >
                {{ isFollowing ? '已关注' : '＋ 关注' }}
              </el-button>
              <el-tag v-else type="info" effect="plain">这是你自己</el-tag>
            </div>
          </div>
        </el-card>

        <!-- 动态 / 粉丝 / 关注 切换 -->
        <el-radio-group v-model="tab" class="tab-bar" @change="handleTabChange">
          <el-radio-button value="posts">他的动态</el-radio-button>
          <el-radio-button value="followers">粉丝</el-radio-button>
          <el-radio-button value="following">关注</el-radio-button>
        </el-radio-group>

        <div v-loading="listLoading">
          <!-- 动态列表 -->
          <template v-if="tab === 'posts'">
            <el-empty v-if="!listLoading && posts.length === 0" description="还没有发布过动态" :image-size="80" />
            <el-card v-for="post in posts" :key="post.id" shadow="never" class="panel post-card" @click="goPost(post.id)">
              <div class="post-content">{{ post.content }}</div>
              <div v-if="parseImages(post.images).length > 0" class="post-images">
                <el-image
                  v-for="(url, index) in parseImages(post.images).slice(0, 3)"
                  :key="url + index"
                  :src="resolveAsset(url)"
                  fit="cover"
                  class="post-image"
                />
              </div>
              <div class="post-meta">
                {{ formatTime(post.created_at) }} · ❤️ {{ post.like_count || 0 }} · 💬 {{ post.comment_count || 0 }}
              </div>
            </el-card>
          </template>

          <!-- 粉丝 / 关注列表 -->
          <template v-else>
            <el-empty
              v-if="!listLoading && relationUsers.length === 0"
              :description="tab === 'followers' ? '还没有粉丝' : '还没有关注任何人'"
              :image-size="80"
            />
            <el-card v-for="item in relationUsers" :key="item.id" shadow="never" class="panel user-row">
              <el-avatar :size="40" :src="resolveAsset(item.avatar)" @click="goUser(item.id)">
                {{ firstChar(item.nickname || item.username) }}
              </el-avatar>
              <div class="user-row-info" @click="goUser(item.id)">
                <div class="user-row-name">{{ item.nickname || item.username }}</div>
                <div class="user-row-sign">{{ item.signature || '这个人很懒，什么都没留下' }}</div>
              </div>
              <el-button
                v-if="Number(item.id) !== Number(currentUserId)"
                size="small"
                :type="item.is_following ? 'default' : 'primary'"
                @click.stop="handleFollowRow(item)"
              >
                {{ item.is_following ? '已关注' : '关注' }}
              </el-button>
            </el-card>
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { resolveAsset } from '@/api/request'
import {
  followUser,
  getCommunityUser,
  getUserFollowers,
  getUserFollowing,
  getUserPosts,
  parseImages,
  unfollowUser
} from '@/api/community'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const userId = computed(() => route.params.id || route.query.id || '')
const currentUserId = computed(() => userStore.user?.id ?? null)
const isSelf = computed(() => {
  if (!userId.value || !currentUserId.value) return false
  return Number(userId.value) === Number(currentUserId.value)
})

const user = ref(null)
const profileLoading = ref(false)
const loadError = ref('')
const followLoading = ref(false)
const isFollowing = ref(false)

const displayName = computed(() => {
  const info = user.value || {}
  return info.nickname || info.username || `用户${userId.value}`
})

/* ------------------------------------------------------------------ 统计 */
const postCount = ref(0)
const followersCount = ref(0)
const followingCount = ref(0)

/* ------------------------------------------------------------------ 加载用户信息 */
async function loadUser() {
  if (!userId.value) {
    loadError.value = '缺少用户 ID'
    return
  }
  profileLoading.value = true
  loadError.value = ''
  try {
    const data = await getCommunityUser(userId.value)
    if (!data) {
      user.value = null
      loadError.value = '用户不存在'
      return
    }
    user.value = data
    isFollowing.value = Boolean(data.is_following ?? data.followed ?? false)
  } catch (error) {
    user.value = null
    loadError.value = `加载失败：${error.message}`
  } finally {
    profileLoading.value = false
  }
}

/* ------------------------------------------------------------------ 关注 */
async function handleToggleFollow() {
  followLoading.value = true
  const before = isFollowing.value
  try {
    if (before) {
      await unfollowUser(userId.value)
      isFollowing.value = false
      followersCount.value = Math.max(followersCount.value - 1, 0)
      ElMessage.success('已取消关注')
    } else {
      await followUser(userId.value)
      isFollowing.value = true
      followersCount.value += 1
      ElMessage.success('关注成功')
    }
  } catch (error) {
    isFollowing.value = before
    ElMessage.error(`操作失败：${error.message}`)
  } finally {
    followLoading.value = false
  }
}

async function handleFollowRow(item) {
  const before = Boolean(item.is_following)
  item.is_following = !before
  try {
    if (before) await unfollowUser(item.id)
    else await followUser(item.id)
    ElMessage.success(before ? '已取消关注' : '关注成功')
  } catch (error) {
    item.is_following = before
    ElMessage.error(`操作失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 列表 */
const tab = ref('posts')
const listLoading = ref(false)
const posts = ref([])
const relationUsers = ref([])

async function loadTabContent() {
  if (!userId.value) return
  listLoading.value = true
  try {
    if (tab.value === 'posts') {
      const data = await getUserPosts(userId.value)
      posts.value = Array.isArray(data) ? data : data?.items || []
      postCount.value = Number(data?.total) || posts.value.length
      relationUsers.value = []
    } else {
      const data =
        tab.value === 'followers' ? await getUserFollowers(userId.value) : await getUserFollowing(userId.value)
      relationUsers.value = Array.isArray(data) ? data : data?.items || []
      if (tab.value === 'followers') followersCount.value = Number(data?.total) || relationUsers.value.length
      else followingCount.value = Number(data?.total) || relationUsers.value.length
      posts.value = []
    }
  } catch (error) {
    posts.value = []
    relationUsers.value = []
    ElMessage.error(`列表加载失败：${error.message}`)
  } finally {
    listLoading.value = false
  }
}

function handleTabChange() {
  loadTabContent()
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

function goPost(id) {
  if (!id) return
  router.push(`/community/posts/${id}`)
}

function goUser(id) {
  if (!id || Number(id) === Number(userId.value)) return
  router.push(`/community/users/${id}`)
}

watch(userId, (value, oldValue) => {
  if (value && value !== oldValue) {
    loadUser()
    loadTabContent()
  }
})

onMounted(() => {
  loadUser()
  loadTabContent()
})
</script>

<style scoped>
.page-head {
  margin-bottom: 14px;
}
.load-error {
  margin-bottom: 12px;
}
.panel {
  margin-bottom: 12px;
  background: var(--ft-card);
}
.profile-card :deep(.el-card__body) {
  padding: 18px 20px;
}
.profile {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}
.profile-info {
  flex: 1;
  min-width: 200px;
}
.profile-name {
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.profile-account {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 2px;
}
.profile-sign {
  font-size: 13px;
  color: var(--ft-text-sub);
  margin-top: 8px;
}
.profile-stats {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 13px;
  color: var(--ft-text-sub);
}
.profile-stats b {
  color: var(--ft-primary);
  font-size: 15px;
}
.profile-action {
  flex: 0 0 auto;
}
.tab-bar {
  margin-bottom: 14px;
}
.post-card {
  cursor: pointer;
}
.post-content {
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.post-images {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.post-image {
  width: 90px;
  height: 90px;
  border-radius: var(--ft-radius-sm);
}
.post-meta {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 10px;
}
.user-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-row :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
}
.user-row-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.user-row-name {
  font-size: 14px;
  font-weight: 600;
}
.user-row-sign {
  font-size: 12px;
  color: var(--ft-text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
