<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">数据统计</h2>
        <p class="page-sub">体重、体脂、卡路里收支与训练频率，一屏看清身体变化</p>
      </div>
      <el-button :loading="refreshing" @click="refreshAll">刷新数据</el-button>
    </div>

    <!-- 总览卡片 -->
    <el-row :gutter="12" class="summary-row">
      <el-col v-for="card in overviewCards" :key="card.label" :xs="12" :sm="12" :md="6">
        <div class="summary-card">
          <div class="summary-value">
            {{ card.value }}<span class="summary-unit">{{ card.unit }}</span>
          </div>
          <div class="summary-label">{{ card.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 体重 / 体脂趋势 + BMI 计算器 -->
    <el-row :gutter="12">
      <el-col :xs="24" :md="15">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">体重 / 体脂趋势</span>
              <el-radio-group v-model="trendDays" size="small" @change="loadTrend">
                <el-radio-button :value="30">30天</el-radio-button>
                <el-radio-button :value="90">90天</el-radio-button>
                <el-radio-button :value="180">180天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div class="chart-wrap">
            <div ref="weightChartRef" v-loading="trendLoading" class="chart chart-lg"></div>
            <div v-if="!trendLoading && trendEmpty" class="chart-empty">还没有体重记录，先在下方录入一次体测数据</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="9">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">BMI 计算器</span></template>
          <div class="bmi-form">
            <div class="bmi-field">
              <span class="bmi-label">体重 (kg)</span>
              <el-input-number v-model="bmiForm.weight" :min="20" :max="300" :precision="1" :step="0.5" style="width: 100%" />
            </div>
            <div class="bmi-field">
              <span class="bmi-label">身高 (cm)</span>
              <el-input-number v-model="bmiForm.height" :min="100" :max="250" :precision="0" :step="1" style="width: 100%" />
            </div>
            <el-button type="primary" :loading="bmiLoading" style="width: 100%" @click="handleCalcBmi">计算 BMI</el-button>
          </div>

          <div v-if="bmiResult !== null" class="bmi-result">
            <div class="bmi-value" :style="{ color: bmiInfo.color }">{{ bmiResult }}</div>
            <div class="bmi-level" :style="{ color: bmiInfo.color }">{{ bmiInfo.text }}</div>
            <div class="bmi-scale">
              <div class="bmi-scale-bar">
                <span
                  v-for="seg in bmiSegments"
                  :key="seg.text"
                  :style="{ background: seg.color }"
                  :title="seg.text"
                ></span>
              </div>
              <div class="bmi-scale-labels">
                <span>18.5</span><span>24</span><span>28</span>
              </div>
            </div>
            <p class="bmi-tip">BMI = 体重(kg) ÷ 身高(m)²，仅作参考，肌肉量高的人群可能偏高。</p>
          </div>
          <el-empty v-else description="输入身高体重后点击计算" :image-size="54" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 卡路里收支 + 训练频率 -->
    <el-row :gutter="12">
      <el-col :xs="24" :md="15">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">卡路里收支（{{ monthValue }}）</span>
              <div class="panel-tools">
                <el-date-picker
                  v-model="monthValue"
                  type="month"
                  size="small"
                  value-format="YYYY-MM"
                  :clearable="false"
                  style="width: 120px"
                  @change="loadCaloriesMonth"
                />
                <el-date-picker
                  v-model="balanceDate"
                  type="date"
                  size="small"
                  value-format="YYYY-MM-DD"
                  :clearable="false"
                  style="width: 130px"
                  @change="loadBalanceDay"
                />
              </div>
            </div>
          </template>

          <div class="balance-row">
            <div class="balance-item">
              <div class="balance-value" style="color: #22c55e">{{ balanceDay.in }}</div>
              <div class="balance-label">当日摄入(千卡)</div>
            </div>
            <div class="balance-item">
              <div class="balance-value" style="color: #f9b73c">{{ balanceDay.out }}</div>
              <div class="balance-label">当日消耗(千卡)</div>
            </div>
            <div class="balance-item">
              <div class="balance-value" :style="{ color: balanceDay.net > 0 ? '#f04b4b' : '#38bdf8' }">
                {{ balanceDay.net > 0 ? '+' : '' }}{{ balanceDay.net }}
              </div>
              <div class="balance-label">净收支(千卡)</div>
            </div>
          </div>

          <div class="chart-wrap">
            <div ref="calorieChartRef" v-loading="calorieLoading" class="chart"></div>
            <div v-if="!calorieLoading && calorieEmpty" class="chart-empty">本月暂无饮食/训练数据</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="9">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">训练频率</span>
              <el-select v-model="freqWeeks" size="small" style="width: 100px" @change="loadFrequency">
                <el-option :value="4" label="最近4周" />
                <el-option :value="8" label="最近8周" />
                <el-option :value="12" label="最近12周" />
              </el-select>
            </div>
          </template>
          <div class="chart-wrap">
            <div ref="freqChartRef" v-loading="freqLoading" class="chart"></div>
            <div v-if="!freqLoading && freqEmpty" class="chart-empty">暂无训练记录</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 体测录入 + 历史记录 -->
    <el-row :gutter="12">
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">录入身体数据</span>
              <span class="panel-hint">每人每天一条，重复提交会覆盖当天数据</span>
            </div>
          </template>
          <el-form ref="metricFormRef" :model="metricForm" label-width="78px">
            <el-form-item label="记录日期">
              <el-date-picker v-model="metricForm.metric_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
            <el-form-item label="体重(kg)">
              <el-input-number v-model="metricForm.weight" :min="0" :max="300" :precision="1" :step="0.5" style="width: 100%" />
            </el-form-item>
            <el-form-item label="体脂率(%)">
              <el-input-number v-model="metricForm.body_fat" :min="0" :max="70" :precision="1" :step="0.5" style="width: 100%" />
            </el-form-item>
            <el-form-item label="肌肉量(kg)">
              <el-input-number v-model="metricForm.muscle_mass" :min="0" :max="120" :precision="1" :step="0.5" style="width: 100%" />
            </el-form-item>
            <el-form-item label="腰围(cm)">
              <el-input-number v-model="metricForm.waist" :min="0" :max="200" :precision="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="胸围(cm)">
              <el-input-number v-model="metricForm.chest" :min="0" :max="200" :precision="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="臀围(cm)">
              <el-input-number v-model="metricForm.hip" :min="0" :max="200" :precision="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="metricForm.note" maxlength="200" placeholder="例如：空腹晨称" />
            </el-form-item>
            <div class="ft-form-actions">
              <el-button type="primary" :loading="savingMetric" @click="handleSaveMetric">保存数据</el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">身体数据记录</span>
              <span class="panel-hint">共 {{ metricTotal }} 条</span>
            </div>
          </template>
          <el-table v-loading="metricLoading" :data="metrics" size="small" style="width: 100%">
            <el-table-column prop="metric_date" label="日期" width="110" />
            <el-table-column label="体重" width="90">
              <template #default="{ row }">{{ row.weight || '—' }}</template>
            </el-table-column>
            <el-table-column label="体脂率" width="90">
              <template #default="{ row }">{{ row.body_fat || '—' }}</template>
            </el-table-column>
            <el-table-column label="肌肉量" width="90">
              <template #default="{ row }">{{ row.muscle_mass || '—' }}</template>
            </el-table-column>
            <el-table-column label="腰围" width="80">
              <template #default="{ row }">{{ row.waist || '—' }}</template>
            </el-table-column>
            <el-table-column label="备注" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.note || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="handleDeleteMetric(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="还没有身体数据，先在左侧录入一条" :image-size="60" />
            </template>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="metricPage"
              v-model:page-size="metricPageSize"
              :total="metricTotal"
              layout="prev, pager, next"
              background
              small
              @current-change="loadMetrics"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  bmiLevel,
  calcBmi,
  createBodyMetric,
  deleteBodyMetric,
  getBodyFatTrend,
  getBodyMetrics,
  getCaloriesBalance,
  getCaloriesBalanceMonth,
  getFrequency,
  getStatsDashboard,
  getWeightTrend
} from '@/api/stats'

/* ------------------------------------------------------------------ 通用取值 helper */
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

/** 时间轴标签压缩：2024-05-01 → 05-01 */
function shortLabel(text, fallback) {
  if (!text) return fallback
  const value = String(text)
  return value.length > 5 ? value.slice(5) : value
}

const todayStr = () => new Date().toISOString().slice(0, 10)
const thisMonth = () => new Date().toISOString().slice(0, 7)

/* ------------------------------------------------------------------ 总览卡片 */
const dashboard = ref({})
const refreshing = ref(false)

const overviewCards = computed(() => {
  const data = dashboard.value || {}
  return [
    {
      label: '累计训练',
      value: pickNumber(data, ['total_records', 'total_workouts', 'record_count']),
      unit: '次'
    },
    {
      label: '累计消耗',
      value: pickNumber(data, ['total_calories', 'calories_burned', 'burn_calories']),
      unit: '千卡'
    },
    {
      label: '最新体重',
      value: pickNumber(data, ['current_weight', 'latest_weight', 'weight']),
      unit: 'kg'
    },
    {
      label: '连续打卡',
      value: pickNumber(data, ['streak_days', 'current_streak', 'continuous_days']),
      unit: '天'
    }
  ]
})

async function loadDashboard() {
  try {
    dashboard.value = (await getStatsDashboard()) || {}
  } catch (error) {
    dashboard.value = {}
    ElMessage.warning(`总览数据加载失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 体重/体脂趋势 */
const trendDays = ref(30)
const trendLoading = ref(false)
const trendEmpty = ref(false)
const weightChartRef = ref(null)
let weightChart = null

async function loadTrend() {
  trendLoading.value = true
  try {
    const [weightData, fatData] = await Promise.all([
      getWeightTrend({ days: trendDays.value }).catch(() => null),
      getBodyFatTrend({ days: trendDays.value }).catch(() => null)
    ])
    const weightList = pickArray(weightData, ['trend', 'items', 'list', 'data', 'records'])
    const fatList = pickArray(fatData, ['trend', 'items', 'list', 'data', 'records'])

    // 以日期为轴合并两条曲线
    const dateSet = []
    const pushDate = (value) => {
      if (value && !dateSet.includes(value)) dateSet.push(value)
    }
    weightList.forEach((item) => pushDate(pickText(item, ['date', 'metric_date', 'label'])))
    fatList.forEach((item) => pushDate(pickText(item, ['date', 'metric_date', 'label'])))
    dateSet.sort()

    const weightMap = new Map()
    weightList.forEach((item) => {
      weightMap.set(pickText(item, ['date', 'metric_date', 'label']), pickNumber(item, ['weight', 'value']))
    })
    const fatMap = new Map()
    fatList.forEach((item) => {
      fatMap.set(pickText(item, ['date', 'metric_date', 'label']), pickNumber(item, ['body_fat', 'fat', 'value']))
    })

    const weights = dateSet.map((date) => (weightMap.has(date) ? weightMap.get(date) : null))
    const fats = dateSet.map((date) => (fatMap.has(date) ? fatMap.get(date) : null))

    trendEmpty.value = dateSet.length === 0
    renderTrend(dateSet.map((date) => shortLabel(date, '')), weights, fats)
  } catch (error) {
    trendEmpty.value = true
    renderTrend([], [], [])
    ElMessage.warning(`趋势数据加载失败：${error.message}`)
  } finally {
    trendLoading.value = false
  }
}

function renderTrend(labels, weights, fats) {
  if (!weightChartRef.value) return
  if (!weightChart) weightChart = echarts.init(weightChartRef.value)
  weightChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['体重(kg)', '体脂率(%)'], textStyle: { color: '#8b93a7' }, top: 0 },
      grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        axisLabel: { color: '#8b93a7' }
      },
      yAxis: [
        {
          type: 'value',
          name: 'kg',
          scale: true,
          nameTextStyle: { color: '#8b93a7' },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
          axisLabel: { color: '#8b93a7' }
        },
        {
          type: 'value',
          name: '%',
          scale: true,
          nameTextStyle: { color: '#8b93a7' },
          splitLine: { show: false },
          axisLabel: { color: '#8b93a7' }
        }
      ],
      series: [
        {
          name: '体重(kg)',
          type: 'line',
          smooth: true,
          connectNulls: true,
          symbolSize: 5,
          itemStyle: { color: '#ff5a1f' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(255,90,31,0.35)' },
              { offset: 1, color: 'rgba(255,90,31,0)' }
            ])
          },
          data: weights
        },
        {
          name: '体脂率(%)',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          connectNulls: true,
          symbolSize: 5,
          itemStyle: { color: '#38bdf8' },
          data: fats
        }
      ]
    },
    true
  )
}

/* ------------------------------------------------------------------ BMI */
const bmiForm = ref({ weight: 70, height: 175 })
const bmiResult = ref(null)
const bmiLoading = ref(false)
const bmiInfo = computed(() => bmiLevel(bmiResult.value))

const bmiSegments = [
  { text: '偏瘦', color: '#38bdf8' },
  { text: '正常', color: '#22c55e' },
  { text: '超重', color: '#f9b73c' },
  { text: '肥胖', color: '#f04b4b' }
]

async function handleCalcBmi() {
  if (!bmiForm.value.weight || !bmiForm.value.height) {
    ElMessage.warning('请填写体重和身高')
    return
  }
  bmiLoading.value = true
  try {
    const data = await calcBmi({ weight: bmiForm.value.weight, height: bmiForm.value.height })
    const value = pickNumber(data, ['bmi', 'bmi_value', 'value'])
    if (value) {
      bmiResult.value = Number(value.toFixed(1))
    } else {
      // 后端没返回 bmi 字段时按公式本地兜底
      const h = Number(bmiForm.value.height) / 100
      bmiResult.value = Number((Number(bmiForm.value.weight) / (h * h)).toFixed(1))
    }
  } catch (error) {
    ElMessage.error(`BMI 计算失败：${error.message}`)
  } finally {
    bmiLoading.value = false
  }
}

/* ------------------------------------------------------------------ 卡路里收支 */
const monthValue = ref(thisMonth())
const balanceDate = ref(todayStr())
const calorieLoading = ref(false)
const calorieEmpty = ref(false)
const calorieChartRef = ref(null)
const balanceDay = ref({ in: 0, out: 0, net: 0 })
let calorieChart = null

async function loadBalanceDay() {
  try {
    const data = await getCaloriesBalance({ date: balanceDate.value })
    const intake = pickNumber(data, ['intake', 'intake_calories', 'calories_in', 'in', 'total_intake'])
    const burn = pickNumber(data, ['burn', 'burn_calories', 'calories_out', 'out', 'total_burn', 'burned'])
    const net = pickNumber(data, ['net', 'balance', 'net_calories', 'surplus'], intake - burn)
    balanceDay.value = { in: intake, out: burn, net }
  } catch (error) {
    balanceDay.value = { in: 0, out: 0, net: 0 }
  }
}

async function loadCaloriesMonth() {
  const [year, month] = String(monthValue.value || '').split('-')
  if (!year || !month) return
  calorieLoading.value = true
  try {
    const data = await getCaloriesBalanceMonth({ year: Number(year), month: Number(month) })
    const list = pickArray(data, ['days', 'items', 'list', 'daily', 'trend'])
    calorieEmpty.value = list.length === 0

    const labels = list.map((item, index) => shortLabel(pickText(item, ['date', 'day', 'label']), String(index + 1)))
    const intakes = list.map((item) => pickNumber(item, ['intake', 'intake_calories', 'calories_in', 'in']))
    const burns = list.map((item) => pickNumber(item, ['burn', 'burn_calories', 'calories_out', 'out', 'burned']))
    const nets = list.map((item, index) => pickNumber(item, ['net', 'balance', 'net_calories'], intakes[index] - burns[index]))

    renderCalories(labels, intakes, burns, nets)
  } catch (error) {
    calorieEmpty.value = true
    renderCalories([], [], [], [])
    ElMessage.warning(`卡路里收支加载失败：${error.message}`)
  } finally {
    calorieLoading.value = false
  }
}

function renderCalories(labels, intakes, burns, nets) {
  if (!calorieChartRef.value) return
  if (!calorieChart) calorieChart = echarts.init(calorieChartRef.value)
  calorieChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['摄入', '消耗', '净收支'], textStyle: { color: '#8b93a7' }, top: 0 },
      grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        axisLabel: { color: '#8b93a7' }
      },
      yAxis: {
        type: 'value',
        name: '千卡',
        nameTextStyle: { color: '#8b93a7' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#8b93a7' }
      },
      series: [
        {
          name: '摄入',
          type: 'bar',
          barMaxWidth: 14,
          itemStyle: { color: '#22c55e', borderRadius: [3, 3, 0, 0] },
          data: intakes
        },
        {
          name: '消耗',
          type: 'bar',
          barMaxWidth: 14,
          itemStyle: { color: '#f9b73c', borderRadius: [3, 3, 0, 0] },
          data: burns
        },
        {
          name: '净收支',
          type: 'line',
          smooth: true,
          symbolSize: 4,
          itemStyle: { color: '#ff5a1f' },
          data: nets
        }
      ]
    },
    true
  )
}

/* ------------------------------------------------------------------ 训练频率 */
const freqWeeks = ref(8)
const freqLoading = ref(false)
const freqEmpty = ref(false)
const freqChartRef = ref(null)
let freqChart = null

async function loadFrequency() {
  freqLoading.value = true
  try {
    const data = await getFrequency({ weeks: freqWeeks.value })
    const list = pickArray(data, ['weeks', 'items', 'list', 'frequency', 'trend'])
    freqEmpty.value = list.length === 0

    const labels = list.map((item, index) =>
      shortLabel(pickText(item, ['week_start', 'start_date', 'label', 'week']), `第${index + 1}周`)
    )
    const counts = list.map((item) => pickNumber(item, ['count', 'record_count', 'times', 'total_records']))
    renderFrequency(labels, counts)
  } catch (error) {
    freqEmpty.value = true
    renderFrequency([], [])
    ElMessage.warning(`训练频率加载失败：${error.message}`)
  } finally {
    freqLoading.value = false
  }
}

function renderFrequency(labels, counts) {
  if (!freqChartRef.value) return
  if (!freqChart) freqChart = echarts.init(freqChartRef.value)
  freqChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 8, right: 8, top: 20, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        axisLabel: { color: '#8b93a7' }
      },
      yAxis: {
        type: 'value',
        name: '次',
        minInterval: 1,
        nameTextStyle: { color: '#8b93a7' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        axisLabel: { color: '#8b93a7' }
      },
      series: [
        {
          name: '训练次数',
          type: 'bar',
          barMaxWidth: 26,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#ff8148' },
              { offset: 1, color: '#ff5a1f' }
            ])
          },
          data: counts
        }
      ]
    },
    true
  )
}

/* ------------------------------------------------------------------ 体测录入与列表 */
const metricFormRef = ref(null)
const savingMetric = ref(false)
const metricForm = ref({
  metric_date: todayStr(),
  weight: 70,
  body_fat: 18,
  muscle_mass: null,
  waist: null,
  chest: null,
  hip: null,
  note: ''
})

async function handleSaveMetric() {
  if (!metricForm.value.metric_date) {
    ElMessage.warning('请选择记录日期')
    return
  }
  if (!metricForm.value.weight) {
    ElMessage.warning('请填写体重')
    return
  }
  const payload = {
    metric_date: metricForm.value.metric_date,
    weight: Number(metricForm.value.weight),
    body_fat: metricForm.value.body_fat === null ? null : Number(metricForm.value.body_fat),
    muscle_mass: metricForm.value.muscle_mass === null ? null : Number(metricForm.value.muscle_mass),
    waist: metricForm.value.waist === null ? null : Number(metricForm.value.waist),
    chest: metricForm.value.chest === null ? null : Number(metricForm.value.chest),
    hip: metricForm.value.hip === null ? null : Number(metricForm.value.hip),
    note: metricForm.value.note || null
  }
  savingMetric.value = true
  try {
    await createBodyMetric(payload)
    ElMessage.success('身体数据已保存')
    await Promise.all([loadMetrics(), loadTrend(), loadDashboard()])
  } catch (error) {
    ElMessage.error(`保存失败：${error.message}`)
  } finally {
    savingMetric.value = false
  }
}

const metrics = ref([])
const metricLoading = ref(false)
const metricPage = ref(1)
const metricPageSize = ref(10)
const metricTotal = ref(0)

async function loadMetrics() {
  metricLoading.value = true
  try {
    const data = await getBodyMetrics({ page: metricPage.value, page_size: metricPageSize.value })
    metrics.value = Array.isArray(data) ? data : data?.items || []
    metricTotal.value = Array.isArray(data) ? metrics.value.length : Number(data?.total) || 0
  } catch (error) {
    metrics.value = []
    metricTotal.value = 0
    ElMessage.error(`身体数据加载失败：${error.message}`)
  } finally {
    metricLoading.value = false
  }
}

async function handleDeleteMetric(row) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.metric_date || ''} 的身体数据吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteBodyMetric(row.id)
    ElMessage.success('已删除')
    await Promise.all([loadMetrics(), loadTrend()])
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

/* ------------------------------------------------------------------ 生命周期 */
async function refreshAll() {
  refreshing.value = true
  try {
    await Promise.all([
      loadDashboard(),
      loadTrend(),
      loadCaloriesMonth(),
      loadBalanceDay(),
      loadFrequency(),
      loadMetrics()
    ])
    ElMessage.success('数据已刷新')
  } finally {
    refreshing.value = false
  }
}

function handleResize() {
  if (weightChart) weightChart.resize()
  if (calorieChart) calorieChart.resize()
  if (freqChart) freqChart.resize()
}

onMounted(() => {
  loadDashboard()
  loadTrend()
  loadCaloriesMonth()
  loadBalanceDay()
  loadFrequency()
  loadMetrics()
  handleCalcBmi()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (weightChart) {
    weightChart.dispose()
    weightChart = null
  }
  if (calorieChart) {
    calorieChart.dispose()
    calorieChart = null
  }
  if (freqChart) {
    freqChart.dispose()
    freqChart = null
  }
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
}
.page-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ft-text-sub);
}
.summary-row {
  margin-bottom: 2px;
}
.summary-card {
  padding: 14px 16px;
  border-radius: var(--ft-radius-sm);
  background: var(--ft-card);
  border: 1px solid var(--ft-border);
  margin-bottom: 12px;
}
.summary-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--ft-primary);
  line-height: 1.2;
}
.summary-unit {
  font-size: 12px;
  margin-left: 4px;
  color: var(--ft-text-dim);
}
.summary-label {
  margin-top: 6px;
  font-size: 13px;
  color: var(--ft-text-sub);
}
.panel {
  margin-bottom: 12px;
  background: var(--ft-card);
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
  color: var(--ft-text-dim);
}
.panel-tools {
  display: flex;
  gap: 8px;
}
.chart-wrap {
  position: relative;
}
.chart {
  width: 100%;
  height: 240px;
}
.chart-lg {
  height: 288px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--ft-text-dim);
  text-align: center;
  padding: 0 20px;
}
.bmi-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bmi-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bmi-label {
  font-size: 13px;
  color: var(--ft-text-sub);
}
.bmi-result {
  margin-top: 18px;
  text-align: center;
}
.bmi-value {
  font-size: 38px;
  font-weight: 700;
  line-height: 1.1;
}
.bmi-level {
  font-size: 14px;
  font-weight: 600;
  margin-top: 2px;
}
.bmi-scale {
  margin-top: 14px;
}
.bmi-scale-bar {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
}
.bmi-scale-bar span {
  flex: 1;
}
.bmi-scale-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--ft-text-dim);
  margin-top: 4px;
}
.bmi-tip {
  margin-top: 12px;
  font-size: 12px;
  color: var(--ft-text-dim);
  line-height: 1.6;
  text-align: left;
}
.balance-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.balance-item {
  flex: 1 1 120px;
  padding: 10px 12px;
  border-radius: var(--ft-radius-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border);
}
.balance-value {
  font-size: 20px;
  font-weight: 600;
}
.balance-label {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 2px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
