<template>
  <div class="admin-shell">
    <!-- 后台顶栏 -->
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
          <h2 class="page-title">数据看板</h2>
          <p class="page-sub">平台整体运行情况一览</p>
        </div>
        <el-button :loading="loading" @click="loadDashboard">刷新</el-button>
      </div>

      <!-- 统计卡片 -->
      <el-row :gutter="12" v-loading="loading">
        <el-col v-for="card in cards" :key="card.label" :xs="12" :sm="8" :md="8" :lg="4">
          <div class="stat-card">
            <div class="stat-icon">{{ card.icon }}</div>
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 趋势折线 -->
      <el-card shadow="never" class="panel">
        <template #header>
          <div class="panel-head">
            <span class="panel-title">近期趋势</span>
            <span class="panel-hint">数据来源：GET /api/admin/dashboard</span>
          </div>
        </template>
        <div class="chart-wrap">
          <div ref="trendChartRef" v-loading="loading" class="chart"></div>
          <div v-if="!loading && !hasTrend" class="chart-empty">后端暂未返回趋势数据</div>
        </div>
      </el-card>

      <!-- 待处理事项 / 快捷入口 -->
      <el-row :gutter="12">
        <el-col :xs="24" :md="12">
          <el-card shadow="never" class="panel">
            <template #header><span class="panel-title">待处理事项</span></template>
            <div class="todo-list">
              <div class="todo-item" @click="go('/admin/comments')">
                <span>💬 待审核课程评论</span>
                <b>{{ pendingComments }}</b>
              </div>
              <div class="todo-item" @click="go('/admin/realnames')">
                <span>🪪 待审核实名认证</span>
                <b>{{ pendingRealnames }}</b>
              </div>
              <div class="todo-item" @click="go('/admin/posts')">
                <span>📝 社区动态总数</span>
                <b>{{ totalPosts }}</b>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card shadow="never" class="panel">
            <template #header><span class="panel-title">快捷入口</span></template>
            <div class="quick-links">
              <el-button @click="go('/admin/users')">用户管理</el-button>
              <el-button @click="go('/admin/courses')">课程管理</el-button>
              <el-button @click="go('/admin/comments')">评论审核</el-button>
              <el-button @click="go('/admin/posts')">动态管理</el-button>
              <el-button @click="go('/admin/realnames')">实名审核</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { clearAdminAuth, getAdminDashboard, getAdminInfo } from '@/api/admin'

const router = useRouter()
const adminInfo = getAdminInfo() || {}
const adminName = adminInfo.nickname || adminInfo.real_name || adminInfo.username || '管理员'

const dashboard = ref({})
const loading = ref(false)
const trendChartRef = ref(null)
let trendChart = null

/* ------------------------------------------------------------------ 取值 helper */
function pickArray(data, keys) {
  if (Array.isArray(data)) return data
  if (!data || typeof data !== 'object') return []
  for (const key of keys) {
    if (Array.isArray(data[key])) return data[key]
  }
  return []
}

function pickNumber(source, keys, fallback = 0) {
  if (!source || typeof source !== 'object') return fallback
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string' && value !== '' && !Number.isNaN(Number(value))) return Number(value)
  }
  return fallback
}

function pickText(source, keys, fallback = '') {
  if (!source || typeof source !== 'object') return fallback
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'string' && value) return value
  }
  return fallback
}

/* ------------------------------------------------------------------ 卡片 */
const cards = computed(() => {
  const data = dashboard.value || {}
  return [
    { label: '用户总数', value: pickNumber(data, ['total_users', 'user_count', 'users']), icon: '👥' },
    { label: '今日新增用户', value: pickNumber(data, ['today_new_users', 'new_users_today', 'today_users']), icon: '🆕' },
    { label: '训练记录数', value: pickNumber(data, ['total_records', 'record_count', 'workout_count']), icon: '🏃' },
    { label: '课程总数', value: pickNumber(data, ['total_courses', 'course_count']), icon: '🎬' },
    { label: '社区动态数', value: pickNumber(data, ['total_posts', 'post_count']), icon: '📝' },
    { label: '评论总数', value: pickNumber(data, ['total_comments', 'comment_count']), icon: '💬' }
  ]
})

