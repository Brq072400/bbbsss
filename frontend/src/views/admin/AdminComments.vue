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
          <h2 class="page-title">评论审核</h2>
          <p class="page-sub">审核课程评论，通过或驳回用户发言</p>
        </div>
        <el-button :loading="loading" @click="loadComments">刷新</el-button>
      </div>

      <div class="toolbar">
        <el-select v-model="status" placeholder="审核状态" style="width: 140px" @change="handleSearch">
          <el-option label="全部状态" value="" />
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-input
          v-model="courseId"
          placeholder="按课程ID筛选"
          clearable
          style="width: 160px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button @click="handleSearch">筛选</el-button>
        <span class="total-tip">共 {{ total }} 条评论</span>
      </div>

      <el-card shadow="never" class="panel">
        <el-table v-loading="loading" :data="comments" size="small" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="评论用户" width="140">
            <template #default="{ row }">
              {{ row.user?.nickname || row.user?.username || `用户${row.user_id || ''}` }}
            </template>
          </el-table-column>
          <el-table-column label="课程" width="150">
            <template #default="{ row }">
              <span class="ellipsis">{{ row.course?.title || `课程#${row.course_id || '—'}` }}</span>
            </template>
          </el-table-column>
          <el-table-column label="评论内容" min-width="240">
            <template #default="{ row }">
              <div class="comment-text">{{ row.content }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="plain">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="提交时间" width="150">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="success"
                size="small"
                :disabled="row.status === 'approved'"
                @click="handleAudit(row, 'approve')"
              >
                通过
              </el-button>
              <el-button
                link
                type="warning"
                size="small"
                :disabled="row.status === 'rejected'"
                @click="handleAudit(row, 'reject')"
              >
                驳回
              </el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="没有符合条件的评论" :image-size="80" />
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
            @current-change="loadComments"
            @size-change="loadComments"
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
import {
  auditAdminComment,
  clearAdminAuth,
  deleteAdminComment,
  getAdminComments,
  getAdminInfo
} from '@/api/admin'

const router = useRouter()
const adminInfo = getAdminInfo() || {}
const adminName = adminInfo.nickname || adminInfo.real_name || adminInfo.username || '管理员'

const comments = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const status = ref('pending')
const courseId = ref('')

function statusLabel(value) {
  const map = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
  return map[value] || value || '未知'
}

function statusTagType(value) {
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'danger'
  return 'warning'
}

async function loadComments() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (status.value) params.status = status.value
    if (courseId.value) params.course_id = Number(courseId.value)

    const data = await getAdminComments(params)
    comments.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? comments.value.length : Number(data?.total) || 0
  } catch (error) {
    comments.value = []
    total.value = 0
    ElMessage.error(`评论加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadComments()
}

async function handleAudit(row, action) {
  const label = action === 'approve' ? '通过' : '驳回'
  try {
    await ElMessageBox.confirm(`确定${label}这条评论吗？`, `${label}确认`, {
      type: 'warning',
      confirmButtonText: label,
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await auditAdminComment(row.id, action)
    ElMessage.success(`已${label}`)
    await loadComments()
  } catch (error) {
    ElMessage.error(`${label}失败：${error.message}`)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除这条评论吗？删除后不可恢复。', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteAdminComment(row.id)
    ElMessage.success('已删除')
    if (comments.value.length === 1 && page.value > 1) page.value -= 1
    await loadComments()
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
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

onMounted(loadComments)
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
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.total-tip {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
  margin-left: auto;
}
.panel {
  background: var(--ft-card, #171b24);
}
.comment-text {
  font-size: 13px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
