<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">{{ isEdit ? '编辑运动记录' : '新建运动记录' }}</h2>
        <p class="page-sub">填写本次训练的汇总信息，并逐组记录每个动作的重量与次数</p>
      </div>
      <div>
        <el-button @click="goBack">返回</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存记录</el-button>
      </div>
    </div>

    <el-alert
      v-if="loadError"
      type="error"
      :closable="false"
      show-icon
      :title="loadError"
      class="load-error"
    />

    <el-card v-loading="detailLoading" shadow="never" class="panel">
      <template #header>
        <span class="panel-title">训练概况</span>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="训练日期" prop="workout_date">
              <el-date-picker
                v-model="form.workout_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="训练类型" prop="workout_type">
              <el-select v-model="form.workout_type" style="width: 100%" placeholder="选择类型">
                <el-option v-for="item in WORKOUT_TYPES" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" maxlength="100" show-word-limit placeholder="例如：胸+三头 力量日" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="总时长">
              <el-input-number v-model="form.duration_min" :min="0" :max="1440" :step="5" style="width: 100%" />
              <span class="unit-tip">分钟</span>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="消耗热量">
              <el-input-number v-model="form.calories" :min="0" :max="10000" :step="10" style="width: 100%" />
              <span class="unit-tip">千卡</span>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="主观强度">
              <el-rate v-model="form.feeling" :max="5" show-score score-template="{value} 分" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="训练备注">
              <el-input
                v-model="form.note"
                type="textarea"
                :rows="3"
                maxlength="500"
                show-word-limit
                placeholder="今天状态如何？有没有突破？"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 动作组次录入 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="panel-head">
          <span class="panel-title">动作组次（{{ sets.length }} 组）</span>
          <div class="quick-add">
            <el-select
              v-model="quickExerciseId"
              filterable
              remote
              clearable
              reserve-keyword
              :remote-method="searchExerciseOptions"
              :loading="exerciseLoading"
              placeholder="搜索动作库，快速添加一组"
              style="width: 260px"
            >
              <el-option
                v-for="item in exerciseOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
            <el-button type="primary" plain :disabled="!quickExerciseId" @click="quickAddSet">＋ 添加一组</el-button>
            <el-button plain @click="addEmptySet">＋ 空白行</el-button>
          </div>
        </div>
      </template>

      <el-table :data="sets" size="small" style="width: 100%">
        <el-table-column label="#" type="index" width="50" />
        <el-table-column label="动作" min-width="220">
          <template #default="{ row }">
            <el-select
              v-model="row.exercise_id"
              filterable
              remote
              clearable
              reserve-keyword
              :remote-method="searchExerciseOptions"
              :loading="exerciseLoading"
              placeholder="选择动作"
              style="width: 100%"
              @change="(val) => handleExerciseChange(row, val)"
            >
              <el-option v-for="item in exerciseOptions" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="第几组" width="110">
          <template #default="{ row }">
            <el-input-number v-model="row.set_index" :min="1" :max="99" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="重量kg" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.weight" :min="0" :max="1000" :step="2.5" :precision="2" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="次数" width="110">
          <template #default="{ row }">
            <el-input-number v-model="row.reps" :min="0" :max="1000" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="时长(秒)" width="110">
          <template #default="{ row }">
            <el-input-number v-model="row.duration_sec" :min="0" :max="36000" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="距离(km)" width="110">
          <template #default="{ row }">
            <el-input-number v-model="row.distance_km" :min="0" :max="1000" :precision="2" :step="0.5" controls-position="right" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="140">
          <template #default="{ row }">
            <el-input v-model="row.note" maxlength="200" placeholder="可选" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ $index }">
            <el-button link type="danger" size="small" @click="removeSet($index)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有动作明细，从上方搜索动作库添加，或点「空白行」手动录入" :image-size="70" />
        </template>
      </el-table>

      <div class="sets-summary">
        总容量（重量×次数）：<b>{{ totalVolume }}</b> kg · 动作数：<b>{{ exerciseCount }}</b> 个 · 组数：<b>{{ sets.length }}</b>
      </div>
    </el-card>

    <div class="footer-actions">
      <el-button @click="goBack">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">保存记录</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { WORKOUT_TYPES, createRecord, getRecordDetail, updateRecord } from '@/api/record'
import { getExercises, searchExercises } from '@/api/exercise'

const route = useRoute()
const router = useRouter()