const pendingComments = computed(() =>
  pickNumber(dashboard.value || {}, ['pending_comments', 'comments_pending', 'audit_comments'])
)
const pendingRealnames = computed(() =>
  pickNumber(dashboard.value || {}, ['pending_realnames', 'realnames_pending', 'audit_realnames'])
)
const totalPosts = computed(() => pickNumber(dashboard.value || {}, ['total_posts', 'post_count']))

/* ------------------------------------------------------------------ 趋势图 */
const trendSeriesMeta = [
  { keys: ['user_trend', 'users_trend', 'new_users_trend'], name: '新增用户', color: '#ff5a1f' },
  { keys: ['record_trend', 'records_trend', 'workout_trend'], name: '训练记录', color: '#38bdf8' },
  { keys: ['post_trend', 'posts_trend', 'community_trend'], name: '社区动态', color: '#22c55e' }
]

const hasTrend = ref(false)

function buildTrendSeries() {
  const data = dashboard.value || {}
  const series = []
  trendSeriesMeta.forEach((meta) => {
    const list = pickArray(data, meta.keys)
    if (list.length === 0) return
    series.push({
      meta,
      list,
      labels: list.map((item, index) => pickText(item, ['date', 'day', 'label']) || String(index + 1)),
      values: list.map((item) => pickNumber(item, ['count', 'value', 'total', 'num']))
    })
  })

  // 兜底：任意一个可用的趋势数组
  if (series.length === 0) {
    const fallback = pickArray(data, ['trend', 'daily', 'chart', 'items', 'list'])
    if (fallback.length > 0) {
      series.push({
        meta: { name: '趋势', color: '#ff5a1f' },
        list: fallback,
        labels: fallback.map((item, index) => pickText(item, ['date', 'day', 'label']) || String(index + 1)),
        values: fallback.map((item) => pickNumber(item, ['count', 'value', 'total', 'num']))
      })
    }
  }
  return series
}

function renderTrend() {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)

  const series = buildTrendSeries()
  hasTrend.value = series.length > 0
  const labels = series.length > 0 ? series[0].labels : []

  trendChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: series.map((item) => item.meta.name), textStyle: { color: '#8b93a7' }, top: 0 },
      grid: { left: 8, right: 12, top: 42, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        axisLabel: { color: '#8b93a7' }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#8b93a7' }
      },
      series: series.map((item) => ({
        name: item.meta.name,
        type: 'line',
        smooth: true,
        symbolSize: 5,
        itemStyle: { color: item.meta.color },
        data: item.values
      }))
    },
    true
  )
}

/* ------------------------------------------------------------------ 加载 */
async function loadDashboard() {
  loading.value = true
  try {
    const data = await getAdminDashboard()
    dashboard.value = data || {}
    renderTrend()
  } catch (error) {
    dashboard.value = {}
    renderTrend()
    ElMessage.error(`看板数据加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function go(path) {
  router.push(path)
}

function handleLogout() {
  clearAdminAuth()
  router.replace('/admin/login')
}

function handleResize() {
  if (trendChart) trendChart.resize()
}

onMounted(() => {
  loadDashboard()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
})
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
.stat-card {
  padding: 14px 16px;
  border-radius: var(--ft-radius-sm, 9px);
  background: var(--ft-card, #171b24);
  border: 1px solid var(--ft-border, rgba(255, 255, 255, 0.08));
  margin-bottom: 12px;
}
.stat-icon {
  font-size: 16px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--ft-primary, #ff5a1f);
  line-height: 1.3;
}
.stat-label {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
  margin-top: 2px;
}
.panel {
  margin-bottom: 12px;
  background: var(--ft-card, #171b24);
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
}
.panel-hint {
  font-size: 12px;
  color: var(--ft-text-dim, #7b8497);
}
.chart-wrap {
  position: relative;
}
.chart {
  width: 100%;
  height: 300px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--ft-text-dim, #7b8497);
}
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: var(--ft-radius-sm, 9px);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border, rgba(255, 255, 255, 0.08));
  font-size: 13px;
  cursor: pointer;
}
.todo-item:hover {
  border-color: rgba(255, 90, 31, 0.45);
}
.todo-item b {
  color: var(--ft-primary, #ff5a1f);
  font-size: 16px;
}
.quick-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
