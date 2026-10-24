<script setup>
/**
 * PlanEdit.vue 新建 / 编辑训练计划
 * 新建：基础信息 + 动作明细一起提交（POST /api/plans/publish）
 * 编辑：基础信息用 PUT /api/plans/{id}；动作明细通过
 *       POST/PUT/DELETE /api/plans/{id}/item 逐条维护，实时生效
 * 动作可以从动作库挑选，也可以自定义名称
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  addPlanItem,
  deletePlanItem,
  getPlanDetail,
  publishPlan,
  updatePlan,
  updatePlanItem
} from '@/api/plan'
import { getExerciseCategories, getExercises } from '@/api/exercise'

const route = useRoute()
const router = useRouter()

/** 路由上的计划 ID；为空表示新建模式 */
const planId = computed(() => route.params.id)
const isEdit = computed(() => Boolean(planId.value))

// ---------------- 基础信息 ----------------
const formRef = ref(null)
const pageLoading = ref(false)
const saving = ref(false)
const loadError = ref('')
/** 编辑模式下是否为本人计划（非本人只读） */
const isOwner = ref(true)

/** 计划基础信息表单 */
const form = reactive({
  name: '',
  description: '',
  goal: 'keep_fit',
  cycle_type: 'weekly',
  cycle_days: 7,
  cover: '',
  is_public: false
})

/** 训练目标选项（与后端 PlanPublishRequest 的枚举一致） */
const goalOptions = [
  { label: '增肌', value: 'gain_muscle' },
  { label: '减脂', value: 'lose_fat' },
  { label: '塑形', value: 'shape' },
  { label: '康复', value: 'rehab' },
  { label: '保持健康', value: 'keep_fit' }
]

/** 周期类型选项 */
const cycleTypeOptions = [
  { label: '按周安排（weekly）', value: 'weekly' },
  { label: '每日循环（daily）', value: 'daily' }
]

/** 基础信息校验规则 */
const rules = {
  name: [
    { required: true, message: '请输入计划名称', trigger: 'blur' },
    { min: 1, max: 100, message: '名称长度需在 1 到 100 个字符之间', trigger: 'blur' }
  ],
  goal: [{ required: true, message: '请选择训练目标', trigger: 'change' }],
  cycle_type: [{ required: true, message: '请选择周期类型', trigger: 'change' }],
  cycle_days: [
    { required: true, message: '请输入周期天数', trigger: 'blur' },
    { type: 'number', min: 1, max: 30, message: '周期天数需在 1-30 天之间', trigger: 'blur' }
  ],
  description: [{ max: 2000, message: '计划说明最多 2000 个字符', trigger: 'blur' }],
  cover: [{ max: 255, message: '封面地址最多 255 个字符', trigger: 'blur' }]
}

// ---------------- 动作明细 ----------------
/**
 * 前端统一的动作明细结构
 * { id?, exercise_id, exerciseName, dayIndex, sets, reps, weight, rest_seconds, duration_min, note }
 */
const items = ref([])
const itemsLoading = ref(false)

/** 按天分组（第 1 天 … 第 cycle_days 天） */
const dayGroups = computed(() => {
  const days = Number(form.cycle_days) || 7
  const groups = []
  for (let day = 1; day <= days; day += 1) {
    groups.push({
      dayIndex: day,
      items: items.value.filter((item) => Number(item.dayIndex) === day)
    })
  }
  // 超出周期天数的动作单独提示（切换周期天数后可能出现）
  const overflow = items.value.filter((item) => Number(item.dayIndex) > days)
  return { groups, overflow }
})

/** 动作总数 */
const totalItems = computed(() => items.value.length)
/** 有训练安排的天数 */
const activeDays = computed(
  () => dayGroups.value.groups.filter((group) => group.items.length > 0).length
)

// ---------------- 加载计划（编辑模式） ----------------
/** 把后端动作明细转成前端结构 */
function mapItemsFromPlan(plan) {
  return (plan?.items || []).map((item) => ({
    id: item.id,
    exercise_id: item.exercise_id ?? null,
    exerciseName: item.exercise?.name || item.note || '自定义动作',
    dayIndex: Number(item.day_index ?? 1),
    sets: Number(item.sets ?? 3),
    reps: Number(item.reps ?? 12),
    weight: item.weight ?? null,
    rest_seconds: Number(item.rest_seconds ?? 60),
    duration_min: item.duration_min ?? null,
    note: item.note || ''
  }))
}

