<script setup>
/**
 * PlanDetail.vue 计划详情
 * 内容：基础信息、完成统计（含最近 30 天打卡日历）、按天动作明细、
 *       打卡、分享码生成 / 导入、训练提醒、打卡记录、收藏与删除
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  checkinPlan,
  createPlanReminder,
  deletePlan,
  deletePlanReminder,
  favoritePlan,
  getPlanCheckinRecords,
  getPlanDetail,
  getPlanReminders,
  getPlanStats,
  importSharedPlan,
  sharePlan,
  unfavoritePlan
} from '@/api/plan'
import { resolveAsset } from '@/api/request'

const route = useRoute()
const router = useRouter()

/** 计划 ID */
const planId = computed(() => route.params.id)

// ---------------- 基础状态 ----------------
const plan = ref(null)
const loading = ref(true)
const errorMsg = ref('')
/** 收藏操作中 */
const favoriteLoading = ref(false)

/** 目标文案映射 */
const goalMap = {
  keep_fit: '保持健康',
  gain_muscle: '增肌',
  lose_fat: '减脂',
  shape: '塑形',
  rehab: '康复'
}

/** 计划封面 */
const coverUrl = computed(() => resolveAsset(plan.value?.cover || ''))

/** 是否为本人计划 */
const isOwner = computed(() => plan.value?.is_owner !== false)

/** 按天分组的动作（第 1 天 … cycle_days 天） */
const dayGroups = computed(() => {
  const total = Number(plan.value?.cycle_days || 7)
  const groups = []
  for (let day = 1; day <= total; day += 1) {
    const dayItems = (plan.value?.items || []).filter((item) => Number(item.day_index) === day)
    groups.push({ dayIndex: day, items: dayItems })
  }
  return groups
})

/** 加载计划详情 */
async function loadPlan() {
  loading.value = true
  errorMsg.value = ''
  try {
    plan.value = await getPlanDetail(planId.value)
  } catch (error) {
    plan.value = null
    errorMsg.value = '计划加载失败，可能已被删除或没有查看权限'
  } finally {
    loading.value = false
  }
}

// ---------------- 完成统计 ----------------
const stats = ref(null)
const statsLoading = ref(true)
const statsError = ref('')

/** 加载完成统计 */
async function loadStats() {
  statsLoading.value = true
  statsError.value = ''
  try {
    stats.value = await getPlanStats(planId.value)
  } catch (error) {
    stats.value = null
    statsError.value = '统计数据加载失败'
  } finally {
    statsLoading.value = false
  }
}

/** 最近 30 天打卡日历 */
const calendarDays = computed(() => stats.value?.calendar || [])

/** 完成率百分比（取整展示） */
const completePercent = computed(() => Math.round(Number(stats.value?.complete_percent ?? 0)))

// ---------------- 打卡记录 ----------------
const records = ref([])
const recordsLoading = ref(true)
const recordsError = ref('')
const recordPage = ref(1)
const recordPageSize = ref(8)
const recordTotal = ref(0)

/** 加载打卡记录 */
async function loadRecords() {
  recordsLoading.value = true
  recordsError.value = ''
  try {
    const data = await getPlanCheckinRecords(planId.value, {
      page: recordPage.value,
      page_size: recordPageSize.value
    })
    records.value = Array.isArray(data) ? data : data?.items || []
    recordTotal.value = Number(data?.total ?? records.value.length)
  } catch (error) {
    records.value = []
    recordTotal.value = 0
    recordsError.value = '打卡记录加载失败'
  } finally {
    recordsLoading.value = false
  }
}

/** 打卡记录分页 */
function handleRecordPageChange(nextPage) {
  recordPage.value = nextPage
  loadRecords()
}

// ---------------- 打卡 ----------------
const checkinVisible = ref(false)
const checkinLoading = ref(false)
const checkinFormRef = ref(null)

/** 打卡表单 */
const checkinForm = reactive({
  day_index: 1,
  note: ''
})

