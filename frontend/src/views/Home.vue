<script setup>
/**
 * Home.vue 首页看板
 * 内容：今日计划、每日签到按钮、统计卡片（连续/本月/本周签到、今日计划）、
 *       等级积分进度、最近 7 天签到图表（ECharts）、快捷入口
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
// ECharts 按需引入，控制打包体积
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'
import { checkin, getCheckinCalendar, getCheckinStats, getLevel } from '@/api/user'
import { checkinPlan, getMyPlans, getTodayCheckin } from '@/api/plan'
import { getFavoriteCourses } from '@/api/course'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const router = useRouter()
const userStore = useUserStore()

// ---------------- 页面状态 ----------------
/** 整体刷新中 */
const refreshing = ref(false)
/** 各数据块加载状态 */
const profileLoading = ref(true)
const todayLoading = ref(true)
const weekLoading = ref(true)
const levelLoading = ref(true)
/** 各数据块错误信息（有值时展示错误占位与重试） */
const todayError = ref('')
const weekError = ref('')
/** 今日签到按钮 loading */
const checkinLoading = ref(false)
/** 单个计划的打卡 loading（按计划 id 记录） */
const planCheckinLoading = ref({})

/** 签到统计 */
const checkinStats = ref({
  current_streak: 0,
  total_days: 0,
  month_days: 0,
  today_checked: false,
  last_checkin_date: ''
})
/** 等级信息 */
const levelInfo = ref(null)
/** 今日计划列表（规范化后） */
const todayPlans = ref([])
/** 我的计划总数（用于快捷入口展示） */
const planTotal = ref(0)
/** 收藏课程数 */
const favoriteCount = ref(0)
/** 最近 7 天签到数据：[{ label, checked }] */
const weekDays = ref([])

/** 图表容器与实例 */
const chartRef = ref(null)
let chartInstance = null

/** 今日是否已签到 */
const todayChecked = computed(() => Boolean(checkinStats.value.today_checked || userStore.profile?.today_checked))

/** 本周已签到天数 */
const weekCheckedCount = computed(() => weekDays.value.filter((d) => d.checked).length)

/** 今日计划的完成情况 */
const todayPlanDone = computed(() => todayPlans.value.filter((p) => p.checked).length)

/** 等级进度百分比 */
const levelProgress = computed(() => {
  const info = levelInfo.value
  if (info) {
    if (info.is_max_level) return 100
    if (typeof info.progress === 'number') return Math.min(100, Math.round(info.progress))
    const min = Number(info.level_min_points ?? 0)
    const next = Number(info.next_level_points ?? 0)
    if (next > min) return Math.min(100, Math.round(((info.points - min) / (next - min)) * 100))
    return 0
  }
  // 退化到 profile 数据
  const profile = userStore.profile
  if (!profile) return 0
  const next = Number(profile.next_level_points ?? 0)
  if (!next) return 100
  return Math.min(100, Math.round((Number(profile.points ?? 0) / next) * 100))
})

/** 等级文案 */
const levelTitle = computed(() => levelInfo.value?.title || `Lv.${userStore.level}`)

/** 距离下一等级还差多少积分 */
const pointsToNext = computed(() => {
  if (levelInfo.value) return Number(levelInfo.value.points_to_next_level ?? 0)
  return Number(userStore.profile?.points_to_next_level ?? 0)
})

/** 问候语（按当前时间） */
const greeting = computed(() => {
  const hour = new Date().getHours()
  const name = userStore.displayName
  if (hour < 6) return `凌晨好，${name}，注意休息`
  if (hour < 11) return `早上好，${name}，今天也要坚持训练`
  if (hour < 14) return `中午好，${name}，补充能量后再上强度`
  if (hour < 18) return `下午好，${name}，来一组训练提提神`
  return `晚上好，${name}，别忘了今天的签到`
})

/** 快捷入口配置 */
const shortcuts = [
  { path: '/plans', title: '我的计划', desc: '管理训练安排', icon: '📋' },
  { path: '/templates', title: '模板库', desc: '一键套用计划', icon: '🧩' },
  { path: '/courses', title: '课程中心', desc: '跟练视频课程', icon: '🎬' },
  { path: '/checkin', title: '签到日历', desc: '记录坚持天数', icon: '🔥' },
  { path: '/profile', title: '个人中心', desc: '资料与实名', icon: '👤' }
]

