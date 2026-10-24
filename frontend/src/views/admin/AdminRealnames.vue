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
          <h2 class="page-title">实名审核</h2>
          <p class="page-sub">审核用户的实名认证申请，通过或驳回并填写原因</p>
        </div>
        <el-button :loading="loading" @click="loadRealnames">刷新</el-button>
      </div>

      <div class="toolbar">
        <el-select v-model="status" placeholder="审核状态" style="width: 140px" @change="handleSearch">
          <el-option label="全部状态" value="" />
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-button @click="handleSearch">筛选</el-button>
        <span class="total-tip">共 {{ total }} 条申请</span>
      </div>

      <el-card shadow="never" class="panel">
        <el-table v-loading="loading" :data="items" size="small" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="用户" width="150">
            <template #default="{ row }">
              <div class="user-name">{{ row.user?.nickname || row.user?.username || `用户${row.user_id || ''}` }}</div>
              <div class="user-sub">ID: {{ row.user_id || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="真实姓名" width="120">
            <template #default="{ row }">{{ row.real_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="身份证号" width="180">
            <template #default="{ row }">{{ row.id_card || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="plain">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="驳回原因" min-width="160">
            <template #default="{ row }">{{ row.reject_reason || '—' }}</template>
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
                @click="openRejectDialog(row)"
              >
                驳回
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="没有符合条件的实名申请" :image-size="80" />
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
            @current-change="loadRealnames"
            @size-change="loadRealnames"
          />
        </div>
      </el-card>

      <!-- 驳回弹窗 -->
      <el-dialog v-model="rejectVisible" title="驳回实名申请" width="420px">
        <p class="dialog-tip">驳回用户「{{ rejectTarget?.user?.nickname || rejectTarget?.real_name }}」的实名申请</p>
        <el-input
          v-model="rejectReason"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          placeholder="请填写驳回原因，例如：身份证照片不清晰"
        />
        <template #footer>
          <el-button @click="rejectVisible = false">取消</el-button>
          <el-button type="warning" :loading="auditing" @click="handleReject">确认驳回</el-button>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { auditAdminRealname, clearAdminAuth, getAdminInfo, getAdminRealnames } from '@/api/admin'

const router = useRouter()
const adminInfo = getAdminInfo() || {}
const adminName = adminInfo.nickname || adminInfo.real_name || adminInfo.username || '管理员'

const items = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const status = ref('pending')

const rejectVisible = ref(false)
const rejectTarget = ref(null)
const rejectReason = ref('')
const auditing = ref(false)

function statusLabel(value) {
  const map = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
  return map[value] || value || '未知'
}

function statusTagType(value) {
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'danger'
  return 'warning'
}

async function loadRealnames() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (status.value) params.status = status.value
    const data = await getAdminRealnames(params)
    items.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? items.value.length : Number(data?.total) || 0
  } catch (error) {
    items.value = []
    total.value = 0
    ElMessage.error(`实名申请加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadRealnames()
}

async function handleAudit(row, action) {
  try {
    await ElMessageBox.confirm('确定通过这条实名申请吗？通过后用户将标记为已实名。', '通过确认', {
      type: 'warning',
      confirmButtonText: '通过',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  auditing.value = true
  try {
    await auditAdminRealname(row.id, action, null)
    ElMessage.success('已通过')
    await loadRealnames()
  } catch (error) {
    ElMessage.error(`操作失败：${error.message}`)
  } finally {
    auditing.value = false
  }
}

function openRejectDialog(row) {
  rejectTarget.value = row
  rejectReason.value = ''
  rejectVisible.value = true
}

async function handleReject() {
  if (!rejectReason.value) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  auditing.value = true
  try {
    await auditAdminRealname(rejectTarget.value.id, 'reject', rejectReason.value)
    ElMessage.success('已驳回')
    rejectVisible.value = false
    await loadRealnames()
  } catch (error) {
    ElMessage.error(`驳回失败：${error.message}`)
  } finally {
    auditing.value = false
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

onMounted(loadRealnames)
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
.user-name {
  font-size: 13px;
  font-weight: 600;
}
.user-sub {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
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