/** 加载计划详情并回填表单 */
async function loadPlan() {
  if (!isEdit.value) return
  pageLoading.value = true
  loadError.value = ''
  try {
    const plan = await getPlanDetail(planId.value)
    form.name = plan.name || ''
    form.description = plan.description || ''
    form.goal = plan.goal || 'keep_fit'
    form.cycle_type = plan.cycle_type || 'weekly'
    form.cycle_days = Number(plan.cycle_days || 7)
    form.cover = plan.cover || ''
    form.is_public = Boolean(plan.is_public)
    isOwner.value = plan.is_owner !== false
    items.value = mapItemsFromPlan(plan)
  } catch (error) {
    loadError.value = '计划加载失败，可能已被删除'
  } finally {
    pageLoading.value = false
  }
}

// ---------------- 动作编辑弹窗 ----------------
const itemVisible = ref(false)
const itemSaving = ref(false)
const itemFormRef = ref(null)
/** 正在编辑的动作索引（-1 表示新增） */
const editingIndex = ref(-1)

/** 动作表单 */
const itemForm = reactive({
  source: 'library', // library 从动作库选择 / custom 自定义名称
  exercise_id: null,
  exerciseName: '',
  customName: '',
  dayIndex: 1,
  sets: 3,
  reps: 12,
  weight: null,
  rest_seconds: 60,
  duration_min: null,
  note: ''
})