/** 打卡表单校验 */
const checkinRules = {
  day_index: [
    { required: true, message: '请选择完成的是第几天', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (Number(value) < 1 || Number(value) > Number(plan.value?.cycle_days || 7)) {
          return callback(new Error(`天数需在 1-${plan.value?.cycle_days || 7} 之间`))
        }
        callback()
      },
      trigger: 'change'
    }
  ]
}

/** 打开打卡弹窗（默认定位到「今天对应周期第几天」） */
function openCheckinDialog() {
  const cycleDays = Number(plan.value?.cycle_days || 7)
  const today = new Date()
  // 周一为一周起点，简单取模得到默认天数
  const guess = plan.value?.cycle_type === 'daily' ? 1 : ((today.getDay() + 6) % 7) % cycleDays + 1
  checkinForm.day_index = guess
  checkinForm.note = ''
  checkinVisible.value = true
}

/** 提交打卡 */
async function handleCheckin() {
  if (!checkinFormRef.value) return
  try {
    await checkinFormRef.value.validate()
  } catch (error) {
    return
  }
  checkinLoading.value = true
  try {
    const data = await checkinPlan(planId.value, {
      day_index: Number(checkinForm.day_index),
      note: checkinForm.note.trim() || null
    })
    // 后端返回 { checkin, points_awarded, total_points }
    const points = Number(data?.points_awarded ?? 0)
    ElMessage.success(points > 0 ? `打卡成功，积分 +${points}` : '打卡成功')
    checkinVisible.value = false
    await Promise.all([loadStats(), loadRecords()])
  } catch (error) {
    /* 错误已提示（重复打卡会返回 409） */
  } finally {
    checkinLoading.value = false
  }
}

// ---------------- 收藏 ----------------
/** 切换收藏状态 */
async function handleToggleFavorite() {
  if (!plan.value) return
  favoriteLoading.value = true
  try {
    const data = plan.value.is_favorited
      ? await unfavoritePlan(planId.value)
      : await favoritePlan(planId.value)
    plan.value.is_favorited = Boolean(data?.is_favorited ?? !plan.value.is_favorited)
    if (data?.favorite_count !== undefined) plan.value.favorite_count = data.favorite_count
    ElMessage.success(plan.value.is_favorited ? '已收藏该计划' : '已取消收藏')
  } catch (error) {
    /* 错误已提示 */
  } finally {
    favoriteLoading.value = false
  }
}

// ---------------- 分享 ----------------
const shareVisible = ref(false)
const shareLoading = ref(false)
/** 分享有效期（小时），0 表示永久 */
const shareExpires = ref(0)
/** 已生成的分享信息 */
const shareInfo = ref(null)

/** 生成分享码 */
async function handleCreateShare() {
  shareLoading.value = true
  try {
    const payload = shareExpires.value > 0 ? { expires_hours: shareExpires.value } : {}
    shareInfo.value = await sharePlan(planId.value, payload)
    ElMessage.success('分享码已生成')
  } catch (error) {
    /* 错误已提示 */
  } finally {
    shareLoading.value = false
  }
}

/** 复制分享码到剪贴板 */
async function handleCopyShareCode() {
  const code = shareInfo.value?.share_code
  if (!code) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(code)
    } else {
      // 兜底方案：旧浏览器用临时 input 选中复制
      const input = document.createElement('input')
      input.value = code
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
    }
    ElMessage.success('分享码已复制')
  } catch (error) {
    ElMessage.warning(`复制失败，请手动记录分享码：${code}`)
  }
}

// ---------------- 导入分享码 ----------------
const importVisible = ref(false)
const importLoading = ref(false)
const importFormRef = ref(null)
const importForm = reactive({ code: '' })

/** 导入表单校验 */
const importRules = {
  code: [
    { required: true, message: '请输入分享码', trigger: 'blur' },
    { min: 4, max: 20, message: '分享码长度为 4-20 位', trigger: 'blur' }
  ]
}

