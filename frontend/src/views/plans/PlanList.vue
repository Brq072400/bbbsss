<script setup>
/**
 * PlanList.vue 我的计划列表
 * 功能：状态筛选（进行中/已归档）、分页、查看/编辑/归档/删除、我的收藏计划
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  deletePlan,
  getFavoritePlans,
  getMyPlans,
  unfavoritePlan,
  updatePlan
} from '@/api/plan'
import { resolveAsset } from '@/api/request'

const router = useRouter()

/** 当前标签：mine 我的计划 / favorite 我的收藏 */
const activeTab = ref('mine')

// ---------------- 我的计划 ----------------
const plans = ref([])
const plansLoading = ref(true)
const plansError = ref('')
const page = ref(1)
const pageSize = ref(9)
const total = ref(0)
/** 状态筛选：'' 全部 / active 进行中 / archived 已归档 */
const statusFilter = ref('')

/** 状态选项 */
const statusOptions = [
  { label: '全部', value: '' },
  { label: '进行中', value: 'active' },
  { label: '已归档', value: 'archived' }
]

/** 目标可读文案（后端枚举：gain_muscle / lose_fat / shape / rehab / keep_fit） */
const goalMap = {
  keep_fit: '保持健康',
  gain_muscle: '增肌',
  lose_fat: '减脂',
  shape: '塑形',
  rehab: '康复',
  增肌: '增肌',
  减脂: '减脂',
  塑形: '塑形',
  康复: '康复'
}

/** 周期类型文案 */
const cycleMap = { daily: '每日循环', weekly: '每周循环' }

/** 把接口返回的列表统一成数组 */
function normalizeList(data) {
  if (Array.isArray(data)) return data
  return data?.items || data?.list || []
}

/** 计划的动作数量（后端字段为 items_count） */
function itemCountOf(plan) {
  return Number(plan.items_count ?? plan.item_count ?? (Array.isArray(plan.items) ? plan.items.length : 0))
}

/** 加载我的计划 */
async function loadPlans() {
  plansLoading.value = true
  plansError.value = ''
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    const data = await getMyPlans(params)
    plans.value = normalizeList(data)
    total.value = Number(data?.total ?? plans.value.length)
  } catch (error) {
    plans.value = []
    total.value = 0
    plansError.value = '计划列表加载失败，请稍后重试'
  } finally {
    plansLoading.value = false
  }
}

// ---------------- 我的收藏 ----------------
const favorites = ref([])
const favoritesLoading = ref(false)
const favoritesError = ref('')

/** 加载收藏的计划 */
async function loadFavorites() {
  favoritesLoading.value = true
  favoritesError.value = ''
  try {
    const data = await getFavoritePlans()
    const list = normalizeList(data)
    // 收藏接口可能直接返回计划对象，也可能返回 { plan: {...} }
    favorites.value = list.map((item) => item?.plan || item)
  } catch (error) {
    favorites.value = []
    favoritesError.value = '收藏列表加载失败'
  } finally {
    favoritesLoading.value = false
  }
}

// ---------------- 交互 ----------------
/** 切换状态筛选（回到第一页重新请求） */
function handleStatusChange(value) {
  statusFilter.value = value
  page.value = 1
  loadPlans()
}

/** 分页变化 */
function handlePageChange(nextPage) {
  page.value = nextPage
  loadPlans()
}

/** 切换标签页时按需加载 */
function handleTabChange(name) {
  if (name === 'favorite' && !favorites.value.length) loadFavorites()
}

