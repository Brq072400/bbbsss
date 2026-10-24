<script setup>
/**
 * Checkin.vue 每日签到
 * 内容：签到按钮、签到统计、月历网格（可切换年月）、连续签到奖励说明、本月签到记录
 */
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'
import { checkin, getCheckinCalendar, getCheckinStats, getLevelRules } from '@/api/user'

const userStore = useUserStore()

// ---------------- 状态 ----------------
/** 统计信息 */
const stats = ref({
  current_streak: 0,
  total_days: 0,
  month_days: 0,
  today_checked: false,
  last_checkin_date: ''
})
/** 日历数据 */
const calendar = ref({ year: 0, month: 0, days: [], checked_days: 0, today_checked: false })
/** 等级规则（含签到积分规则，用于奖励说明） */
const levelRules = ref(null)

const statsLoading = ref(true)
const calendarLoading = ref(true)
const rulesLoading = ref(true)
const checkinLoading = ref(false)
const calendarError = ref('')

const now = new Date()
/** 当前展示的年月 */
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth() + 1)

/** 今天是否已签到 */
const todayChecked = computed(() => Boolean(stats.value.today_checked || calendar.value.today_checked))

/** 是否正在看当月（非当月时不显示签到按钮提示） */
const isCurrentMonth = computed(
  () => viewYear.value === now.getFullYear() && viewMonth.value === now.getMonth() + 1
)

/** 标题：2024 年 6 月 */
const monthLabel = computed(() => `${viewYear.value} 年 ${viewMonth.value} 月`)

/**
 * 生成月历网格数据
 * 前面补空占位，让 1 号对齐到正确的星期
 */
const calendarCells = computed(() => {
  const days = calendar.value.days || []
  if (!days.length) return []
  // 用 1 号是星期几来决定前面补几个空格子（周一为一周起点）
  const first = new Date(viewYear.value, viewMonth.value - 1, 1)
  const firstWeekday = (first.getDay() + 6) % 7 // 0=周一 … 6=周日
  const cells = []
  for (let i = 0; i < firstWeekday; i += 1) cells.push({ empty: true, key: `empty-${i}` })
  days.forEach((day) => {
    cells.push({
      key: day.date,
      empty: false,
      day: day.day,
      date: day.date,
      checked: Boolean(day.checked),
      isToday: Boolean(day.is_today),
      streak: day.streak,
      points: day.points_awarded
    })
  })
  return cells
})

/** 星期表头 */
const weekHeads = ['一', '二', '三', '四', '五', '六', '日']

/** 本月已签到天数（优先用日历统计） */
const monthCheckedDays = computed(() => calendar.value.checked_days || stats.value.month_days || 0)

/** 连续签到奖励说明（来自等级规则接口） */
const rewardRules = computed(() => {
  const base = levelRules.value?.checkin_points ?? 0
  const bonus = levelRules.value?.checkin_streak_bonus ?? 0
  const cap = levelRules.value?.checkin_streak_bonus_cap ?? 0
  return { base, bonus, cap }
})

/** 连续签到奖励档位表格（按 7 天、14 天、30 天展示累计额外奖励，纯前端推算） */
const rewardTiers = computed(() => {
  const { base, bonus, cap } = rewardRules.value
  if (!base && !bonus) return []
  return [1, 3, 7, 14, 30].map((days) => {
    const bonusPerDay = Math.min(bonus * days, cap || bonus * days)
    return {
      days,
      single: base,
      bonus: bonusPerDay,
      total: base + Math.min(bonus * (days - 1), cap || bonus * (days - 1))
    }
  })
})

/** 本月签到记录（从日历里筛出已签到的日子，倒序） */
const checkedList = computed(() =>
  (calendar.value.days || [])
    .filter((day) => day.checked)
    .map((day) => ({
      date: day.date,
      day: day.day,
      streak: day.streak,
      points: day.points_awarded
    }))
    .sort((a, b) => (a.date < b.date ? 1 : -1))
)

/** 把日期对象格式化为 YYYY-MM月 */
function formatMonth(year, month) {
  return `${year}-${String(month).padStart(2, '0')}`
}