/** 动作表单校验规则 */
const itemRules = {
  dayIndex: [
    { required: true, message: '请选择第几天', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (Number(value) < 1 || Number(value) > Number(form.cycle_days)) {
          return callback(new Error(`天数需在 1-${form.cycle_days} 之间`))
        }
        callback()
      },
      trigger: 'change'
    }
  ],
  sets: [
    { required: true, message: '请输入组数', trigger: 'blur' },
    { type: 'number', min: 0, max: 99, message: '组数需在 0-99 之间', trigger: 'blur' }
  ],
  reps: [
    { required: true, message: '请输入次数', trigger: 'blur' },
    { type: 'number', min: 0, max: 999, message: '次数需在 0-999 之间', trigger: 'blur' }
  ],
  rest_seconds: [
    { type: 'number', min: 0, max: 3600, message: '休息时间需在 0-3600 秒之间', trigger: 'blur' }
  ],
  weight: [{ type: 'number', min: 0, max: 1000, message: '重量需在 0-1000 kg 之间', trigger: 'blur' }],
  duration_min: [{ type: 'number', min: 0, max: 600, message: '时长需在 0-600 分钟之间', trigger: 'blur' }],
  customName: [
    {
      validator: (rule, value, callback) => {
        // 自定义模式必须填名称；动作库模式必须已选择动作
        if (itemForm.source === 'custom' && !String(value || '').trim()) {
          return callback(new Error('请输入自定义动作名称'))
        }
        if (itemForm.source === 'library' && !itemForm.exercise_id) {
          return callback(new Error('请从动作库中选择一个动作'))
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

/** 重置动作表单为基础值 */
function resetItemForm(dayIndex = 1) {
  itemForm.source = 'library'
  itemForm.exercise_id = null
  itemForm.exerciseName = ''
  itemForm.customName = ''
  itemForm.dayIndex = dayIndex
  itemForm.sets = 3
  itemForm.reps = 12
  itemForm.weight = null
  itemForm.rest_seconds = 60
  itemForm.duration_min = null
  itemForm.note = ''
}

/** 打开「新增动作」弹窗 */
function openAddItem(dayIndex = 1) {
  editingIndex.value = -1
  resetItemForm(dayIndex)
  itemVisible.value = true
}

/** 打开「编辑动作」弹窗（编辑模式下的服务端动作也走同一个弹窗） */
function openEditItem(item, index) {
  editingIndex.value = index
  itemForm.source = item.exercise_id ? 'library' : 'custom'
  itemForm.exercise_id = item.exercise_id ?? null
  itemForm.exerciseName = item.exerciseName || ''
  itemForm.customName = item.exercise_id ? '' : item.exerciseName || ''
  itemForm.dayIndex = Number(item.dayIndex)
  itemForm.sets = Number(item.sets)
  itemForm.reps = Number(item.reps)
  itemForm.weight = item.weight ?? null
  itemForm.rest_seconds = Number(item.rest_seconds ?? 60)
  itemForm.duration_min = item.duration_min ?? null
  itemForm.note = item.note || ''
  itemVisible.value = true
}

/** 构造提交给后端的动作数据（PlanItemRequest） */
function buildItemPayload() {
  const isCustom = itemForm.source === 'custom'
  return {
    day_index: Number(itemForm.dayIndex),
    exercise_id: isCustom ? null : itemForm.exercise_id,
    sets: Number(itemForm.sets ?? 0),
    reps: Number(itemForm.reps ?? 0),
    weight: itemForm.weight === null || itemForm.weight === '' ? null : Number(itemForm.weight),
    rest_seconds: Number(itemForm.rest_seconds ?? 60),
    duration_min:
      itemForm.duration_min === null || itemForm.duration_min === '' ? null : Number(itemForm.duration_min),
    // 自定义动作把名称存进 note，避免动作库匹配不到时丢失信息
    note: isCustom ? itemForm.customName.trim() : itemForm.note.trim() || null
  }
}

/** 保存动作（新增或修改） */
async function handleSaveItem() {
  if (!itemFormRef.value) return
  try {
    await itemFormRef.value.validate()
  } catch (error) {
    return
  }

  const payload = buildItemPayload()
  const displayName =
    itemForm.source === 'custom' ? itemForm.customName.trim() : itemForm.exerciseName || '动作'

  itemSaving.value = true
  try {
    if (isEdit.value) {
      // 编辑模式：直接调用动作增删改接口，实时生效
      const editing = editingIndex.value >= 0 ? items.value[editingIndex.value] : null
      if (editing?.id) {
        await updatePlanItem(planId.value, editing.id, payload)
        ElMessage.success('动作已更新')
      } else {
        await addPlanItem(planId.value, payload)
        ElMessage.success('动作已添加')
      }
      await reloadItems()
    } else {
      // 新建模式：只更新本地草稿，随计划一起提交
      const next = {
        id: null,
        exercise_id: payload.exercise_id,
        exerciseName: displayName,
        dayIndex: payload.day_index,
        sets: payload.sets,
        reps: payload.reps,
        weight: payload.weight,
        rest_seconds: payload.rest_seconds,
        duration_min: payload.duration_min,
        note: payload.note || ''
      }
      if (editingIndex.value >= 0) items.value.splice(editingIndex.value, 1, next)
      else items.value.push(next)
      ElMessage.success(editingIndex.value >= 0 ? '动作已修改' : '动作已添加')
    }
    itemVisible.value = false
  } catch (error) {
    /* 错误已提示 */
  } finally {
    itemSaving.value = false
  }
}

/** 编辑模式下重新拉取动作明细（保证与后端一致） */
async function reloadItems() {
  itemsLoading.value = true
  try {
    const plan = await getPlanDetail(planId.value)
    items.value = mapItemsFromPlan(plan)
  } catch (error) {
    /* 错误已提示 */
  } finally {
    itemsLoading.value = false
  }
}

/** 删除一个动作 */
async function handleDeleteItem(item, index) {
  try {
    await ElMessageBox.confirm(`确定删除动作「${item.exerciseName}」吗？`, '删除动作', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return // 取消
  }

  try {
    if (isEdit.value && item.id) {
      await deletePlanItem(planId.value, item.id)
      ElMessage.success('动作已删除')
      await reloadItems()
    } else {
      items.value.splice(index, 1)
      ElMessage.success('动作已删除')
    }
  } catch (error) {
    /* 错误已提示 */
  }
}

// ---------------- 动作库选择器 ----------------
const pickerVisible = ref(false)
const exerciseCategories = ref([])
const exerciseList = ref([])
const exerciseLoading = ref(false)
const exerciseError = ref('')
const exerciseKeyword = ref('')
const exerciseCategory = ref('')
const exercisePage = ref(1)
const exerciseTotal = ref(0)
const exercisePageSize = 8

/** 加载动作分类 */
async function loadExerciseCategories() {
  try {
    const data = await getExerciseCategories()
    exerciseCategories.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    exerciseCategories.value = []
  }
}

/** 加载动作列表 */
async function loadExercises() {
  exerciseLoading.value = true
  exerciseError.value = ''
  try {
    const params = { page: exercisePage.value, page_size: exercisePageSize }
    if (exerciseKeyword.value.trim()) params.keyword = exerciseKeyword.value.trim()
    if (exerciseCategory.value !== '') params.category_id = exerciseCategory.value
    const data = await getExercises(params)
    exerciseList.value = Array.isArray(data) ? data : data?.items || []
    exerciseTotal.value = Number(data?.total ?? exerciseList.value.length)
  } catch (error) {
    exerciseList.value = []
    exerciseTotal.value = 0
    exerciseError.value = '动作库加载失败'
  } finally {
    exerciseLoading.value = false
  }
}

/** 打开动作库选择器 */
function openPicker() {
  pickerVisible.value = true
  if (!exerciseList.value.length) loadExercises()
}

/** 搜索动作 */
function handleExerciseSearch() {
  exercisePage.value = 1
  loadExercises()
}

/** 选择动作库中的某个动作 */
function handlePickExercise(exercise) {
  itemForm.source = 'library'
  itemForm.exercise_id = exercise.id
  itemForm.exerciseName = exercise.name
  pickerVisible.value = false
  ElMessage.success(`已选择动作：${exercise.name}`)
}

/** 动作难度星级 */
function stars(level) {
  const n = Math.max(1, Math.min(5, Number(level) || 1))
  return '★'.repeat(n)
}

// ---------------- 保存计划 ----------------
/** 新建模式下把草稿动作转成后端入参（按天排序） */
function buildPublishItems() {
  return [...items.value]
    .sort((a, b) => Number(a.dayIndex) - Number(b.dayIndex))
    .map((item) => ({
      day_index: Number(item.dayIndex),
      exercise_id: item.exercise_id || null,
      sets: Number(item.sets ?? 0),
      reps: Number(item.reps ?? 0),
      weight: item.weight ?? null,
      rest_seconds: Number(item.rest_seconds ?? 60),
      duration_min: item.duration_min ?? null,
      note: item.note || (item.exercise_id ? null : item.exerciseName)
    }))
}

/** 保存（新建提交发布，编辑提交基础信息更新） */
async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (error) {
    return
  }

  if (!isOwner.value) {
    ElMessage.warning('只能编辑自己创建的计划')
    return
  }

  // 切换周期天数后可能有动作超出天数，提前拦截避免后端报错
  if (dayGroups.value.overflow.length) {
    ElMessage.warning(
      `有 ${dayGroups.value.overflow.length} 个动作安排在超过 ${form.cycle_days} 天的位置，请先调整`
    )
    return
  }

  saving.value = true
  try {
    const base = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      goal: form.goal,
      cycle_type: form.cycle_type,
      cycle_days: Number(form.cycle_days),
      cover: form.cover.trim() || null,
      is_public: form.is_public
    }

    if (isEdit.value) {
      await updatePlan(planId.value, base)
      ElMessage.success('计划信息已保存')
      router.push(`/plans/${planId.value}`)
    } else {
      const created = await publishPlan({ ...base, items: buildPublishItems() })
      ElMessage.success('计划创建成功')
      if (created?.id) router.push(`/plans/${created.id}`)
      else router.push('/plans')
    }
  } catch (error) {
    /* 错误已提示 */
  } finally {
    saving.value = false
  }
}

/** 取消并返回 */
function handleCancel() {
  if (isEdit.value) router.push(`/plans/${planId.value}`)
  else router.push('/plans')
}

onMounted(async () => {
  await loadPlan()
  // 动作库分类只在需要时加载
  loadExerciseCategories()
})
</script>

<template>
  <div class="ft-page">
    <PageHeader
      :title="isEdit ? '编辑计划' : '新建计划'"
      :subtitle="
        isEdit
          ? '基础信息保存后立即生效；动作明细的增删改会实时同步到服务器'
          : '先填写基础信息，再按天添加动作，最后一次性创建计划'
      "
      :back-to="isEdit ? `/plans/${planId}` : '/plans'"
    >
      <template #actions>
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ isEdit ? '保存修改' : '创建计划' }}
        </el-button>
      </template>
    </PageHeader>

    <div v-if="pageLoading" class="ft-loading-text">正在加载计划…</div>

    <EmptyState v-else-if="loadError" icon="⚠️" :description="loadError" error>
      <el-button @click="loadPlan">重新加载</el-button>
      <el-button @click="router.push('/plans')">返回列表</el-button>
    </EmptyState>

    <template v-else>
      <el-alert
        v-if="!isOwner"
        type="warning"
        show-icon
        :closable="false"
        title="只读模式"
        description="这不是你创建的计划，只能查看不能修改。"
        style="margin-bottom: 16px"
      />

      <div class="plan-edit">
        <!-- ============ 基础信息 ============ -->
        <section class="ft-card">
          <h3 class="ft-section-title">基础信息</h3>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="96px"
            :disabled="!isOwner"
          >
            <el-form-item label="计划名称" prop="name">
              <el-input v-model="form.name" placeholder="例如：增肌上下肢 4 日分化" maxlength="100" show-word-limit />
            </el-form-item>

            <el-form-item label="训练目标" prop="goal">
              <el-select v-model="form.goal" style="width: 100%">
                <el-option v-for="opt in goalOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>

            <div class="plan-edit__grid">
              <el-form-item label="周期类型" prop="cycle_type">
                <el-select v-model="form.cycle_type" style="width: 100%">
                  <el-option
                    v-for="opt in cycleTypeOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="周期天数" prop="cycle_days">
                <el-input-number
                  v-model="form.cycle_days"
                  :min="1"
                  :max="30"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </div>

            <el-form-item label="封面地址" prop="cover">
              <el-input v-model="form.cover" placeholder="可选，图片 URL（如 /uploads/xxx.png）" />
            </el-form-item>

            <el-form-item label="计划说明" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="3"
                maxlength="2000"
                show-word-limit
                placeholder="简单描述这个计划的训练思路、适合人群"
              />
            </el-form-item>

            <el-form-item label="公开计划">
              <el-switch v-model="form.is_public" active-text="公开后可被他人查看与收藏" />
            </el-form-item>
          </el-form>
        </section>

        <!-- ============ 动作明细 ============ -->
        <section class="ft-card">
          <div class="plan-edit__items-head">
            <h3 class="ft-section-title" style="margin: 0">动作安排</h3>
            <div class="plan-edit__items-stat">
              <span class="ft-chip ft-chip--primary">{{ totalItems }} 个动作</span>
              <span class="ft-chip">{{ activeDays }} 天有训练</span>
              <el-button
                size="small"
                type="primary"
                :disabled="!isOwner"
                :loading="itemsLoading"
                @click="openAddItem(1)"
              >
                + 添加动作
              </el-button>
            </div>
          </div>

          <el-alert
            v-if="isEdit"
            type="info"
            :closable="false"
            show-icon
            title="动作明细会实时保存"
            description="在编辑模式下添加、修改、删除动作会立即生效，无需再点保存。"
            style="margin: 12px 0"
          />

          <el-alert
            v-if="dayGroups.overflow.length"
            type="warning"
            :closable="false"
            show-icon
            :title="`有 ${dayGroups.overflow.length} 个动作排在超过 ${form.cycle_days} 天的位置`"
            description="请把这些动作改到周期范围内，否则保存会被后端拒绝。"
            style="margin: 12px 0"
          />

          <div v-if="itemsLoading" class="ft-loading-text" style="padding: 30px 0">正在同步动作…</div>

          <div v-else-if="!totalItems" class="plan-edit__empty">
            <EmptyState size="sm" icon="🏋️" description="还没有添加任何动作，先加一个吧">
              <el-button size="small" type="primary" :disabled="!isOwner" @click="openAddItem(1)">
                添加第一个动作
              </el-button>
            </EmptyState>
          </div>

          <div v-else class="day-list">
            <section
              v-for="group in dayGroups.groups"
              :key="group.dayIndex"
              class="day-block"
              :class="{ 'day-block--empty': !group.items.length }"
            >
              <header class="day-block__head">
                <div class="day-block__title">
                  <span class="day-block__index">{{ group.dayIndex }}</span>
                  第 {{ group.dayIndex }} 天
                  <span class="ft-muted" style="font-size: 11px">
                    {{ group.items.length ? `${group.items.length} 个动作` : '休息日' }}
                  </span>
                </div>
                <el-button
                  size="small"
                  text
                  type="primary"
                  :disabled="!isOwner"
                  @click="openAddItem(group.dayIndex)"
                >
                  + 加到这天
                </el-button>
              </header>

              <ul v-if="group.items.length" class="item-list">
                <li v-for="item in group.items" :key="`${group.dayIndex}-${item.id ?? item.exerciseName}-${item.exerciseName}`">
                  <div class="item-list__main">
                    <span class="item-list__name">{{ item.exerciseName }}</span>
                    <span class="item-list__detail">
                      <template v-if="item.duration_min">
                        {{ item.sets }} 组 × {{ item.duration_min }} 分钟
                      </template>
                      <template v-else>{{ item.sets }} 组 × {{ item.reps }} 次</template>
                      <template v-if="item.weight"> · {{ item.weight }} kg</template>
                      <template v-if="item.rest_seconds"> · 组间休息 {{ item.rest_seconds }}s</template>
                    </span>
                    <span v-if="item.note && item.exercise_id" class="item-list__note">{{ item.note }}</span>
                  </div>
                  <div class="item-list__actions">
                    <el-button
                      size="small"
                      text
                      :disabled="!isOwner"
                      @click="openEditItem(item, items.indexOf(item))"
                    >
                      修改
                    </el-button>
                    <el-button
                      size="small"
                      text
                      type="danger"
                      :disabled="!isOwner"
                      @click="handleDeleteItem(item, items.indexOf(item))"
                    >
                      删除
                    </el-button>
                  </div>
                </li>
              </ul>

              <p v-else class="day-block__rest">休息日 · 可安排拉伸或轻度有氧</p>
            </section>
          </div>
        </section>
      </div>
    </template>

    <!-- ============ 动作编辑弹窗 ============ -->
    <el-dialog
      v-model="itemVisible"
      :title="editingIndex >= 0 ? '修改动作' : '添加动作'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-width="96px">
        <el-form-item label="动作来源">
          <el-radio-group v-model="itemForm.source">
            <el-radio-button value="library">动作库</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="itemForm.source === 'library'" label="选择动作" prop="customName">
          <div class="picker-row">
            <el-input
              :model-value="itemForm.exerciseName"
              placeholder="点击右侧按钮从动作库选择"
              readonly
            />
            <el-button @click="openPicker">浏览动作库</el-button>
          </div>
        </el-form-item>

        <el-form-item v-else label="动作名称" prop="customName">
          <el-input v-model="itemForm.customName" placeholder="例如：壶铃摇摆" maxlength="60" />
        </el-form-item>

        <el-form-item label="安排在第几天" prop="dayIndex">
          <el-input-number
            v-model="itemForm.dayIndex"
            :min="1"
            :max="Number(form.cycle_days) || 1"
            controls-position="right"
            style="width: 160px"
          />
          <span class="ft-muted" style="margin-left: 10px; font-size: 12px">
            当前周期共 {{ form.cycle_days }} 天
          </span>
        </el-form-item>

        <div class="plan-edit__grid">
          <el-form-item label="组数" prop="sets">
            <el-input-number v-model="itemForm.sets" :min="0" :max="99" style="width: 100%" />
          </el-form-item>
          <el-form-item label="每组次数" prop="reps">
            <el-input-number v-model="itemForm.reps" :min="0" :max="999" style="width: 100%" />
          </el-form-item>
        </div>

        <div class="plan-edit__grid">
          <el-form-item label="建议重量" prop="weight">
            <el-input v-model.number="itemForm.weight" type="number" placeholder="kg，可留空" />
          </el-form-item>
          <el-form-item label="休息(秒)" prop="rest_seconds">
            <el-input-number v-model="itemForm.rest_seconds" :min="0" :max="3600" style="width: 100%" />
          </el-form-item>
        </div>

        <el-form-item label="有氧时长" prop="duration_min">
          <el-input v-model.number="itemForm.duration_min" type="number" placeholder="分钟，有氧/静力动作填" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="itemForm.note"
            type="textarea"
            :rows="2"
            maxlength="200"
            placeholder="发力要点、注意事项"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="itemVisible = false">取消</el-button>
        <el-button type="primary" :loading="itemSaving" @click="handleSaveItem">
          {{ isEdit ? '保存到服务器' : '加入计划' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ============ 动作库选择器 ============ -->
    <el-dialog v-model="pickerVisible" title="从动作库选择" width="620px" append-to-body>
      <div class="ft-toolbar" style="margin-bottom: 12px">
        <el-select v-model="exerciseCategory" placeholder="全部分类" clearable style="width: 140px" @change="handleExerciseSearch">
          <el-option
            v-for="cat in exerciseCategories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
        <el-input
          v-model="exerciseKeyword"
          placeholder="搜索动作名称"
          clearable
          style="width: 200px"
          @keyup.enter="handleExerciseSearch"
          @clear="handleExerciseSearch"
        >
          <template #append>
            <el-button @click="handleExerciseSearch">搜索</el-button>
          </template>
        </el-input>
        <span class="ft-toolbar__spacer"></span>
        <el-button size="small" :loading="exerciseLoading" @click="loadExercises">刷新</el-button>
      </div>

      <div v-if="exerciseLoading" class="ft-loading-text" style="padding: 30px 0">正在加载动作…</div>

      <EmptyState v-else-if="exerciseError" size="sm" icon="⚠️" :description="exerciseError" error>
        <el-button size="small" @click="loadExercises">重试</el-button>
      </EmptyState>

      <EmptyState v-else-if="!exerciseList.length" size="sm" icon="🔍" description="没有找到动作，换个关键词试试" />

      <ul v-else class="exercise-list">
        <li v-for="ex in exerciseList" :key="ex.id" class="exercise-item" @click="handlePickExercise(ex)">
          <div class="exercise-item__icon">
            <img v-if="ex.image_url" :src="ex.image_url" :alt="ex.name" />
            <span v-else>💪</span>
          </div>
          <div class="exercise-item__info">
            <p class="exercise-item__name">
              {{ ex.name }}
              <span class="ft-muted" style="font-size: 11px">{{ ex.name_en }}</span>
            </p>
            <p class="exercise-item__meta">
              <span v-if="ex.category_name">{{ ex.category_name }}</span>
              <span v-if="ex.equipment"> · {{ ex.equipment }}</span>
              <span v-if="ex.primary_muscles"> · {{ ex.primary_muscles }}</span>
            </p>
          </div>
          <span class="exercise-item__stars" :title="`难度 ${ex.difficulty}`">{{ stars(ex.difficulty) }}</span>
        </li>
      </ul>

      <div v-if="exerciseTotal > exercisePageSize" class="ft-pager">
        <el-pagination
          layout="prev, pager, next"
          :current-page="exercisePage"
          :page-size="exercisePageSize"
          :total="exerciseTotal"
          background
          small
          @current-change="
            (p) => {
              exercisePage = p
              loadExercises()
            }
          "
        />
      </div>

      <template #footer>
        <el-button @click="pickerVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.plan-edit {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
  gap: 16px;
  align-items: start;
}

.plan-edit__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.plan-edit__items-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.plan-edit__items-stat {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plan-edit__empty {
  padding: 10px 0;
}

.picker-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

/* 按天分组的动作列表 */
.day-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
  max-height: 560px;
  overflow-y: auto;
  padding-right: 4px;
}

.day-block {
  border: 1px solid var(--ft-border);
  border-radius: var(--ft-radius);
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
}

.day-block--empty {
  border-style: dashed;
  opacity: 0.75;
}

.day-block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.day-block__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.day-block__index {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: var(--ft-primary-soft);
  color: var(--ft-primary-light);
  font-size: 11px;
}

.day-block__rest {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.item-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border);
}

.item-list__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-list__name {
  font-size: 13px;
  color: var(--ft-text);
  font-weight: 500;
}

.item-list__detail {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.item-list__note {
  font-size: 11px;
  color: var(--ft-text-sub);
}

.item-list__actions {
  display: flex;
  gap: 2px;
  flex: 0 0 auto;
}

/* 动作库选择器 */
.exercise-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 380px;
  overflow-y: auto;
}

.exercise-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 11px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: all 0.16s ease;
}

.exercise-item:hover {
  border-color: rgba(255, 90, 31, 0.5);
  background: var(--ft-primary-soft);
}

.exercise-item__icon {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  font-size: 16px;
}

.exercise-item__icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.exercise-item__info {
  flex: 1;
  min-width: 0;
}

.exercise-item__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ft-text);
}

.exercise-item__meta {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.exercise-item__stars {
  color: var(--ft-warning);
  font-size: 11px;
  flex: 0 0 auto;
}

@media (max-width: 1080px) {
  .plan-edit {
    grid-template-columns: 1fr;
  }

  .plan-edit__grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
