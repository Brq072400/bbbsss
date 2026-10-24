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
          <h2 class="page-title">用户管理</h2>
          <p class="page-sub">查询用户、封禁账号、重置密码或删除账号</p>
        </div>
      </div>

      <!-- 筛选 -->
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名 / 昵称 / 手机号"
          clearable
          style="width: 240px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">搜索</el-button>
          </template>
        </el-input>
        <el-select v-model="statusFilter" placeholder="账号状态" style="width: 140px" @change="handleSearch">
          <el-option label="全部" value="" />
          <el-option label="正常" :value="false" />
          <el-option label="已封禁" :value="true" />
        </el-select>
        <el-button @click="resetFilter">重置</el-button>
        <span class="total-tip">共 {{ total }} 个用户</span>
      </div>

      <el-card shadow="never" class="panel">
        <el-table v-loading="loading" :data="users" size="small" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="用户名" min-width="130">
            <template #default="{ row }">
              <div class="user-cell">
                <div class="user-cell-name">{{ row.username }}</div>
                <div class="user-cell-sub">{{ row.nickname || '—' }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="手机号" width="130">
            <template #default="{ row }">{{ row.phone || '—' }}</template>
          </el-table-column>
          <el-table-column label="等级" width="80">
            <template #default="{ row }">Lv.{{ row.level || 1 }}</template>
          </el-table-column>
          <el-table-column label="积分" width="80">
            <template #default="{ row }">{{ row.points || 0 }}</template>
          </el-table-column>
          <el-table-column label="实名" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_verified ? 'success' : 'info'" size="small" effect="plain">
                {{ row.is_verified ? '已实名' : '未实名' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_disabled ? 'danger' : 'success'" size="small" effect="plain">
                {{ row.is_disabled ? '已封禁' : '正常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="注册/登录时间" min-width="150">
            <template #default="{ row }">
              <div class="time-cell">
                <div>注册：{{ formatTime(row.created_at) }}</div>
                <div>登录：{{ formatTime(row.last_login_at) }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="210" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                :type="row.is_disabled ? 'success' : 'warning'"
                size="small"
                @click="handleToggleDisable(row)"
              >
                {{ row.is_disabled ? '解封' : '封禁' }}
              </el-button>
              <el-button link type="primary" size="small" @click="openResetDialog(row)">重置密码</el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="没有符合条件的用户" :image-size="80" />
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
            @current-change="loadUsers"
            @size-change="loadUsers"
          />
        </div>
      </el-card>

      <!-- 重置密码 -->
      <el-dialog v-model="resetVisible" title="重置用户密码" width="400px">
        <p class="dialog-tip">正在重置用户「{{ resetTarget?.username }}」的密码</p>
        <el-input v-model="newPassword" placeholder="请输入新密码（至少 6 位）" show-password maxlength="50" />
        <template #footer>
          <el-button @click="resetVisible = false">取消</el-button>
          <el-button type="primary" :loading="resetting" @click="handleResetPassword">确认重置</el-button>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  clearAdminAuth,
  deleteAdminUser,
  getAdminInfo,
  getAdminUsers,
  resetUserPassword,
  setUserDisabled
} from '@/api/admin'

const router = useRouter()
const adminInfo = getAdminInfo() || {}
const adminName = adminInfo.nickname || adminInfo.real_name || adminInfo.username || '管理员'

const users = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')

const resetVisible = ref(false)
const resetTarget = ref(null)
const newPassword = ref('')
const resetting = ref(false)

async function loadUsers() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value) params.keyword = keyword.value
    if (statusFilter.value !== '' && statusFilter.value !== null) params.is_disabled = statusFilter.value

    const data = await getAdminUsers(params)
    users.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? users.value.length : Number(data?.total) || 0
  } catch (error) {
    users.value = []
    total.value = 0
    ElMessage.error(`用户加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadUsers()
}

function resetFilter() {
  keyword.value = ''
  statusFilter.value = ''
  handleSearch()
}

async function handleToggleDisable(row) {
  const nextDisabled = !row.is_disabled
  try {
    await ElMessageBox.confirm(
      nextDisabled ? `确定封禁用户「${row.username}」吗？封禁后该账号将无法登录。` : `确定解封用户「${row.username}」吗？`,
      nextDisabled ? '封禁确认' : '解封确认',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
  } catch (error) {
    return
  }
  try {
    await setUserDisabled(row.id, nextDisabled)
    row.is_disabled = nextDisabled
    ElMessage.success(nextDisabled ? '已封禁' : '已解封')
  } catch (error) {
    ElMessage.error(`操作失败：${error.message}`)
  }
}

function openResetDialog(row) {
  resetTarget.value = row
  newPassword.value = ''
  resetVisible.value = true
}

async function handleResetPassword() {
  if (!newPassword.value || newPassword.value.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  resetting.value = true
  try {
    await resetUserPassword(resetTarget.value.id, newPassword.value)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch (error) {
    ElMessage.error(`重置失败：${error.message}`)
  } finally {
    resetting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？该操作不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteAdminUser(row.id)
    ElMessage.success('已删除')
    if (users.value.length === 1 && page.value > 1) page.value -= 1
    await loadUsers()
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

onMounted(loadUsers)
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
.user-cell-name {
  font-size: 13px;
  font-weight: 600;
}
.user-cell-sub {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
}
.time-cell {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
  line-height: 1.5;
}
.dialog-tip {
  font-size: 13px;
  color: var(--ft-text-sub, #a8b1c4);
  margin-bottom: 12px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