// ---------------- 数据加载 ----------------
/** 加载签到统计 */
async function loadStats() {
  statsLoading.value = true
  try {
    const data = await getCheckinStats()
    stats.value = {
      current_streak: Number(data?.current_streak ?? 0),
      total_days: Number(data?.total_days ?? 0),
      month_days: Number(data?.month_days ?? 0),
      today_checked: Boolean(data?.today_checked),
      last_checkin_date: data?.last_checkin_date || ''
    }
  } catch (error) {
    /* 错误已提示 */
  } finally {
    statsLoading.value = false
  }
}

/** 加载指定年月的签到日历 */
async function loadCalendar() {
  calendarLoading.value = true
  calendarError.value = ''
  try {
    const data = await getCheckinCalendar({ year: viewYear.value, month: viewMonth.value })
    calendar.value = {
      year: Number(data?.year ?? viewYear.value),
      month: Number(data?.month ?? viewMonth.value),
      days: data?.days || [],
      checked_days: Number(data?.checked_days ?? 0),
      today_checked: Boolean(data?.today_checked)
    }
  } catch (error) {
    calendar.value = { year: viewYear.value, month: viewMonth.value, days: [], checked_days: 0 }
    calendarError.value = '签到日历加载失败，请稍后重试'
  } finally {
    calendarLoading.value = false
  }
}

/** 加载等级/签到积分规则 */
async function loadRules() {
  rulesLoading.value = true
  try {
    levelRules.value = await getLevelRules()
  } catch (error) {
    levelRules.value = null
  } finally {
    rulesLoading.value = false
  }
}

/** 刷新全部数据 */
async function refreshAll() {
  await Promise.all([loadStats(), loadCalendar(), loadRules()])
}

// ---------------- 交互 ----------------
/** 点击签到 */
async function handleCheckin() {
  if (todayChecked.value) {
    ElMessage.info('今天已经签到过了，明天记得再来')
    return
  }
  checkinLoading.value = true
  try {
    const data = await checkin()
    const points = Number(data?.points_awarded ?? 0)
    const bonus = Number(data?.bonus ?? 0)
    const streak = Number(data?.streak ?? 0)
    ElMessage.success(
      `签到成功！连续 ${streak} 天，获得 ${points} 积分${bonus > 0 ? `（含连续奖励 ${bonus}）` : ''}`
    )
    // 签到后刷新统计、日历与用户资料（积分/等级变化）
    await Promise.all([loadStats(), loadCalendar(), userStore.fetchProfile()])
  } catch (error) {
    /* 错误已提示 */
  } finally {
    checkinLoading.value = false
  }
}

/** 切换到上个月 */
function prevMonth() {
  if (viewMonth.value === 1) {
    viewYear.value -= 1
    viewMonth.value = 12
  } else {
    viewMonth.value -= 1
  }
}

/** 切换到下个月（不能超过当前月） */
function nextMonth() {
  const nextYear = viewMonth.value === 12 ? viewYear.value + 1 : viewYear.value
  const nextMonthValue = viewMonth.value === 12 ? 1 : viewMonth.value + 1
  // 不允许查看未来月份
  if (nextYear > now.getFullYear() || (nextYear === now.getFullYear() && nextMonthValue > now.getMonth() + 1)) {
    ElMessage.info('已经是当前月份了')
    return
  }
  viewYear.value = nextYear
  viewMonth.value = nextMonthValue
}

/** 回到本月 */
function goToday() {
  viewYear.value = now.getFullYear()
  viewMonth.value = now.getMonth() + 1
}

// ---------------- 生命周期 ----------------
onMounted(refreshAll)

/** 年月变化时重新拉日历 */
watch([viewYear, viewMonth], loadCalendar)
</script>

