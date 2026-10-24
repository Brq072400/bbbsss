<script setup>
/**
 * TemplateLibrary.vue 计划模板库
 * 功能：分类/目标/难度筛选、分页、模板详情（按天分组的动作明细）、一键使用模板生成我的计划
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { getTemplateDetail, getTemplates, useTemplate } from '@/api/plan'
import { resolveAsset } from '@/api/request'

const router = useRouter()

// ---------------- 筛选 ----------------
/** 分类：'' 全部 */
const category = ref('')
/** 目标：'' 全部（后端枚举 gain_muscle/lose_fat/shape/rehab/keep_fit） */
const goal = ref('')
/** 难度 1-5 */
const difficulty = ref('')

/** 目标中文映射 */
const goalMap = {
  keep_fit: '保持健康',
  gain_muscle: '增肌',
  lose_fat: '减脂',
  shape: '塑形',
  rehab: '康复'
}

/** 目标下拉选项 */
const goalOptions = [
  { label: '全部目标', value: '' },
  { label: '增肌', value: 'gain_muscle' },
  { label: '减脂', value: 'lose_fat' },
  { label: '塑形', value: 'shape' },
  { label: '康复', value: 'rehab' },
  { label: '保持健康', value: 'keep_fit' }
]

/** 难度下拉选项 */
const difficultyOptions = [
  { label: '全部难度', value: '' },
  { label: '1 星 · 入门', value: 1 },
  { label: '2 星 · 初级', value: 2 },
  { label: '3 星 · 中级', value: 3 },
  { label: '4 星 · 高级', value: 4 },
  { label: '5 星 · 硬核', value: 5 }
]

/** 默认分类（后端种子数据里的分类，实际会与接口返回的分类合并去重） */
const defaultCategories = ['新手', '减脂', '增肌']
/** 从已加载模板里收集到的分类，保证下拉选项与真实数据一致 */
const collectedCategories = ref([])

/** 分类下拉选项（默认 + 实际数据去重） */
const categoryOptions = computed(() => {
  const set = new Set([...defaultCategories, ...collectedCategories.value].filter(Boolean))
  return [
    { label: '全部分类', value: '' },
    ...Array.from(set).map((name) => ({ label: name, value: name }))
  ]
})

// ---------------- 列表 ----------------
const templates = ref([])
const loading = ref(true)
const errorMsg = ref('')
const page = ref(1)
const pageSize = ref(9)
const total = ref(0)

/** 统一列表结构 */
function normalizeList(data) {
  if (Array.isArray(data)) return data
  return data?.items || data?.list || []
}