/** 删除计划（二次确认） */
async function handleDelete(plan) {
  try {
    await ElMessageBox.confirm(
      `删除后「${plan.name}」的动作安排与打卡记录都会一起清除，且无法恢复。`,
      '删除计划',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch (error) {
    return // 取消
  }
  try {
    await deletePlan(plan.id)
    ElMessage.success('计划已删除')
    // 当前页删空后回退一页
    if (plans.value.length === 1 && page.value > 1) page.value -= 1
    loadPlans()
  } catch (error) {
    /* 错误已提示 */
  }
}

/** 归档 / 恢复计划（通过更新 status 实现） */
async function handleToggleStatus(plan) {
  const nextStatus = plan.status === 'archived' ? 'active' : 'archived'
  try {
    await updatePlan(plan.id, { status: nextStatus })
    ElMessage.success(nextStatus === 'archived' ? '计划已归档' : '计划已恢复进行中')
    loadPlans()
  } catch (error) {
    /* 错误已提示 */
  }
}

/** 取消收藏 */
async function handleUnfavorite(plan) {
  try {
    await unfavoritePlan(plan.id)
    ElMessage.success('已取消收藏')
    favorites.value = favorites.value.filter((item) => item.id !== plan.id)
  } catch (error) {
    /* 错误已提示 */
  }
}

/** 计划封面（无封面时用渐变占位） */
function coverOf(plan) {
  return resolveAsset(plan.cover || '')
}

/** 状态标签 */
function statusChip(plan) {
  return plan.status === 'archived'
    ? { cls: 'ft-chip', label: '已归档' }
    : { cls: 'ft-chip ft-chip--success', label: '进行中' }
}

/** 是否有进行中的计划（空状态文案区分） */
const emptyDesc = computed(() =>
  statusFilter.value === 'archived'
    ? '还没有归档的计划'
    : statusFilter.value === 'active'
      ? '还没有进行中的计划，创建一个开始训练吧'
      : '你还没有创建训练计划，先从一个模板开始试试'
)

onMounted(loadPlans)
</script>

<template>
  <div class="ft-page">
    <PageHeader title="我的计划" subtitle="管理你的训练安排，按周期执行并打卡">
      <template #actions>
        <el-button @click="router.push('/templates')">模板库</el-button>
        <el-button type="primary" @click="router.push('/plans/new')">新建计划</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- ============ 我的计划 ============ -->
      <el-tab-pane label="我的计划" name="mine">
        <div class="ft-toolbar">
          <el-radio-group :model-value="statusFilter" size="default" @change="handleStatusChange">
            <el-radio-button v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
          <span class="ft-toolbar__spacer"></span>
          <span class="ft-muted" style="font-size: 12px">共 {{ total }} 个计划</span>
          <el-button :loading="plansLoading" size="small" @click="loadPlans">刷新</el-button>
        </div>

        <div v-if="plansLoading" class="plan-grid">
          <div v-for="i in 6" :key="i" class="ft-card plan-card plan-card--skeleton">
            <el-skeleton :rows="3" animated />
          </div>
        </div>

        <EmptyState v-else-if="plansError" icon="⚠️" :description="plansError" error>
          <el-button @click="loadPlans">重新加载</el-button>
        </EmptyState>

        <EmptyState v-else-if="!plans.length" icon="📋" :description="emptyDesc">
          <el-button type="primary" @click="router.push('/plans/new')">新建计划</el-button>
          <el-button @click="router.push('/templates')">从模板创建</el-button>
        </EmptyState>

        <template v-else>
          <div class="plan-grid">
            <article v-for="plan in plans" :key="plan.id" class="ft-card ft-card--hover plan-card">
              <div class="plan-card__cover" :style="coverOf(plan) ? { backgroundImage: `url(${coverOf(plan)})` } : {}">
                <span v-if="!coverOf(plan)" class="plan-card__cover-fallback">🏋️</span>
                <span class="ft-chip" :class="statusChip(plan).cls">{{ statusChip(plan).label }}</span>
              </div>

              <div class="plan-card__body">
                <h3 class="plan-card__name" :title="plan.name">{{ plan.name }}</h3>
                <p class="plan-card__desc ft-ellipsis-2">
                  {{ plan.description || '暂无计划说明' }}
                </p>

                <div class="plan-card__chips">
                  <span class="ft-chip ft-chip--primary">{{ goalMap[plan.goal] || plan.goal || '保持健康' }}</span>
                  <span class="ft-chip">{{ cycleMap[plan.cycle_type] || plan.cycle_type || '每周循环' }}</span>
                  <span v-if="plan.cycle_days" class="ft-chip">{{ plan.cycle_days }} 天 / 周期</span>
                  <span class="ft-chip">{{ itemCountOf(plan) }} 个动作</span>
                  <span v-if="plan.favorite_count" class="ft-chip ft-chip--warning">⭐ {{ plan.favorite_count }}</span>
                </div>

                <p class="plan-card__time ft-muted">
                  创建于 {{ String(plan.created_at || '').slice(0, 10) || '—' }}
                </p>
              </div>

              <footer class="plan-card__actions">
                <el-button size="small" type="primary" @click="router.push(`/plans/${plan.id}`)">详情</el-button>
                <el-button size="small" @click="router.push(`/plans/${plan.id}/edit`)">编辑</el-button>
                <el-button size="small" text @click="handleToggleStatus(plan)">
                  {{ plan.status === 'archived' ? '恢复' : '归档' }}
                </el-button>
                <el-button size="small" text type="danger" @click="handleDelete(plan)">删除</el-button>
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
      </el-tab-pane>

      <!-- ============ 我的收藏 ============ -->
      <el-tab-pane label="我的收藏" name="favorite">
        <div class="ft-toolbar">
          <span class="ft-muted" style="font-size: 12px">共 {{ favorites.length }} 个收藏计划</span>
          <span class="ft-toolbar__spacer"></span>
          <el-button :loading="favoritesLoading" size="small" @click="loadFavorites">刷新</el-button>
        </div>

        <div v-if="favoritesLoading" class="ft-loading-text">正在加载收藏…</div>

        <EmptyState v-else-if="favoritesError" icon="⚠️" :description="favoritesError" error>
          <el-button @click="loadFavorites">重新加载</el-button>
        </EmptyState>

        <EmptyState v-else-if="!favorites.length" icon="⭐" description="还没有收藏任何计划，去模板库或详情页收藏喜欢的计划">
          <el-button type="primary" @click="router.push('/templates')">去模板库看看</el-button>
        </EmptyState>

        <div v-else class="plan-grid">
          <article v-for="plan in favorites" :key="plan.id" class="ft-card ft-card--hover plan-card">
            <div class="plan-card__cover" :style="coverOf(plan) ? { backgroundImage: `url(${coverOf(plan)})` } : {}">
              <span v-if="!coverOf(plan)" class="plan-card__cover-fallback">⭐</span>
              <span class="ft-chip ft-chip--warning">已收藏</span>
            </div>
            <div class="plan-card__body">
              <h3 class="plan-card__name">{{ plan.name }}</h3>
              <p class="plan-card__desc ft-ellipsis-2">{{ plan.description || '暂无计划说明' }}</p>
              <div class="plan-card__chips">
                <span class="ft-chip ft-chip--primary">{{ goalMap[plan.goal] || plan.goal || '保持健康' }}</span>
                <span class="ft-chip">{{ itemCountOf(plan) }} 个动作</span>
              </div>
            </div>
            <footer class="plan-card__actions">
              <el-button size="small" type="primary" @click="router.push(`/plans/${plan.id}`)">详情</el-button>
              <el-button size="small" text type="danger" @click="handleUnfavorite(plan)">取消收藏</el-button>
            </footer>
          </article>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(288px, 1fr));
  gap: 16px;
}

.plan-card {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.plan-card--skeleton {
  padding: 16px;
}

.plan-card__cover {
  position: relative;
  height: 96px;
  background: linear-gradient(135deg, rgba(255, 90, 31, 0.28), rgba(60, 110, 255, 0.16));
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.plan-card__cover .ft-chip {
  position: absolute;
  top: 10px;
  right: 10px;
  backdrop-filter: blur(6px);
}

.plan-card__cover-fallback {
  font-size: 30px;
  opacity: 0.65;
}

.plan-card__body {
  padding: 14px 16px 4px;
  flex: 1;
}

.plan-card__name {
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plan-card__desc {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ft-text-dim);
  min-height: 36px;
}

.plan-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.plan-card__time {
  margin-top: 10px;
  font-size: 11px;
}

.plan-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-top: 1px solid var(--ft-border);
  flex-wrap: wrap;
}
</style>