<template>
  <div class="ft-page">
    <PageHeader title="每日签到" subtitle="每天签到累积积分，连续天数越多奖励越高">
      <template #actions>
        <el-button :loading="calendarLoading || statsLoading" @click="refreshAll">刷新</el-button>
        <el-button type="primary" :loading="checkinLoading" :disabled="todayChecked" @click="handleCheckin">
          {{ todayChecked ? '今日已签到 ✓' : '立即签到' }}
        </el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="ft-grid--4" style="margin-bottom: 18px">
      <StatCard
        label="连续签到"
        :value="stats.current_streak"
        unit="天"
        icon="🔥"
        tone="primary"
        :loading="statsLoading"
        :hint="stats.last_checkin_date ? `上次签到 ${stats.last_checkin_date}` : '还没有签到记录'"
      />
      <StatCard
        label="累计签到"
        :value="stats.total_days"
        unit="天"
        icon="🏅"
        tone="success"
        :loading="statsLoading"
        hint="自注册以来累计"
      />
      <StatCard
        label="本月签到"
        :value="monthCheckedDays"
        unit="天"
        icon="📅"
        tone="warning"
        :loading="statsLoading || calendarLoading"
        :hint="monthLabel"
      />
      <StatCard
        label="今日状态"
        :value="todayChecked ? '已签到' : '待签到'"
        icon="✅"
        :tone="todayChecked ? 'success' : 'danger'"
        :loading="statsLoading"
        :hint="todayChecked ? '保持连续记录' : '签到可得积分奖励'"
      />
    </div>

    <div class="checkin">
      <!-- ============ 月历 ============ -->
      <section class="ft-card">
        <div class="cal-head">
          <div class="cal-head__nav">
            <el-button size="small" circle @click="prevMonth">‹</el-button>
            <strong class="cal-head__month">{{ monthLabel }}</strong>
            <el-button size="small" circle @click="nextMonth">›</el-button>
            <el-button v-if="!isCurrentMonth" link size="small" @click="goToday">回到本月</el-button>
          </div>
          <div class="cal-head__legend">
            <span><i class="dot dot--checked"></i>已签到</span>
            <span><i class="dot dot--today"></i>今天</span>
            <span class="cal-head__count">本月 {{ monthCheckedDays }} 天</span>
          </div>
        </div>

        <div class="cal-week">
          <span v-for="head in weekHeads" :key="head">{{ head }}</span>
        </div>

        <div v-if="calendarLoading" class="ft-loading-text">正在加载签到日历…</div>

        <EmptyState v-else-if="calendarError" icon="⚠️" :description="calendarError" error>
          <el-button size="small" @click="loadCalendar">重新加载</el-button>
        </EmptyState>

        <EmptyState v-else-if="!calendarCells.length" icon="📅" description="该月没有签到数据" />

        <div v-else class="cal-grid">
          <div
            v-for="cell in calendarCells"
            :key="cell.key"
            class="cal-cell"
            :class="{
              'cal-cell--empty': cell.empty,
              'cal-cell--checked': cell.checked,
              'cal-cell--today': cell.isToday
            }"
            :title="
              cell.empty
                ? ''
                : `${cell.date}${cell.checked ? ` 已签到（连续 ${cell.streak} 天）` : ' 未签到'}`
            "
          >
            <template v-if="!cell.empty">
              <span class="cal-cell__day">{{ cell.day }}</span>
              <span v-if="cell.checked" class="cal-cell__mark">
                {{ cell.points ? `+${cell.points}` : '✓' }}
              </span>
              <span v-if="cell.streak > 1" class="cal-cell__streak">🔥{{ cell.streak }}</span>
            </template>
          </div>
        </div>

        <p class="cal-foot">
          提示：每日可签到 1 次，签到日按自然日（{{ formatMonth(viewYear, viewMonth) }}）统计。
        </p>
      </section>

      <!-- ============ 右侧：规则 + 本月记录 ============ -->
      <aside class="checkin__side">
        <section class="ft-card">
          <h3 class="ft-section-title">连续签到奖励</h3>
          <div v-if="rulesLoading" class="ft-loading-text" style="padding: 22px 0">加载中…</div>
          <template v-else-if="rewardRules.base || rewardRules.bonus">
            <p class="reward-desc">
              每日签到基础
              <strong class="ft-primary">{{ rewardRules.base }}</strong> 积分；连续签到每天额外
              <strong class="ft-primary">+{{ rewardRules.bonus }}</strong> 积分，单日额外奖励上限
              <strong class="ft-primary">{{ rewardRules.cap }}</strong> 积分。
            </p>
            <table class="reward-table">
              <thead>
                <tr>
                  <th>连续天数</th>
                  <th>当日可得</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tier in rewardTiers" :key="tier.days">
                  <td>{{ tier.days }} 天</td>
                  <td>{{ tier.single }} + {{ tier.bonus }} 额外</td>
                </tr>
              </tbody>
            </table>
            <p class="reward-tip">中断一天连续天数会重新计算，保持每天来打卡吧。</p>
          </template>
          <EmptyState v-else size="sm" icon="🎁" description="暂未获取到签到奖励规则" />
        </section>

        <section class="ft-card">
          <h3 class="ft-section-title">本月签到明细</h3>
          <div v-if="calendarLoading" class="ft-loading-text" style="padding: 22px 0">加载中…</div>
          <EmptyState
            v-else-if="!checkedList.length"
            size="sm"
            icon="🗓️"
            description="本月还没有签到记录"
          />
          <ul v-else class="record-list">
            <li v-for="item in checkedList" :key="item.date">
              <div class="record-list__date">
                <strong>{{ item.day }}</strong>
                <span>日</span>
              </div>
              <div class="record-list__info">
                <p>{{ item.date }}</p>
                <p class="ft-muted">
                  连续 {{ item.streak }} 天<template v-if="item.points"> · 获得 {{ item.points }} 积分</template>
                </p>
              </div>
              <span class="ft-chip ft-chip--success">已签到</span>
            </li>
          </ul>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.checkin {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
  gap: 16px;
  align-items: start;
}

