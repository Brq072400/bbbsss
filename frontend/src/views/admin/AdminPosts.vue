<template>
  <div class="admin-shell">
    <header class="admin-nav">
      <div class="admin-brand">🏋️ FitTrack 后台</div>
      <nav class="admin-menu">
        <router-link to="/admin/dashboard">数据看板</router-link>
        <router-link to="/admin/users">用户管理</router-link>
        <router-link to="/admin/courses">课程管理</router-link>
        <router-link to="/admin/comments">评论审核</router-link>
        <router-link to="/admin/posts">动态管理</router-link>
        <router-link to="/admin/realnames">实名审核</router-link>
      </nav>
      <div class="admin-user">
        <span class="admin-name">{{ adminName }}</span>
        <el-button link type="danger" size="small" @click="handleLogout">退出</el-button>
      </div>
    </header>

    <main class="admin-body">
      <div class="page-head">
        <div>
          <h2 class="page-title">动态管理</h2>
          <p class="page-sub">查看社区动态，隐藏不合规内容或恢复显示</p>
        </div>
        <el-button :loading="loading" @click="loadPosts">刷新</el-button>
      </div>

      <el-card shadow="never" class="panel">
        <el-table v-loading="loading" :data="posts" size="small" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="发布者" width="140">
            <template #default="{ row }">
              {{ row.user?.nickname || row.user?.username || `用户${row.user_id || ''}` }}
            </template>
          </el-table-column>
          <el-table-column label="内容" min-width="300">
            <template #default="{ row }">
              <div class="post-content">{{ row.content }}</div>
              <div v-if="row.topic" class="post-topic">#{{ row.topic }}</div>
            </template>
          </el-table-column>
          <el-table-column label="互动" width="130">
            <template #default="{ row }">
              ❤️ {{ row.like_count || 0 }} · 💬 {{ row.comment_count || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="可见性" width="100">
            <template #default="{ row }">
              <el-tag :type="isVisible(row) ? 'success' : 'danger'" size="small" effect="plain">
                {{ isVisible(row) ? '正常显示' : '已隐藏' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="发布时间" width="150">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                :type="isVisible(row) ? 'warning' : 'success'"
                size="small"
                @click="handleToggleVisibility(row)"
              >
                {{ isVisible(row) ? '隐藏' : '恢复' }}
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无社区动态" :image-size="80" />
          </template>
        </el-table>

        <div class="pager">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            background
            @current-change="loadPosts"
            @size-change="loadPosts"
          />
        </div>
      </el-card>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clearAdminAuth, getAdminInfo, getAdminPosts, setAdminPostVisibility } from '@/api/admin'

const router = useRouter()
const adminInfo = getAdminInfo() || {}
const adminName = adminInfo.nickname || adminInfo.real_name || adminInfo.username || '管理员'

const posts = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

function isVisible(row) {
  if (!row) return true
  return Boolean(row.is_visible ?? true)
}

async function loadPosts() {
  loading.value = true
  try {
    const data = await getAdminPosts({ page: page.value, page_size: pageSize.value })
    posts.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? posts.value.length : Number(data?.total) || 0
  } catch (error) {
    posts.value = []
    total.value = 0
    ElMessage.error(`动态加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

async function handleToggleVisibility(row) {
  const nextVisible = !isVisible(row)
  try {
    await ElMessageBox.confirm(
      nextVisible ? '确定恢复显示这条动态吗？' : '确定隐藏这条动态吗？隐藏后普通用户将看不到。',
      nextVisible ? '恢复确认' : '隐藏确认',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
  } catch (error) {
    return
  }
  try {
    await setAdminPostVisibility(row.id, nextVisible)
    row.is_visible = nextVisible
    ElMessage.success(nextVisible ? '已恢复显示' : '已隐藏')
  } catch (error) {
    ElMessage.error(`操作失败：${error.message}`)
  }
}

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}`
}

function handleLogout() {
  clearAdminAuth()
  router.replace('/admin/login')
}

onMounted(loadPosts)
</script>

<style scoped>
.admin-shell {
  min-height: 100vh;
  background: var(--ft-bg, #0f1115);
}
.admin-nav {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 0 22px;
  height: 56px;
  background: var(--ft-bg-soft, #14171e);
  border-bottom: 1px solid var(--ft-border, rgba(255, 255, 255, 0.08));
  position: sticky;
  top: 0;
  z-index: 10;
  flex-wrap: wrap;
}
.admin-brand {
  font-size: 15px;
  font-weight: 700;
  color: var(--ft-primary, #ff5a1f);
  white-space: nowrap;
}
.admin-menu {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  flex-wrap: wrap;
}
.admin-menu a {
  padding: 6px 12px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--ft-text-sub, #a8b1c4);
  text-decoration: none;
}
.admin-menu a:hover {
  color: var(--ft-primary, #ff5a1f);
  background: rgba(255, 255, 255, 0.04);
}
.admin-menu a.router-link-active {
  color: #fff;
  background: var(--ft-primary, #ff5a1f);
}
.admin-user {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ft-text-sub, #a8b1c4);
}
.admin-name {
  white-space: nowrap;
}
.admin-body {
  padding: 20px 22px 40px;
  max-width: 1400px;
  margin: 0 auto;
}
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
  color: var(--ft-text-dim, #7b8497);
}
.panel {
  background: var(--ft-card, #171b24);
}
.post-content {
  font-size: 13px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
}
.post-topic {
  font-size: 12px;
  color: var(--ft-primary, #ff5a1f);
  margin-top: 4px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