/** 提交导入分享码 */
async function handleImportShare() {
  if (!importFormRef.value) return
  try {
    await importFormRef.value.validate()
  } catch (error) {
    return
  }
  importLoading.value = true
  try {
    const newPlan = await importSharedPlan(importForm.code.trim())
    ElMessage.success('导入成功，已添加到你的计划')
    importVisible.value = false
    importForm.code = ''
    if (newPlan?.id) router.push(`/plans/${newPlan.id}`)
  } catch (error) {
    /* 错误已提示 */
  } finally {
    importLoading.value = false
  }
}

// ---------------- 训练提醒 ----------------
const reminders = ref([])
const remindersLoading = ref(false)
const reminderSaving = ref(false)
const reminderVisible = ref(false)

/** 提醒表单 */
const reminderForm = reactive({
  remind_time: '20:00',
  weekdays: [1, 2, 3, 4, 5, 6, 7],
  enabled: true
})

/** 周几选项 */
const weekdayOptions = [
  { label: '一', value: 1 },
  { label: '二', value: 2 },
  { label: '三', value: 3 },
  { label: '四', value: 4 },
  { label: '五', value: 5 },
  { label: '六', value: 6 },
  { label: '日', value: 7 }
]

/** 加载提醒列表 */
async function loadReminders() {
  remindersLoading.value = true
  try {
    const data = await getPlanReminders(planId.value)
    reminders.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    reminders.value = []
  } finally {
    remindersLoading.value = false
  }
}

/** 保存提醒 */
async function handleSaveReminder() {
  if (!reminderForm.weekdays.length) {
    ElMessage.warning('请至少选择一个提醒的星期')
    return
  }
  reminderSaving.value = true
  try {
    await createPlanReminder(planId.value, {
      remind_time: reminderForm.remind_time,
      weekdays: [...reminderForm.weekdays].sort((a, b) => a - b).join(','),
      enabled: reminderForm.enabled
    })
    ElMessage.success('提醒已保存')
    reminderVisible.value = false
    loadReminders()
  } catch (error) {
    /* 错误已提示 */
  } finally {
    reminderSaving.value = false
  }
}

/** 删除提醒 */
async function handleDeleteReminder(reminder) {
  try {
    await deletePlanReminder(planId.value, reminder.id)
    ElMessage.success('提醒已删除')
    loadReminders()
  } catch (error) {
    /* 错误已提示 */
  }
}

