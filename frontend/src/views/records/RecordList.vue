<template>
  <div class="ft-page">
    <!-- 页面标题 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">运动记录</h2>
        <p class="page-sub">记录每一次训练，用数据看见自己的进步</p>
      </div>
      <el-button type="primary" @click="goCreate">＋ 新建记录</el-button>
    </div>

    <!-- 累计数据卡片 -->
    <el-row :gutter="12" class="summary-row">
      <el-col v-for="card in summaryCards" :key="card.label" :xs="12" :sm="12" :md="6">
        <div class="summary-card">
          <div class="summary-value">
            {{ card.value }}<span class="summary-unit">{{ card.unit }}</span>
          </div>
          <div class="summary-label">{{ card.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 统计图表：月度 + 周 -->
    <el-row :gutter="12" class="chart-row">
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">月度训练统计</span>
              <el-date-picker
                v-model="monthValue"
                type="month"
                size="small"
                value-format="YYYY-MM"
                :clearable="false"
                style="width: 130px"
                @change="loadMonthly"
              />
            </div>
          </template>
          <div class="chart-wrap">
            <div ref="monthChartRef" v-loading="monthLoading" class="chart"></div>
            <div v-if="!monthLoading && monthEmpty" class="chart-empty">本月还没有训练数据</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">训练频率（按周）</span>
              <el-select v-model="weeks" size="small" style="width: 100px" @change="loadWeekly">
                <el-option :value="4" label="最近4周" />
                <el-option :value="8" label="最近8周" />
                <el-option :value="12" label="最近12周" />
              </el-select>
            </div>
          </template>
          <div class="chart-wrap">
            <div ref="weekChartRef" v-loading="weekLoading" class="chart"></div>
            <div v-if="!weekLoading && weekEmpty" class="chart-empty">暂无训练数据</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选 + 列表 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="panel-head">
          <span class="panel-title">记录列表</span>
          <div class="filter-bar">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              size="small"
              unlink-panels
              value-format="YYYY-MM-DD"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 240px"
              @change="handleFilter"
            />
            <el-select
              v-model="filterType"
              size="small"
              placeholder="训练类型"
              clearable
              style="width: 130px"
              @change="handleFilter"
            >
              <el-option v-for="item in WORKOUT_TYPES" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button size="small" @click="resetFilter">重置</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="listLoading"
        :data="records"
        stripe
        style="width: 100%"
        @row-click="goDetail"
      >
        <el-table-column prop="workout_date" label="日期" width="120" />
        <el-table-column label="标题" min-width="180">
          <template #default="{ row }">
            <span class="link-text">{{ row.title || '未命名训练' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="dark" :color="workoutTypeColor(row.workout_type)" style="border: none">
              {{ workoutTypeLabel(row.workout_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时长" width="100">
          <template #default="{ row }">{{ row.duration_min || 0 }} 分钟</template>
        </el-table-column>
        <el-table-column label="消耗" width="110">
          <template #default="{ row }">{{ row.calories || 0 }} 千卡</template>
        </el-table-column>
        <el-table-column label="主观强度" width="140">
          <template #default="{ row }">
            <el-rate :model-value="Number(row.feeling) || 0" disabled size="small" />
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.note || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="goDetail(row)">详情</el-button>
            <el-button link type="primary" size="small" @click.stop="goEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click.stop="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有训练记录，去记录第一次训练吧" :image-size="80" />
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
          @current-change="loadRecords"
          @size-change="loadRecords"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  WORKOUT_TYPES,
  deleteRecord,
  getMonthlyStatistics,
  getRecords,
  getSummaryStatistics,
  getWeeklyStatistics,
  workoutTypeColor,
  workoutTypeLabel
} from '@/api/record'

const router = useRouter()

/* ------------------------------------------------------------------ 通用取值helper
 * 后端不同统计接口的字段命名可能略有差异，这里做一次兼容，避免某个字段名不同就白屏
 */
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

/* ------------------------------------------------------------------ 累计数据卡片 */
const summary = ref({})

const summaryCards = computed(() => {
  const data = summary.value || {}
  return [
    {
      label: '累计训练',
      value: pickNumber(data, ['total_records', 'record_count', 'total_count', 'count']),
      unit: '次'
    },
    {
      label: '累计时长',
      value: pickNumber(data, ['total_duration', 'total_duration_min', 'duration_total']),
      unit: '分钟'
    },
    {
      label: '累计消耗',
      value: pickNumber(data, ['total_calories', 'calories_total']),
      unit: '千卡'
    },
    {
      label: '连续打卡',
      value: pickNumber(data, ['streak_days', 'current_streak', 'continuous_days']),
      unit: '天'
    }
  ]
})

async function loadSummary() {
  try {
    summary.value = (await getSummaryStatistics()) || {}
  } catch (error) {
    ElMessage.warning(`累计数据加载失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 记录列表 */
const records = ref([])
const listLoading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dateRange = ref([])
const filterType = ref('')

async function loadRecords() {
  listLoading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (Array.isArray(dateRange.value) && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    if (filterType.value) params.workout_type = filterType.value

    const data = await getRecords(params)
    records.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? records.value.length : Number(data?.total) || 0
  } catch (error) {
    records.value = []
    total.value = 0
    ElMessage.error(`记录加载失败：${error.message}`)
  } finally {
    listLoading.value = false
  }
}

function handleFilter() {
  page.value = 1
  loadRecords()
}

function resetFilter() {
  dateRange.value = []
  filterType.value = ''
  handleFilter()
}

/* ------------------------------------------------------------------ 月度图表 */
const monthValue = ref(new Date().toISOString().slice(0, 7))
const monthLoading = ref(false)
const monthEmpty = ref(false)
const monthChartRef = ref(null)
let monthChart = null

async function loadMonthly() {
  const [year, month] = String(monthValue.value || '').split('-')
  if (!year || !month) return
  monthLoading.value = true
  try {
    const data = await getMonthlyStatistics({ year: Number(year), month: Number(month) })
    const list = pickArray(data, ['days', 'items', 'list', 'daily', 'trend', 'stats'])
    monthEmpty.value = list.length === 0
    renderMonthly(list)
  } catch (error) {
    monthEmpty.value = true
    renderMonthly([])
    ElMessage.warning(`月度统计加载失败：${error.message}`)
  } finally {
    monthLoading.value = false
  }
}

function renderMonthly(list) {
  if (!monthChartRef.value) return
  if (!monthChart) monthChart = echarts.init(monthChartRef.value)

  const labels = list.map((item, index) => {
    const text = pickText(item, ['date', 'day', 'label', 'day_label'])
    if (!text) return String(index + 1)
    return text.length > 5 ? text.slice(5) : text
  })
  const durations = list.map((item) => pickNumber(item, ['duration_min', 'duration', 'total_duration']))
  const calories = list.map((item) => pickNumber(item, ['calories', 'total_calories', 'calorie']))

  monthChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['时长(分钟)', '消耗(千卡)'], textStyle: { color: '#8b93a7' }, top: 0 },
      grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        axisLabel: { color: '#8b93a7' }
      },
      yAxis: [
        {
          type: 'value',
          name: '分钟',
          nameTextStyle: { color: '#8b93a7' },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
          axisLabel: { color: '#8b93a7' }
        },
        {
          type: 'value',
          name: '千卡',
          nameTextStyle: { color: '#8b93a7' },
          splitLine: { show: false },
          axisLabel: { color: '#8b93a7' }
        }
      ],
      series: [
        {
          name: '时长(分钟)',
          type: 'bar',
          barMaxWidth: 22,
          itemStyle: { color: '#ff5a1f', borderRadius: [4, 4, 0, 0] },
          data: durations
        },
        {
          name: '消耗(千卡)',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          symbolSize: 6,
          itemStyle: { color: '#f9b73c' },
          data: calories
        }
      ]
    },
    true
  )
}

/* ------------------------------------------------------------------ 周图表 */
const weeks = ref(8)
const weekLoading = ref(false)
const weekEmpty = ref(false)
const weekChartRef = ref(null)
let weekChart = null

async function loadWeekly() {
  weekLoading.value = true
  try {
    const data = await getWeeklyStatistics({ weeks: weeks.value })
    const list = pickArray(data, ['weeks', 'items', 'list', 'weekly', 'trend'])
    weekEmpty.value = list.length === 0
    renderWeekly(list)
  } catch (error) {
    weekEmpty.value = true
    renderWeekly([])
    ElMessage.warning(`周统计加载失败：${error.message}`)
  } finally {
    weekLoading.value = false
  }
}

function renderWeekly(list) {
  if (!weekChartRef.value) return
  if (!weekChart) weekChart = echarts.init(weekChartRef.value)

  const labels = list.map((item, index) => {
    const text = pickText(item, ['week_start', 'start_date', 'label', 'week'])
    if (!text) return `第${index + 1}周`
    return text.length > 5 ? text.slice(5) : text
  })
  const counts = list.map((item) => pickNumber(item, ['count', 'record_count', 'total_records', 'times']))
  const durations = list.map((item) => pickNumber(item, ['duration_min', 'duration', 'total_duration']))

  weekChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['训练次数', '时长(分钟)'], textStyle: { color: '#8b93a7' }, top: 0 },
      grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        axisLabel: { color: '#8b93a7' }
      },
      yAxis: [
        {
          type: 'value',
          name: '次',
          nameTextStyle: { color: '#8b93a7' },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
          axisLabel: { color: '#8b93a7' }
        },
        {
          type: 'value',
          name: '分钟',
          nameTextStyle: { color: '#8b93a7' },
          splitLine: { show: false },
          axisLabel: { color: '#8b93a7' }
        }
      ],
      series: [
        {
          name: '训练次数',
          type: 'line',
          smooth: true,
          areaStyle: { opacity: 0.15 },
          itemStyle: { color: '#22c55e' },
          data: counts
        },
        {
          name: '时长(分钟)',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          itemStyle: { color: '#a78bfa' },
          data: durations
        }
      ]
    },
    true
  )
}

/* ------------------------------------------------------------------ 交互 */
function goCreate() {
  router.push('/records/create')
}

function goDetail(row) {
  if (!row || !row.id) return
  router.push(`/records/${row.id}`)
}

function goEdit(row) {
  if (!row || !row.id) return
  router.push(`/records/${row.id}/edit`)
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${row.workout_date || ''} 的「${row.title || '未命名训练'}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (error) {
    return
  }
  try {
    await deleteRecord(row.id)
    ElMessage.success('已删除')
    if (records.value.length === 1 && page.value > 1) page.value -= 1
    await loadRecords()
    loadSummary()
    loadMonthly()
    loadWeekly()
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 生命周期 */
function handleResize() {
  if (monthChart) monthChart.resize()
  if (weekChart) weekChart.resize()
}

onMounted(() => {
  loadSummary()
  loadRecords()
  loadMonthly()
  loadWeekly()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (monthChart) {
    monthChart.dispose()
    monthChart = null
  }
  if (weekChart) {
    weekChart.dispose()
    weekChart = null
  }
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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
.summary-row {
  margin-bottom: 12px;
}
.summary-card {
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--el-bg-color-overlay, #1b2230);
  border: 1px solid var(--el-border-color, #2c3444);
  margin-bottom: 12px;
}
.summary-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-color-primary, #409eff);
  line-height: 1.2;
}
.summary-unit {
  font-size: 12px;
  margin-left: 4px;
  color: var(--el-text-color-secondary, #8b949e);
}
.summary-label {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.chart-row {
  margin-bottom: 0;
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
.chart-wrap {
  position: relative;
}
.chart {
  width: 100%;
  height: 260px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.link-text {
  color: var(--el-color-primary, #409eff);
  cursor: pointer;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