/* ---------------- 日历头部 ---------------- */
.cal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.cal-head__nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cal-head__month {
  font-size: 16px;
  min-width: 116px;
  text-align: center;
}

.cal-head__legend {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

.cal-head__legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot--checked {
  background: var(--ft-primary);
}

.dot--today {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.25);
}

.cal-head__count {
  color: var(--ft-primary-light);
}

/* ---------------- 日历网格 ---------------- */
.cal-week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
  margin-bottom: 6px;
}

.cal-week span {
  text-align: center;
  font-size: 12px;
  color: var(--ft-text-dim);
  padding: 6px 0;
}

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.cal-cell {
  position: relative;
  aspect-ratio: 1 / 1;
  min-height: 52px;
  border-radius: 12px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  transition: transform 0.16s ease, border-color 0.16s ease;
}

.cal-cell:not(.cal-cell--empty):hover {
  transform: translateY(-2px);
  border-color: rgba(255, 90, 31, 0.5);
}

.cal-cell--empty {
  border: 1px dashed rgba(255, 255, 255, 0.05);
  background: transparent;
}

.cal-cell--checked {
  background: linear-gradient(160deg, rgba(255, 90, 31, 0.28), rgba(255, 90, 31, 0.1));
  border-color: rgba(255, 90, 31, 0.55);
  box-shadow: inset 0 0 18px rgba(255, 90, 31, 0.18);
}

.cal-cell--today {
  border-color: rgba(255, 255, 255, 0.6);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.18);
}

.cal-cell__day {
  font-size: 14px;
  font-weight: 600;
  color: var(--ft-text);
}

.cal-cell__mark {
  font-size: 10px;
  color: var(--ft-primary-light);
}

.cal-cell__streak {
  position: absolute;
  top: 3px;
  right: 4px;
  font-size: 9px;
  color: #ffb08a;
}

.cal-foot {
  margin-top: 14px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

/* ---------------- 右侧 ---------------- */
.checkin__side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.reward-desc {
  font-size: 12px;
  line-height: 1.9;
  color: var(--ft-text-sub);
}

.reward-table {
  width: 100%;
  margin-top: 12px;
  border-collapse: collapse;
  font-size: 12px;
}

.reward-table th,
.reward-table td {
  padding: 7px 8px;
  text-align: left;
  border-bottom: 1px solid var(--ft-border);
  color: var(--ft-text-sub);
}

.reward-table th {
  color: var(--ft-text-dim);
  font-weight: 500;
}

.reward-tip {
  margin-top: 10px;
  font-size: 11px;
  color: var(--ft-text-dim);
}

/* 明细列表 */
.record-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 340px;
  overflow-y: auto;
}

.record-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 11px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
}

.record-list__date {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--ft-primary-soft);
  color: var(--ft-primary-light);
  line-height: 1;
}

.record-list__date strong {
  font-size: 15px;
}

.record-list__date span {
  font-size: 9px;
}

.record-list__info {
  flex: 1;
  min-width: 0;
  font-size: 12px;
}

.record-list__info p:last-child {
  font-size: 11px;
}

@media (max-width: 1000px) {
  .checkin {
    grid-template-columns: 1fr;
  }
}
</style>