// ---------------- 删除计划 ----------------
/** 删除当前计划 */
async function handleDelete() {
  try {
    await ElMessageBox.confirm('删除后动作与打卡记录都会清除，且无法恢复。', `删除「${plan.value?.name}」`, {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deletePlan(planId.value)
    ElMessage.success('计划已删除')
    router.replace('/plans')
  } catch (error) {
    /* 错误已提示 */
  }
}

// ---------------- 工具 ----------------
/** 动作展示名 */
function exerciseName(item) {
  return item?.exercise?.name || item?.note || '自定义动作'
}

/** 动作容量描述 */
function itemDetail(item) {
  const parts = []
  if (item?.duration_min) parts.push(`${item.sets} 组 × ${item.duration_min} 分钟`)
  else parts.push(`${item.sets} 组 × ${item.reps} 次`)
  if (item?.weight) parts.push(`${item.weight} kg`)
  if (item?.rest_seconds) parts.push(`休息 ${item.rest_seconds}s`)
  return parts.join(' · ')
}

onMounted(async () => {
  await loadPlan()
  await Promise.all([loadStats(), loadRecords(), loadReminders()])
})
</script>

<template>
  <div class="ft-page">
    <PageHeader
      :title="plan?.name || '计划详情'"
      :subtitle="plan?.description || '查看训练安排、完成情况并坚持打卡'"
      back-to="/plans"
    >
      <template #tag>
        <span v-if="plan" class="ft-chip" :class="plan.status === 'archived' ? '' : 'ft-chip--success'">
          {{ plan.status === 'archived' ? '已归档' : '进行中' }}
        </span>
        <span v-if="plan?.is_public" class="ft-chip ft-chip--primary">公开</span>
      </template>

      <template #actions>
        <el-button :loading="favoriteLoading" @click="handleToggleFavorite">
          {{ plan?.is_favorited ? '★ 已收藏' : '☆ 收藏' }}
        </el-button>
        <el-button @click="shareVisible = true">生成分享码</el-button>
        <el-button @click="importVisible = true">导入分享码</el-button>
        <el-button v-if="isOwner" @click="router.push(`/plans/${planId}/edit`)">编辑</el-button>
        <el-button v-if="isOwner" type="primary" @click="openCheckinDialog">今日打卡</el-button>
      </template>
    </PageHeader>

    <div v-if="loading" class="ft-loading-text">正在加载计划详情…</div>

    <EmptyState v-else-if="errorMsg" icon="⚠️" :description="errorMsg" error>
      <el-button @click="loadPlan">重新加载</el-button>
      <el-button @click="router.push('/plans')">返回列表</el-button>
    </EmptyState>

    <template v-else-if="plan">
      <!-- 封面 + 概要 -->
      <section class="ft-card detail-hero" :style="coverUrl ? { backgroundImage: `url(${coverUrl})` } : {}">
        <div class="detail-hero__mask">
          <div class="detail-hero__chips">
            <span class="ft-chip ft-chip--primary">{{ goalMap[plan.goal] || plan.goal || '保持健康' }}</span>
            <span class="ft-chip">{{ plan.cycle_type === 'daily' ? '每日循环' : '按周安排' }}</span>
            <span class="ft-chip">{{ plan.cycle_days }} 天 / 周期</span>
            <span class="ft-chip">{{ (plan.items || []).length }} 个动作</span>
            <span class="ft-chip ft-chip--warning">⭐ {{ plan.favorite_count || 0 }}</span>
          </div>
          <p class="detail-hero__desc">{{ plan.description || '暂无计划说明' }}</p>
          <p class="detail-hero__time ft-muted">
            创建于 {{ String(plan.created_at || '').slice(0, 10) || '—' }} · 更新于
            {{ String(plan.updated_at || '').slice(0, 10) || '—' }}
          </p>
        </div>
      </section>

      <!-- 完成统计 -->
      <h3 class="ft-section-title" style="margin-top: 20px">完成统计</h3>

      <div v-if="statsLoading" class="ft-loading-text" style="padding: 26px 0">正在统计…</div>

      <EmptyState v-else-if="statsError" size="sm" icon="⚠️" :description="statsError" error>
        <el-button size="small" @click="loadStats">重试</el-button>
      </EmptyState>

      <template v-else>
        <div class="ft-grid--4">
          <StatCard
            label="总打卡次数"
            :value="stats?.total_checkins ?? 0"
            unit="次"
            icon="✅"
            tone="primary"
          />
          <StatCard label="本周打卡" :value="stats?.week_checkins ?? 0" unit="次" icon="📅" tone="success" />
          <StatCard label="连续打卡" :value="stats?.streak_days ?? 0" unit="天" icon="🔥" tone="warning" />
          <StatCard
            label="完成率"
            :value="completePercent"
            unit="%"
            icon="📊"
            tone="info"
            :hint="`已打卡 ${stats?.checked_days ?? 0} / 预计 ${stats?.expected_days ?? 0} 天`"
          />
        </div>

        <!-- 最近 30 天打卡热度 -->
        <section class="ft-card" style="margin-top: 16px">
          <div class="heat-head">
            <h3 class="ft-section-title" style="margin: 0">最近 30 天打卡</h3>
            <span class="ft-chip ft-chip--primary">完成率 {{ completePercent }}%</span>
          </div>
          <el-progress
            :percentage="completePercent"
            :stroke-width="8"
            :show-text="false"
            color="#ff5a1f"
            style="margin: 12px 0 16px"
          />
          <div v-if="!calendarDays.length" class="ft-loading-text" style="padding: 16px 0">
            暂无打卡数据
          </div>
          <div v-else class="heat-grid">
            <div
              v-for="day in calendarDays"
              :key="String(day.date)"
              class="heat-cell"
              :class="{ 'heat-cell--on': day.checked }"
              :title="`${String(day.date).slice(0, 10)}${day.checked ? ` 已打卡（第 ${day.day_index} 天）` : ' 未打卡'}`"
            >
              <span>{{ String(day.date).slice(8, 10) }}</span>
            </div>
          </div>
        </section>
      </template>

      <!-- 动作明细 -->
      <h3 class="ft-section-title" style="margin-top: 20px">训练安排</h3>
      <section class="ft-card">
        <div class="day-detail-list">
          <div v-for="group in dayGroups" :key="group.dayIndex" class="day-detail">
            <header class="day-detail__head">
              <span class="day-detail__index">{{ group.dayIndex }}</span>
              <strong>第 {{ group.dayIndex }} 天</strong>
              <span class="ft-muted" style="font-size: 11px">
                {{ group.items.length ? `${group.items.length} 个动作` : '休息日' }}
              </span>
            </header>
            <ul v-if="group.items.length" class="day-detail__items">
              <li v-for="item in group.items" :key="item.id">
                <span class="day-detail__order">{{ item.sort_order }}</span>
                <span class="day-detail__name">{{ exerciseName(item) }}</span>
                <span class="day-detail__detail">{{ itemDetail(item) }}</span>
              </li>
            </ul>
            <p v-else class="day-detail__rest">休息日 · 建议拉伸或轻度有氧恢复</p>
          </div>
        </div>

        <EmptyState
          v-if="!(plan.items || []).length"
          size="sm"
          icon="🏋️"
          description="这个计划还没有安排动作"
        >
          <el-button v-if="isOwner" size="small" type="primary" @click="router.push(`/plans/${planId}/edit`)">
            去添加动作
          </el-button>
        </EmptyState>
      </section>

      <!-- 打卡记录 + 提醒 -->
      <div class="detail-bottom">
        <section class="ft-card">
          <div class="heat-head">
            <h3 class="ft-section-title" style="margin: 0">打卡记录</h3>
            <el-button link type="primary" size="small" @click="loadRecords">刷新</el-button>
          </div>

          <div v-if="recordsLoading" class="ft-loading-text" style="padding: 24px 0">加载中…</div>

          <EmptyState v-else-if="recordsError" size="sm" icon="⚠️" :description="recordsError" error>
            <el-button size="small" @click="loadRecords">重试</el-button>
          </EmptyState>

          <EmptyState
            v-else-if="!records.length"
            size="sm"
            icon="📝"
            description="还没有打卡记录，完成今天的训练后点「今日打卡」"
          >
            <el-button size="small" type="primary" :disabled="!isOwner" @click="openCheckinDialog">
              立即打卡
            </el-button>
          </EmptyState>

          <template v-else>
            <ul class="record-list">
              <li v-for="record in records" :key="record.id">
                <span class="record-list__date">{{ String(record.checkin_date).slice(0, 10) }}</span>
                <span class="ft-chip ft-chip--primary">第 {{ record.day_index }} 天</span>
                <span class="ft-chip ft-chip--success">{{ record.completed ? '已完成' : '未完成' }}</span>
                <span class="record-list__note">{{ record.note || '' }}</span>
              </li>
            </ul>
            <div v-if="recordTotal > recordPageSize" class="ft-pager">
              <el-pagination
                layout="prev, pager, next"
                :current-page="recordPage"
                :page-size="recordPageSize"
                :total="recordTotal"
                background
                small
                @current-change="handleRecordPageChange"
              />
            </div>
          </template>
        </section>

        <section class="ft-card">
          <div class="heat-head">
            <h3 class="ft-section-title" style="margin: 0">训练提醒</h3>
            <el-button v-if="isOwner" link type="primary" size="small" @click="reminderVisible = true">
              + 添加提醒
            </el-button>
          </div>

          <div v-if="remindersLoading" class="ft-loading-text" style="padding: 24px 0">加载中…</div>

          <EmptyState
            v-else-if="!reminders.length"
            size="sm"
            icon="⏰"
            description="还没有设置提醒，添加后每天到点提醒你训练"
          />

          <ul v-else class="reminder-list">
            <li v-for="reminder in reminders" :key="reminder.id">
              <div>
                <p class="reminder-list__time">{{ reminder.remind_time }}</p>
                <p class="reminder-list__days ft-muted">
                  每周 {{ String(reminder.weekdays || '').split(',').join('/') }} ·
                  {{ reminder.enabled ? '已启用' : '已停用' }}
                </p>
              </div>
              <el-button v-if="isOwner" size="small" text type="danger" @click="handleDeleteReminder(reminder)">
                删除
              </el-button>
            </li>
          </ul>

          <el-button v-if="isOwner" class="delete-plan-btn" size="small" text type="danger" @click="handleDelete">
            删除这个计划
          </el-button>
        </section>
      </div>
    </template>

    <!-- ============ 打卡弹窗 ============ -->
    <el-dialog v-model="checkinVisible" title="计划打卡" width="440px">
      <el-form ref="checkinFormRef" :model="checkinForm" :rules="checkinRules" label-width="110px">
        <el-form-item label="完成的是第几天" prop="day_index">
          <el-input-number
            v-model="checkinForm.day_index"
            :min="1"
            :max="Number(plan?.cycle_days) || 7"
            controls-position="right"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="打卡备注">
          <el-input
            v-model="checkinForm.note"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="今天的训练感受、完成情况"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="checkinVisible = false">取消</el-button>
        <el-button type="primary" :loading="checkinLoading" @click="handleCheckin">确认打卡</el-button>
      </template>
    </el-dialog>

    <!-- ============ 分享弹窗 ============ -->
    <el-dialog v-model="shareVisible" title="分享这个计划" width="460px">
      <p class="dialog-tip">生成分享码后，其他人可以凭码查看计划详情，或直接导入到自己的账号。</p>

      <el-form label-width="96px">
        <el-form-item label="有效期">
          <el-select v-model="shareExpires" style="width: 100%">
            <el-option label="永久有效" :value="0" />
            <el-option label="24 小时" :value="24" />
            <el-option label="7 天" :value="168" />
            <el-option label="30 天" :value="720" />
          </el-select>
        </el-form-item>
      </el-form>

      <div v-if="shareInfo" class="share-result">
        <p class="share-result__label">分享码</p>
        <div class="share-result__code">
          <strong>{{ shareInfo.share_code }}</strong>
          <el-button size="small" @click="handleCopyShareCode">复制</el-button>
        </div>
        <p class="ft-muted" style="font-size: 12px; margin-top: 8px">
          <template v-if="shareInfo.expires_at">
            有效期至 {{ String(shareInfo.expires_at).replace('T', ' ').slice(0, 16) }}
          </template>
          <template v-else>永久有效</template>
          · 已查看 {{ shareInfo.view_count || 0 }} 次
        </p>
      </div>

      <template #footer>
        <el-button @click="shareVisible = false">关闭</el-button>
        <el-button type="primary" :loading="shareLoading" @click="handleCreateShare">
          {{ shareInfo ? '重新生成' : '生成分享码' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ============ 导入分享码弹窗 ============ -->
    <el-dialog v-model="importVisible" title="导入分享的计划" width="420px">
      <p class="dialog-tip">输入他人分享的分享码，可以把该计划复制一份到你自己的账号下。</p>
      <el-form ref="importFormRef" :model="importForm" :rules="importRules" label-position="top">
        <el-form-item label="分享码" prop="code">
          <el-input v-model="importForm.code" placeholder="请输入分享码" maxlength="20" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" @click="handleImportShare">导入</el-button>
      </template>
    </el-dialog>

    <!-- ============ 提醒弹窗 ============ -->
    <el-dialog v-model="reminderVisible" title="添加训练提醒" width="440px">
      <el-form label-width="96px">
        <el-form-item label="提醒时间">
          <el-time-picker
            v-model="reminderForm.remind_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="选择提醒时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="提醒星期">
          <el-checkbox-group v-model="reminderForm.weekdays">
            <el-checkbox v-for="day in weekdayOptions" :key="day.value" :value="day.value">
              {{ day.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="reminderForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reminderVisible = false">取消</el-button>
        <el-button type="primary" :loading="reminderSaving" @click="handleSaveReminder">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 头部封面 */
.detail-hero {
  position: relative;
  padding: 0;
  overflow: hidden;
  background: linear-gradient(135deg, rgba(255, 90, 31, 0.22), rgba(50, 90, 180, 0.18));
  background-size: cover;
  background-position: center;
}

.detail-hero__mask {
  padding: 20px;
  background: linear-gradient(120deg, rgba(15, 17, 21, 0.72), rgba(15, 17, 21, 0.35));
  backdrop-filter: blur(2px);
}

.detail-hero__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-hero__desc {
  margin-top: 12px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--ft-text-sub);
  max-width: 820px;
}

.detail-hero__time {
  margin-top: 10px;
  font-size: 11px;
}

/* 打卡热度格 */
.heat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.heat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(28px, 1fr));
  gap: 5px;
}

.heat-cell {
  aspect-ratio: 1 / 1;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: var(--ft-text-dim);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ft-border);
}

.heat-cell--on {
  background: linear-gradient(160deg, rgba(255, 90, 31, 0.6), rgba(255, 90, 31, 0.28));
  border-color: rgba(255, 90, 31, 0.6);
  color: #fff;
}

/* 按天动作 */
.day-detail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.day-detail {
  border: 1px solid var(--ft-border);
  border-radius: var(--ft-radius);
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
}

.day-detail__head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.day-detail__index {
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

.day-detail__items {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.day-detail__items li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.03);
}

.day-detail__order {
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 10px;
  color: var(--ft-text-dim);
  background: rgba(255, 255, 255, 0.06);
}

.day-detail__name {
  flex: 1;
  color: var(--ft-text);
}

.day-detail__detail {
  color: var(--ft-text-dim);
  white-space: nowrap;
}

.day-detail__rest {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

/* 底部两栏 */
.detail-bottom {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 1fr);
  gap: 16px;
  margin-top: 16px;
  align-items: start;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.record-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ft-border);
  font-size: 12px;
}

.record-list__date {
  color: var(--ft-text);
  font-variant-numeric: tabular-nums;
}

.record-list__note {
  color: var(--ft-text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reminder-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.reminder-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
}

.reminder-list__time {
  font-size: 14px;
  font-weight: 600;
  color: var(--ft-primary-light);
}

.reminder-list__days {
  font-size: 11px;
}

.delete-plan-btn {
  margin-top: 14px;
}

.dialog-tip {
  font-size: 13px;
  color: var(--ft-text-sub);
  line-height: 1.7;
  margin-bottom: 14px;
}

.share-result {
  margin-top: 8px;
  padding: 12px;
  border-radius: var(--ft-radius);
  border: 1px dashed rgba(255, 90, 31, 0.45);
  background: var(--ft-primary-soft);
}

.share-result__label {
  font-size: 12px;
  color: var(--ft-text-dim);
}

.share-result__code {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
}

.share-result__code strong {
  font-size: 22px;
  letter-spacing: 3px;
  color: var(--ft-primary-light);
}

@media (max-width: 1000px) {
  .detail-bottom {
    grid-template-columns: 1fr;
  }
}
</style>