// ---------------- 数据加载 ----------------
/** 加载签到统计 + 个人资料（用于签到卡片与等级卡） */
async function loadProfileAndStats() {
  profileLoading.value = true
  try {
    await userStore.fetchProfile()
    const stats = await getCheckinStats()
    checkinStats.value = {
      current_streak: Number(stats?.current_streak ?? 0),
      total_days: Number(stats?.total_days ?? 0),
      month_days: Number(stats?.month_days ?? 0),
      today_checked: Boolean(stats?.today_checked),
      last_checkin_date: stats?.last_checkin_date || ''
    }
  } catch (error) {
    // 签到统计失败不阻塞页面，使用 store 中的资料兜底
    const profile = userStore.profile
    if (profile) {
      checkinStats.value = {
        current_streak: Number(profile.checkin_streak ?? 0),
        total_days: Number(profile.checkin_total ?? 0),
        month_days: Number(profile.checkin_month ?? 0),
        today_checked: Boolean(profile.today_checked),
        last_checkin_date: ''
      }
    }
  } finally {
    profileLoading.value = false
  }
}

/** 把今日计划接口返回的多种可能结构统一成前端结构（后端返回 TodayPlanOut 数组） */
function normalizeTodayPlans(data) {
  const raw = Array.isArray(data)
    ? data
    : data?.plans || data?.items || data?.today_plans || data?.list || []
  if (!Array.isArray(raw)) return []
  return raw.map((item) => ({
    id: Number(item.plan_id ?? item.id ?? 0),
    name: item.plan_name || item.name || item.title || '训练计划',
    goal: item.goal || '',
    cycleType: item.cycle_type || '',
    cycleDays: Number(item.cycle_days ?? 0),
    dayIndex: Number(item.day_index ?? 1),
    // 后端字段为 checked_in；其余为兼容写法
    checked: Boolean(item.checked_in ?? item.checked ?? item.is_checked ?? item.completed),
    isRestDay: Boolean(item.is_rest_day),
    itemCount: Number(item.items_count ?? item.item_count ?? (Array.isArray(item.items) ? item.items.length : 0)),
    note: item.note || ''
  }))
}

/** 加载今日计划 */
async function loadTodayPlans() {
  todayLoading.value = true
  todayError.value = ''
  try {
    const data = await getTodayCheckin()
    todayPlans.value = normalizeTodayPlans(data)
  } catch (error) {
    todayPlans.value = []
    todayError.value = '今日计划加载失败，请稍后重试'
  } finally {
    todayLoading.value = false
  }
}

