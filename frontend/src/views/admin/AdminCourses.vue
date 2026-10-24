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
          <h2 class="page-title">课程管理</h2>
          <p class="page-sub">新增、编辑、上下架与删除运动课程</p>
        </div>
        <div class="head-tools">
          <el-button :loading="loading" @click="loadCourses">刷新</el-button>
          <el-button type="primary" @click="openCreate">＋ 新增课程</el-button>
        </div>
      </div>

      <el-card shadow="never" class="panel">
        <el-table v-loading="loading" :data="courses" size="small" style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="课程" min-width="220">
            <template #default="{ row }">
              <div class="cell-title">{{ row.title }}</div>
              <div class="cell-sub">{{ row.subtitle || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="分类" width="110">
            <template #default="{ row }">{{ row.category?.name || row.category_id || '—' }}</template>
          </el-table-column>
          <el-table-column label="难度" width="90">
            <template #default="{ row }">L{{ row.difficulty || 1 }}</template>
          </el-table-column>
          <el-table-column label="时长" width="90">
            <template #default="{ row }">{{ row.duration_min || 0 }} 分</template>
          </el-table-column>
          <el-table-column label="消耗" width="100">
            <template #default="{ row }">{{ row.calories || 0 }} 千卡</template>
          </el-table-column>
          <el-table-column label="播放量" width="90">
            <template #default="{ row }">{{ row.view_count || 0 }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_published ? 'success' : 'info'" size="small" effect="plain">
                {{ row.is_published ? '已上架' : '已下架' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button
                link
                :type="row.is_published ? 'warning' : 'success'"
                size="small"
                @click="handleTogglePublish(row)"
              >
                {{ row.is_published ? '下架' : '上架' }}
              </el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="还没有课程，点击右上角新增" :image-size="80" />
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
            @current-change="loadCourses"
            @size-change="loadCourses"
          />
        </div>
      </el-card>

      <!-- 新增 / 编辑弹窗 -->
      <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑课程' : '新增课程'" width="640px" top="6vh">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
          <el-row :gutter="12">
            <el-col :span="24">
              <el-form-item label="课程标题" prop="title">
                <el-input v-model="form.title" maxlength="120" show-word-limit placeholder="例如：20分钟燃脂 HIIT" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="副标题">
                <el-input v-model="form.subtitle" maxlength="200" placeholder="一句话卖点" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="分类ID" prop="category_id">
                <el-input-number v-model="form.category_id" :min="1" :max="9999" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="难度">
                <el-select v-model="form.difficulty" style="width: 100%">
                  <el-option :value="1" label="初级" />
                  <el-option :value="2" label="中级" />
                  <el-option :value="3" label="高级" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="时长(分钟)">
                <el-input-number v-model="form.duration_min" :min="1" :max="600" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="消耗(千卡)">
                <el-input-number v-model="form.calories" :min="0" :max="5000" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="教练">
                <el-input v-model="form.coach_name" maxlength="50" placeholder="教练名" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="器械">
                <el-input v-model="form.equipment" maxlength="100" placeholder="如：瑜伽垫、哑铃" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="锻炼部位">
                <el-input v-model="form.body_parts" maxlength="100" placeholder="如：全身、核心" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="是否上架">
                <el-switch v-model="form.is_published" active-text="上架" inactive-text="下架" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="封面地址">
                <el-input v-model="form.cover" placeholder="/static/uploads/covers/xxx.jpg 或完整 URL" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="视频地址">
                <el-input v-model="form.video_url" placeholder="mp4 / m3u8 地址" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="课程介绍">
                <el-input v-model="form.description" type="textarea" :rows="3" maxlength="1000" show-word-limit />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
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
  createAdminCourse,
  deleteAdminCourse,
  getAdminCourses,
  getAdminInfo,
  publishAdminCourse,
  updateAdminCourse
} from '@/api/admin'

const router = useRouter()
const adminInfo = getAdminInfo() || {}
const adminName = adminInfo.nickname || adminInfo.real_name || adminInfo.username || '管理员'

const courses = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formRef = ref(null)

const emptyForm = () => ({
  title: '',
  subtitle: '',
  category_id: 1,
  cover: '',
  video_url: '',
  duration_min: 20,
  calories: 150,
  difficulty: 1,
  equipment: '',
  body_parts: '',
  description: '',
  coach_name: '',
  is_published: true
})

const form = ref(emptyForm())

const rules = {
  title: [{ required: true, message: '请输入课程标题', trigger: 'blur' }],
  category_id: [{ required: true, message: '请填写分类ID', trigger: 'blur' }]
}

async function loadCourses() {
  loading.value = true
  try {
    const data = await getAdminCourses({ page: page.value, page_size: pageSize.value })
    courses.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? courses.value.length : Number(data?.total) || 0
  } catch (error) {
    courses.value = []
    total.value = 0
    ElMessage.error(`课程加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    title: row.title || '',
    subtitle: row.subtitle || '',
    category_id: Number(row.category_id) || 1,
    cover: row.cover || '',
    video_url: row.video_url || '',
    duration_min: Number(row.duration_min) || 20,
    calories: Number(row.calories) || 0,
    difficulty: Number(row.difficulty) || 1,
    equipment: row.equipment || '',
    body_parts: row.body_parts || '',
    description: row.description || '',
    coach_name: row.coach_name || '',
    is_published: Boolean(row.is_published)
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (error) {
    ElMessage.warning('请先补全必填项')
    return
  }
  const payload = {
    title: form.value.title,
    subtitle: form.value.subtitle || null,
    category_id: Number(form.value.category_id) || 1,
    cover: form.value.cover || null,
    video_url: form.value.video_url || null,
    duration_min: Number(form.value.duration_min) || 0,
    calories: Number(form.value.calories) || 0,
    difficulty: Number(form.value.difficulty) || 1,
    equipment: form.value.equipment || null,
    body_parts: form.value.body_parts || null,
    description: form.value.description || null,
    coach_name: form.value.coach_name || null,
    is_published: Boolean(form.value.is_published)
  }

  saving.value = true
  try {
    if (isEdit.value && editingId.value) {
      await updateAdminCourse(editingId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await createAdminCourse(payload)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    await loadCourses()
  } catch (error) {
    ElMessage.error(`保存失败：${error.message}`)
  } finally {
    saving.value = false
  }
}

async function handleTogglePublish(row) {
  const next = !row.is_published
  try {
    await publishAdminCourse(row.id, next)
    row.is_published = next
    ElMessage.success(next ? '已上架' : '已下架')
  } catch (error) {
    ElMessage.error(`操作失败：${error.message}`)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除课程「${row.title}」吗？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteAdminCourse(row.id)
    ElMessage.success('已删除')
    if (courses.value.length === 1 && page.value > 1) page.value -= 1
    await loadCourses()
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

function handleLogout() {
  clearAdminAuth()
  router.replace('/admin/login')
}

onMounted(loadCourses)
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
.head-tools {
  display: flex;
  gap: 8px;
}
.panel {
  background: var(--ft-card, #171b24);
}
.cell-title {
  font-size: 13px;
  font-weight: 600;
}
.cell-sub {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