// 兼容 /records/:id/edit 与 /records/edit?id= 两种路由写法
const recordId = computed(() => route.params.id || route.query.id || '')

const isEdit = computed(() => Boolean(recordId.value))

const formRef = ref(null)
const detailLoading = ref(false)
const saving = ref(false)
const loadError = ref('')

const form = ref({
  workout_date: new Date().toISOString().slice(0, 10),
  workout_type: 'strength',
  title: '',
  duration_min: 60,
  calories: 300,
  feeling: 3,
  note: ''
})

const rules = {
  workout_date: [{ required: true, message: '请选择训练日期', trigger: 'change' }],
  workout_type: [{ required: true, message: '请选择训练类型', trigger: 'change' }]
}

// 动作组次列表
const sets = ref([])

// 动作库远程搜索选项
const exerciseOptions = ref([])
const exerciseLoading = ref(false)
const quickExerciseId = ref(null)

const totalVolume = computed(() =>
  sets.value.reduce((sum, row) => sum + (Number(row.weight) || 0) * (Number(row.reps) || 0), 0).toFixed(1)
)

const exerciseCount = computed(() => {
  const ids = new Set()
  sets.value.forEach((row) => {
    if (row.exercise_id) ids.add(row.exercise_id)
    else if (row.exercise_name) ids.add(`name:${row.exercise_name}`)
  })
  return ids.size
})

/** 把任意返回结构统一成数组 */
function toList(data, keys) {
  if (Array.isArray(data)) return data
  if (!data || typeof data !== 'object') return []
  for (const key of keys) {
    if (Array.isArray(data[key])) return data[key]
  }
  return []
}

/** 合并选项，保证已选中的动作始终能回显 */
function mergeOptions(list) {
  const merged = [...exerciseOptions.value]
  list
    .filter((item) => item && item.id)
    .forEach((item) => {
      if (!merged.some((exist) => exist.id === item.id)) merged.push(item)
    })
  exerciseOptions.value = merged
}

/** 打开页面时先塞一批默认动作，避免远程搜索接口空关键词报错 */
async function loadDefaultExerciseOptions() {
  exerciseLoading.value = true
  try {
    const data = await getExercises({ page: 1, page_size: 20 })
    const list = toList(data, ['items', 'list', 'exercises', 'results'])
    mergeOptions(list.map((item) => ({ id: item.id, name: item.name || `动作#${item.id}` })))
  } catch (error) {
    // 默认动作列表拿不到不影响手动搜索
  } finally {
    exerciseLoading.value = false
  }
}

/** 远程搜索动作库（关键词为空时回退到默认动作列表） */
async function searchExerciseOptions(keyword) {
  if (!keyword) {
    await loadDefaultExerciseOptions()
    return
  }
  exerciseLoading.value = true
  try {
    const data = await searchExercises(keyword)
    const list = toList(data, ['items', 'list', 'exercises', 'results'])
    mergeOptions(list.map((item) => ({ id: item.id, name: item.name || `动作#${item.id}` })))
  } catch (error) {
    ElMessage.warning(`动作搜索失败：${error.message}`)
  } finally {
    exerciseLoading.value = false
  }
}

/** 记录动作名称快照 */
function handleExerciseChange(row, exerciseId) {
  const hit = exerciseOptions.value.find((item) => item.id === exerciseId)
  row.exercise_name = hit ? hit.name : ''
  if (!exerciseId) return
  // 自动推算该动作的第几组
  const same = sets.value.filter((item) => item.exercise_id === exerciseId)
  row.set_index = same.length
}

/** 空白行 */
function addEmptySet() {
  sets.value.push({
    exercise_id: null,
    exercise_name: '',
    set_index: sets.value.length + 1,
    weight: 0,
    reps: 10,
    duration_sec: null,
    distance_km: null,
    note: ''
  })
}

/** 快速添加一组（沿用上次重量/次数） */
function quickAddSet() {
  if (!quickExerciseId.value) return
  const hit = exerciseOptions.value.find((item) => item.id === quickExerciseId.value)
  const sameRows = sets.value.filter((row) => row.exercise_id === quickExerciseId.value)
  const last = sameRows[sameRows.length - 1]
  sets.value.push({
    exercise_id: quickExerciseId.value,
    exercise_name: hit ? hit.name : '',
    set_index: sameRows.length + 1,
    weight: last ? last.weight : 0,
    reps: last ? last.reps : 10,
    duration_sec: last ? last.duration_sec : null,
    distance_km: last ? last.distance_km : null,
    note: ''
  })
}