/** 加载模板列表 */
async function loadTemplates() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (category.value) params.category = category.value
    if (goal.value) params.goal = goal.value
    if (difficulty.value !== '') params.difficulty = difficulty.value

    const data = await getTemplates(params)
    templates.value = normalizeList(data)
    total.value = Number(data?.total ?? templates.value.length)

    // 收集分类，供筛选下拉使用
    const next = new Set(collectedCategories.value)
    templates.value.forEach((tpl) => {
      if (tpl.category) next.add(tpl.category)
    })
    collectedCategories.value = Array.from(next)
  } catch (error) {
    templates.value = []
    total.value = 0
    errorMsg.value = '模板列表加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// ---------------- 详情 ----------------
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

/** 打开模板详情弹窗 */
async function openDetail(template) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getTemplateDetail(template.id)
  } catch (error) {
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

/** 详情里的按天分组（后端返回 items: [{ day_index, items: [...] }]） */
const detailDays = computed(() => {
  const groups = detail.value?.items || []
  return groups
    .map((group) => ({
      dayIndex: Number(group.day_index ?? 1),
      items: group.items || []
    }))
    .sort((a, b) => a.dayIndex - b.dayIndex)
})

// ---------------- 使用模板 ----------------
const useVisible = ref(false)
const useLoading = ref(false)
const useTarget = ref(null)
/** 使用模板时可选的自定义计划名 */
const useForm = reactive({ name: '' })

/** 打开「使用模板」弹窗 */
function openUseDialog(template) {
  useTarget.value = template
  useForm.name = template?.name || ''
  useVisible.value = true
}

/** 确认使用模板创建计划 */
async function handleUseTemplate() {
  if (!useTarget.value) return
  useLoading.value = true
  try {
    const newPlan = await useTemplate(useTarget.value.id, useForm.name.trim() || undefined)
    ElMessage.success('已按模板创建计划，可在「我的计划」中查看')
    useVisible.value = false
    // 后端返回新建计划详情，直接跳到详情页
    if (newPlan?.id) router.push(`/plans/${newPlan.id}`)
    else router.push('/plans')
  } catch (error) {
    /* 错误已提示 */
  } finally {
    useLoading.value = false
  }
}

// ---------------- 交互 ----------------
/** 筛选条件变化后重新查询 */
function applyFilters() {
  page.value = 1
  loadTemplates()
}

/** 重置筛选 */
function resetFilters() {
  category.value = ''
  goal.value = ''
  difficulty.value = ''
  page.value = 1
  loadTemplates()
}

/** 分页切换 */
function handlePageChange(nextPage) {
  page.value = nextPage
  loadTemplates()
}

/** 模板封面 */
function coverOf(template) {
  return resolveAsset(template.cover || '')
}

/** 模板动作总条数 */
function itemsCountOf(template) {
  if (template.items_count) return Number(template.items_count)
  const groups = template.items || []
  return groups.reduce((sum, group) => sum + (group.items?.length || 0), 0)
}

/** 难度星星展示 */
function stars(level) {
  const n = Math.max(1, Math.min(5, Number(level) || 1))
  return '★'.repeat(n) + '☆'.repeat(5 - n)
}

onMounted(loadTemplates)
</script>

<template>
  <div class="ft-page">
    <PageHeader title="计划模板库" subtitle="官方精选训练模板，一键套用后还能自由调整动作">
      <template #actions>
        <el-button @click="router.push('/plans')">我的计划</el-button>
        <el-button type="primary" @click="router.push('/plans/new')">从零新建</el-button>
      </template>
    </PageHeader>

    <!-- 筛选 -->
    <div class="ft-toolbar">
      <el-select v-model="category" placeholder="分类" style="width: 140px" @change="applyFilters">
        <el-option v-for="opt in categoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>

      <el-select v-model="goal" placeholder="目标" style="width: 140px" @change="applyFilters">
        <el-option v-for="opt in goalOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>

      <el-select v-model="difficulty" placeholder="难度" style="width: 150px" @change="applyFilters">
        <el-option
          v-for="opt in difficultyOptions"
          :key="String(opt.value)"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-button @click="resetFilters">重置</el-button>
      <span class="ft-toolbar__spacer"></span>
      <span class="ft-muted" style="font-size: 12px">共 {{ total }} 个模板</span>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="tpl-grid">
      <div v-for="i in 6" :key="i" class="ft-card tpl-card tpl-card--skeleton">
        <el-skeleton :rows="4" animated />
      </div>
    </div>

    <EmptyState v-else-if="errorMsg" icon="⚠️" :description="errorMsg" error>
      <el-button @click="loadTemplates">重新加载</el-button>
    </EmptyState>

    <EmptyState v-else-if="!templates.length" icon="🧩" description="没有符合条件的模板，换个筛选条件试试">
      <el-button @click="resetFilters">重置筛选</el-button>
    </EmptyState>

    <template v-else>
      <div class="tpl-grid">
        <article v-for="tpl in templates" :key="tpl.id" class="ft-card ft-card--hover tpl-card">
          <div class="tpl-card__cover" :style="coverOf(tpl) ? { backgroundImage: `url(${coverOf(tpl)})` } : {}">
            <span v-if="!coverOf(tpl)" class="tpl-card__cover-fallback">🧩</span>
            <span v-if="tpl.is_official" class="ft-chip ft-chip--primary tpl-card__official">官方</span>
            <span class="tpl-card__use">🔥 {{ tpl.use_count || 0 }} 人使用</span>
          </div>

          <div class="tpl-card__body">
            <h3 class="tpl-card__name">{{ tpl.name }}</h3>
            <p class="tpl-card__desc ft-ellipsis-2">{{ tpl.description || '暂无模板说明' }}</p>

            <div class="tpl-card__chips">
              <span v-if="tpl.category" class="ft-chip ft-chip--primary">{{ tpl.category }}</span>
              <span class="ft-chip">{{ goalMap[tpl.goal] || tpl.goal || '保持健康' }}</span>
              <span class="ft-chip">{{ tpl.cycle_type === 'daily' ? '每日循环' : '按周安排' }}</span>
              <span class="ft-chip">{{ tpl.cycle_days }} 天</span>
              <span class="ft-chip">{{ itemsCountOf(tpl) }} 个动作</span>
            </div>

            <p class="tpl-card__stars" :title="`难度 ${tpl.difficulty} / 5`">
              {{ stars(tpl.difficulty) }}
            </p>
          </div>

          <footer class="tpl-card__actions">
            <el-button size="small" @click="openDetail(tpl)">查看详情</el-button>
            <el-button size="small" type="primary" @click="openUseDialog(tpl)">使用模板</el-button>
          </footer>
        </article>
      </div>

      <div class="ft-pager">
        <el-pagination
          layout="prev, pager, next, total"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          background
          @current-change="handlePageChange"
        />
      </div>
    </template>

    <!-- ============ 模板详情弹窗 ============ -->
    <el-dialog v-model="detailVisible" :title="detail?.name || '模板详情'" width="680px">
      <div v-if="detailLoading" class="ft-loading-text">正在加载模板详情…</div>
      <template v-else-if="detail">
        <div class="tpl-detail__meta">
          <span class="ft-chip ft-chip--primary">{{ detail.category || '通用' }}</span>
          <span class="ft-chip">{{ goalMap[detail.goal] || detail.goal || '保持健康' }}</span>
          <span class="ft-chip">{{ detail.cycle_type === 'daily' ? '每日循环' : '按周安排' }}</span>
          <span class="ft-chip">{{ detail.cycle_days }} 天 / 周期</span>
          <span class="ft-chip ft-chip--warning">{{ stars(detail.difficulty) }}</span>
        </div>
        <p class="tpl-detail__desc">{{ detail.description || '暂无模板说明' }}</p>

        <div v-if="!detailDays.length" class="tpl-detail__empty">
          <EmptyState size="sm" icon="📦" description="该模板暂无动作明细" />
        </div>

        <div v-else class="tpl-detail__days">
          <section v-for="day in detailDays" :key="day.dayIndex" class="tpl-day">
            <h4 class="tpl-day__title">
              第 {{ day.dayIndex }} 天
              <span class="ft-muted">{{ day.items.length }} 个动作</span>
            </h4>
            <ul class="tpl-day__items">
              <li v-for="(item, index) in day.items" :key="index">
                <span class="tpl-day__index">{{ index + 1 }}</span>
                <span class="tpl-day__name">{{ item.exercise || item.note || '自定义动作' }}</span>
                <span class="tpl-day__detail">
                  <template v-if="item.duration_min">{{ item.sets }} 组 × {{ item.duration_min }} 分钟</template>
                  <template v-else>{{ item.sets }} 组 × {{ item.reps }} 次</template>
                  <template v-if="item.weight"> · {{ item.weight }} kg</template>
                  <template v-if="item.rest_seconds"> · 休息 {{ item.rest_seconds }}s</template>
                </span>
              </li>
            </ul>
          </section>
        </div>
      </template>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="detail && openUseDialog(detail)">使用这个模板</el-button>
      </template>
    </el-dialog>

    <!-- ============ 使用模板弹窗 ============ -->
    <el-dialog v-model="useVisible" title="使用模板创建计划" width="440px">
      <p class="use-tip">
        将根据模板「{{ useTarget?.name }}」生成一份属于你的计划，生成后可以自由增删动作。
      </p>
      <el-form label-position="top">
        <el-form-item label="计划名称">
          <el-input v-model="useForm.name" placeholder="默认使用模板名称" maxlength="100" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="useVisible = false">取消</el-button>
        <el-button type="primary" :loading="useLoading" @click="handleUseTemplate">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tpl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.tpl-card {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tpl-card--skeleton {
  padding: 16px;
}

.tpl-card__cover {
  position: relative;
  height: 104px;
  background: linear-gradient(135deg, rgba(255, 90, 31, 0.26), rgba(60, 110, 255, 0.18));
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tpl-card__cover-fallback {
  font-size: 30px;
  opacity: 0.6;
}

.tpl-card__official {
  position: absolute;
  top: 10px;
  left: 10px;
}

.tpl-card__use {
  position: absolute;
  bottom: 8px;
  right: 10px;
  font-size: 11px;
  color: #fff;
  background: rgba(0, 0, 0, 0.5);
  padding: 1px 8px;
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.tpl-card__body {
  padding: 13px 15px 6px;
  flex: 1;
}

.tpl-card__name {
  font-size: 15px;
  line-height: 1.4;
}

.tpl-card__desc {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ft-text-dim);
  min-height: 36px;
}

.tpl-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.tpl-card__stars {
  margin-top: 10px;
  color: var(--ft-warning);
  font-size: 12px;
  letter-spacing: 2px;
}

.tpl-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--ft-border);
}

/* 详情弹窗 */
.tpl-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.tpl-detail__desc {
  font-size: 13px;
  color: var(--ft-text-sub);
  line-height: 1.7;
  padding: 10px 12px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border);
}

.tpl-detail__days {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 380px;
  overflow-y: auto;
}

.tpl-day {
  border: 1px solid var(--ft-border);
  border-radius: var(--ft-radius);
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
}

.tpl-day__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 8px;
}

.tpl-day__title span {
  font-size: 11px;
  font-weight: 400;
}

.tpl-day__items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tpl-day__items li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.tpl-day__index {
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--ft-primary-soft);
  color: var(--ft-primary-light);
  font-size: 10px;
}

.tpl-day__name {
  flex: 1;
  min-width: 0;
  color: var(--ft-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tpl-day__detail {
  color: var(--ft-text-dim);
  white-space: nowrap;
}

.use-tip {
  font-size: 13px;
  color: var(--ft-text-sub);
  margin-bottom: 14px;
  line-height: 1.7;
}
</style>