/** 组装最近 7 天的日期数组（跨月时补充上个月日历数据） */
async function loadWeekCheckins() {
  weekLoading.value = true
  weekError.value = ''
  try {
    const today = new Date()
    const requests = [
      getCheckinCalendar({ year: today.getFullYear(), month: today.getMonth() + 1 })
    ]
    // 月初 7 天内，最近 7 天会跨越上个月，需要再取一次上月日历
    if (today.getDate() <= 7) {
      const prev = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      requests.push(getCheckinCalendar({ year: prev.getFullYear(), month: prev.getMonth() + 1 }))
    }
    const calendars = await Promise.all(requests)

    // 把两个月的日期拼成 { 'YYYY-MM-DD': checked } 映射
    const checkedMap = {}
    calendars.forEach((cal) => {
      ;(cal?.days || []).forEach((day) => {
        if (day?.date) checkedMap[String(day.date).slice(0, 10)] = Boolean(day.checked)
      })
    })

    const labels = ['日', '一', '二', '三', '四', '五', '六']
    const result = []
    for (let i = 6; i >= 0; i -= 1) {
      const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i)
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
        date.getDate()
      ).padStart(2, '0')}`
      result.push({
        date: key,
        label: `周${labels[date.getDay()]}`,
        dayOfMonth: date.getDate(),
        checked: Boolean(checkedMap[key])
      })
    }
    weekDays.value = result
    await nextTick()
    renderChart()
  } catch (error) {
    weekDays.value = []
    weekError.value = '最近签到数据加载失败'
  } finally {
    weekLoading.value = false
  }
}

/** 加载等级信息 */
async function loadLevel() {
  levelLoading.value = true
  try {
    levelInfo.value = await getLevel()
  } catch (error) {
    levelInfo.value = null
  } finally {
    levelLoading.value = false
  }
}

/** 加载计划总数与收藏课程数（快捷入口角标） */
async function loadCounters() {
  try {
    const data = await getMyPlans({ page: 1, page_size: 1 })
    planTotal.value = Number(data?.total ?? (Array.isArray(data) ? data.length : 0))
  } catch (error) {
    planTotal.value = 0
  }
  try {
    const favorites = await getFavoriteCourses()
    favoriteCount.value = Array.isArray(favorites)
      ? favorites.length
      : Number(favorites?.total ?? favorites?.items?.length ?? 0)
  } catch (error) {
    favoriteCount.value = 0
  }
}

// ---------------- 图表 ----------------
/** 渲染最近 7 天签到柱状图 */
function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  }
  const data = weekDays.value
  chartInstance.setOption({
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 18, bottom: 6, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c2130',
      borderColor: 'rgba(255,255,255,0.12)',
      textStyle: { color: '#e9edf5', fontSize: 12 },
      formatter: (params) => {
        const p = params?.[0]
        if (!p) return ''
        const item = data[p.dataIndex]
        return `${item.date}<br/>${item.checked ? '已签到 ✅' : '未签到'}`
      }
    },
    xAxis: {
      type: 'category',
      data: data.map((d) => d.label),
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
      axisTick: { show: false },
      axisLabel: { color: '#8b93a7', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      max: 1,
      splitNumber: 1,
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
    },
    series: [
      {
        name: '签到',
        type: 'bar',
        barWidth: 18,
        data: data.map((d) => (d.checked ? 1 : 0.001)),
        itemStyle: {
          borderRadius: [6, 6, 3, 3],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#ff8148' },
            { offset: 1, color: '#ff5a1f' }
          ])
        },
        label: {
          show: true,
          position: 'top',
          color: '#8b93a7',
          fontSize: 11,
          formatter: (params) => (data[params.dataIndex].checked ? '✓' : '')
        }
      }
    ]
  })
}

/** 窗口尺寸变化时重绘图表 */
function handleResize() {
  chartInstance?.resize()
}

// ---------------- 交互 ----------------
/** 每日签到 */
async function handleCheckin() {
  if (todayChecked.value) {
    ElMessage.info('今天已经签到过了，明天再来')
    return
  }
  checkinLoading.value = true
  try {
    const data = await checkin()
    const points = Number(data?.points_awarded ?? 0)
    const streak = Number(data?.streak ?? 0)
    ElMessage.success(
      points > 0
        ? `签到成功，连续 ${streak} 天，获得 ${points} 积分`
        : `签到成功，已连续签到 ${streak} 天`
    )
    // 刷新统计与图表
    await Promise.all([loadProfileAndStats(), loadWeekCheckins(), loadLevel()])
  } catch (error) {
    /* 错误已提示 */
  } finally {
    checkinLoading.value = false
  }
}

/** 对某个计划打卡 */
async function handlePlanCheckin(plan) {
  if (!plan.id) return
  planCheckinLoading.value = { ...planCheckinLoading.value, [plan.id]: true }
  try {
    await checkinPlan(plan.id, { day_index: plan.dayIndex })
    ElMessage.success(`「${plan.name}」打卡成功`)
    await Promise.all([loadTodayPlans(), loadProfileAndStats()])
  } catch (error) {
    /* 错误已提示 */
  } finally {
    planCheckinLoading.value = { ...planCheckinLoading.value, [plan.id]: false }
  }
}

/** 一键刷新所有看板数据 */
async function refreshAll() {
  refreshing.value = true
  await Promise.all([loadProfileAndStats(), loadTodayPlans(), loadWeekCheckins(), loadLevel(), loadCounters()])
  refreshing.value = false
}

// ---------------- 生命周期 ----------------
onMounted(async () => {
  if (!userStore.user) {
    try {
      await userStore.fetchMe()
    } catch (error) {
      /* 401 由拦截器处理 */
    }
  }
  await refreshAll()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<template>
  <div class="ft-page">
    <PageHeader title="首页看板" :subtitle="greeting">
      <template #actions>
        <el-button :loading="refreshing" @click="refreshAll">刷新数据</el-button>
        <el-button type="primary" :loading="checkinLoading" :disabled="todayChecked" @click="handleCheckin">
          {{ todayChecked ? '今日已签到' : '立即签到' }}
        </el-button>
      </template>
    </PageHeader>

    <!-- ============ 统计卡片 ============ -->
    <div class="ft-grid--4" style="margin-bottom: 18px">
      <StatCard
        label="连续签到"
        :value="checkinStats.current_streak"
        unit="天"
        icon="🔥"
        tone="primary"
        :loading="profileLoading"
        :hint="`累计签到 ${checkinStats.total_days} 天`"
        clickable
        @click="router.push('/checkin')"
      />
      <StatCard
        label="本月签到"
        :value="checkinStats.month_days"
        unit="天"
        icon="📅"
        tone="success"
        :loading="profileLoading"
        hint="按自然月统计"
        clickable
        @click="router.push('/checkin')"
      />
      <StatCard
        label="本周签到"
        :value="weekCheckedCount"
        unit="/ 7 天"
        icon="📈"
        tone="warning"
        :loading="weekLoading"
        :hint="weekError ? '数据加载失败' : '最近 7 天统计'"
      />
      <StatCard
        label="今日计划"
        :value="todayPlans.length"
        unit="个"
        icon="🏋️"
        tone="info"
        :loading="todayLoading"
        :hint="`已完成 ${todayPlanDone} 个`"
        clickable
        @click="router.push('/plans')"
      />
    </div>

    <!-- ============ 主区域 ============ -->
    <div class="home">
      <!-- 今日计划 -->
      <section class="home__main ft-card">
        <div class="home__section-head">
          <h3 class="ft-section-title" style="margin: 0">今日训练计划</h3>
          <el-button link type="primary" @click="router.push('/plans')">全部计划 →</el-button>
        </div>

        <div v-if="todayLoading" class="ft-loading-text">
          <el-icon class="is-loading">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3a9 9 0 109 9" stroke-linecap="round" />
            </svg>
          </el-icon>
          正在加载今日计划…
        </div>

        <EmptyState
          v-else-if="todayError"
          size="sm"
          icon="⚠️"
          :description="todayError"
          error
        >
          <el-button size="small" @click="loadTodayPlans">重新加载</el-button>
        </EmptyState>

        <EmptyState
          v-else-if="!todayPlans.length"
          size="sm"
          icon="🗓️"
          description="今天还没有安排训练，去创建一个计划或套用模板吧"
        >
          <el-button size="small" type="primary" @click="router.push('/plans/new')">新建计划</el-button>
          <el-button size="small" @click="router.push('/templates')">浏览模板</el-button>
        </EmptyState>

        <ul v-else class="today-list">
          <li v-for="plan in todayPlans" :key="plan.id" class="today-list__item">
            <div class="today-list__left">
              <div class="today-list__icon">{{ plan.checked ? '✅' : '🏃' }}</div>
              <div class="today-list__info">
                <p class="today-list__name">
                  {{ plan.name }}
                  <span class="ft-chip">第 {{ plan.dayIndex }} 天</span>
                </p>
                <p class="today-list__meta">
                  <span v-if="plan.itemCount">{{ plan.itemCount }} 个动作</span>
                  <span v-if="plan.goal">· 目标 {{ plan.goal }}</span>
                  <span v-if="plan.note">· {{ plan.note }}</span>
                </p>
              </div>
            </div>
            <div class="today-list__actions">
              <el-button link type="primary" @click="router.push(`/plans/${plan.id}`)">查看</el-button>
              <el-button
                v-if="!plan.checked"
                size="small"
                type="primary"
                :loading="planCheckinLoading[plan.id]"
                @click="handlePlanCheckin(plan)"
              >
                打卡
              </el-button>
              <span v-else class="ft-chip ft-chip--success">已完成</span>
            </div>
          </li>
        </ul>
      </section>

      <!-- 右侧栏 -->
      <aside class="home__side">
        <!-- 等级与积分 -->
        <section class="ft-card level-card">
          <div class="level-card__head">
            <div>
              <p class="level-card__label">当前等级</p>
              <p class="level-card__title">{{ levelTitle }}</p>
            </div>
            <div class="level-card__points">
              <strong>{{ userStore.points }}</strong>
              <span>积分</span>
            </div>
          </div>

          <el-progress
            :percentage="levelProgress"
            :stroke-width="9"
            :show-text="false"
            color="#ff5a1f"
            style="margin: 14px 0 8px"
          />
          <p class="level-card__tip">
            <template v-if="levelLoading">正在读取等级规则…</template>
            <template v-else-if="pointsToNext > 0">再获得 {{ pointsToNext }} 积分即可升级</template>
            <template v-else>已达到当前最高等级，继续保持！</template>
          </p>
          <el-button link type="primary" size="small" @click="router.push('/profile')">
            查看等级规则 →
          </el-button>
        </section>

        <!-- 最近 7 天签到 -->
        <section class="ft-card">
          <h3 class="ft-section-title">最近 7 天签到</h3>
          <div v-if="weekLoading" class="ft-loading-text" style="padding: 30px 0">加载中…</div>
          <EmptyState v-else-if="weekError" size="sm" icon="⚠️" :description="weekError" error>
            <el-button size="small" @click="loadWeekCheckins">重试</el-button>
          </EmptyState>
          <div v-else ref="chartRef" class="week-chart"></div>
        </section>

        <!-- 快捷入口 -->
        <section class="ft-card">
          <h3 class="ft-section-title">快捷入口</h3>
          <div class="shortcuts">
            <button
              v-for="item in shortcuts"
              :key="item.path"
              class="shortcut"
              type="button"
              @click="router.push(item.path)"
            >
              <span class="shortcut__icon">{{ item.icon }}</span>
              <span class="shortcut__title">{{ item.title }}</span>
              <span class="shortcut__desc">{{ item.desc }}</span>
              <span v-if="item.path === '/plans'" class="shortcut__badge">{{ planTotal }}</span>
              <span v-else-if="item.path === '/courses'" class="shortcut__badge">{{ favoriteCount }}</span>
            </button>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.home {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 1fr);
  gap: 16px;
  align-items: start;
}

.home__main {
  min-height: 300px;
}

.home__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.home__side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 今日计划列表 */
.today-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.today-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--ft-radius);
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
  transition: border-color 0.18s ease, background 0.18s ease;
}

.today-list__item:hover {
  border-color: rgba(255, 90, 31, 0.4);
  background: rgba(255, 90, 31, 0.06);
}

.today-list__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.today-list__icon {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--ft-primary-soft);
  font-size: 17px;
}

.today-list__info {
  min-width: 0;
}

.today-list__name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ft-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.today-list__meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--ft-text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.today-list__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

/* 等级卡片 */
.level-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.level-card__label {
  font-size: 12px;
  color: var(--ft-text-dim);
}

.level-card__title {
  font-size: 19px;
  font-weight: 700;
  background: linear-gradient(120deg, #ffffff, #ffb08a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.level-card__points {
  text-align: right;
  line-height: 1.2;
}

.level-card__points strong {
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}

.level-card__points span {
  display: block;
  font-size: 11px;
  color: var(--ft-text-dim);
}

.level-card__tip {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-bottom: 6px;
}

/* 图表 */
.week-chart {
  width: 100%;
  height: 170px;
}

/* 快捷入口 */
.shortcuts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.shortcut {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px;
  border-radius: var(--ft-radius);
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
  color: var(--ft-text);
  cursor: pointer;
  text-align: left;
  transition: all 0.18s ease;
}

.shortcut:hover {
  border-color: rgba(255, 90, 31, 0.45);
  background: var(--ft-primary-soft);
  transform: translateY(-2px);
}

.shortcut__icon {
  font-size: 17px;
}

.shortcut__title {
  font-size: 13px;
  font-weight: 600;
}

.shortcut__desc {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.shortcut__badge {
  position: absolute;
  top: 10px;
  right: 10px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(255, 90, 31, 0.18);
  color: var(--ft-primary-light);
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

@media (max-width: 1100px) {
  .home {
    grid-template-columns: 1fr;
  }
}
</style>