function removeSet(index) {
  sets.value.splice(index, 1)
}

/** 加载详情（编辑模式） */
async function loadDetail() {
  if (!recordId.value) return
  detailLoading.value = true
  loadError.value = ''
  try {
    const data = await getRecordDetail(recordId.value)
    if (!data) {
      loadError.value = '记录不存在或已被删除'
      return
    }
    form.value = {
      workout_date: data.workout_date || new Date().toISOString().slice(0, 10),
      workout_type: data.workout_type || 'strength',
      title: data.title || '',
      duration_min: Number(data.duration_min) || 0,
      calories: Number(data.calories) || 0,
      feeling: Number(data.feeling) || 3,
      note: data.note || ''
    }
    const rawSets = toList(data.sets ? { sets: data.sets } : data, ['sets', 'items', 'details'])
    sets.value = rawSets.map((item, index) => ({
      exercise_id: item.exercise_id || null,
      exercise_name: item.exercise_name || '',
      set_index: Number(item.set_index) || index + 1,
      weight: Number(item.weight) || 0,
      reps: Number(item.reps) || 0,
      duration_sec: item.duration_sec === null || item.duration_sec === undefined ? null : Number(item.duration_sec),
      distance_km: item.distance_km === null || item.distance_km === undefined ? null : Number(item.distance_km),
      note: item.note || ''
    }))
    // 把已有动作塞进下拉选项，保证回显正常
    const options = []
    sets.value.forEach((row) => {
      if (row.exercise_id) {
        options.push({ id: row.exercise_id, name: row.exercise_name || `动作#${row.exercise_id}` })
      }
    })
    exerciseOptions.value = options
  } catch (error) {
    loadError.value = `记录加载失败：${error.message}`
  } finally {
    detailLoading.value = false
  }
}

/** 提交 */
async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (error) {
    ElMessage.warning('请先补全必填项')
    return
  }

  // 校验组次：必须有动作
  const invalidRow = sets.value.find((row) => !row.exercise_id && !row.exercise_name)
  if (invalidRow) {
    ElMessage.warning('有组次还没有选择动作，请补全或删除该行')
    return
  }

  const payload = {
    workout_date: form.value.workout_date,
    workout_type: form.value.workout_type,
    title: form.value.title || null,
    duration_min: Number(form.value.duration_min) || 0,
    calories: Number(form.value.calories) || 0,
    feeling: Number(form.value.feeling) || 3,
    note: form.value.note || null,
    sets: sets.value.map((row) => ({
      exercise_id: row.exercise_id || null,
      exercise_name: row.exercise_name || null,
      set_index: Number(row.set_index) || 1,
      weight: Number(row.weight) || 0,
      reps: Number(row.reps) || 0,
      duration_sec: row.duration_sec === null || row.duration_sec === '' ? null : Number(row.duration_sec),
      distance_km: row.distance_km === null || row.distance_km === '' ? null : Number(row.distance_km),
      note: row.note || null
    }))
  }

  // 从课程/计划跳转过来时带上关联 id（编辑模式下不传，避免覆盖原有关系）
  if (!isEdit.value && route.query.plan_id) payload.plan_id = Number(route.query.plan_id)
  if (!isEdit.value && route.query.course_id) payload.course_id = Number(route.query.course_id)

  saving.value = true
  try {
    if (isEdit.value) {
      await updateRecord(recordId.value, payload)
      ElMessage.success('修改成功')
      router.push(`/records/${recordId.value}`)
    } else {
      const created = await createRecord(payload)
      ElMessage.success('记录已保存')
      const newId = created && (created.id || created.record_id)
      if (newId) router.push(`/records/${newId}`)
      else router.push('/records')
    }
  } catch (error) {
    ElMessage.error(`保存失败：${error.message}`)
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(() => {
  loadDefaultExerciseOptions()
  loadDetail()
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  color: var(--el-text-color-primary, #e6edf3);
}
.page-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.load-error {
  margin-bottom: 12px;
}
.panel {
  margin-bottom: 12px;
  background: var(--el-bg-color-overlay, #1b2230);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary, #e6edf3);
}
.quick-add {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.unit-tip {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
}
.sets-summary {
  margin-top: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.sets-summary b {
  color: var(--el-color-primary, #409eff);
}
.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 8px 0 24px;
}
</style>
