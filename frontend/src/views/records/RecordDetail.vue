<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">训练详情</h2>
        <p class="page-sub">按动作分组的组次明细，看清每组的表现</p>
      </div>
      <div>
        <el-button @click="goBack">返回列表</el-button>
        <el-button v-if="record" type="primary" plain @click="goEdit">编辑</el-button>
        <el-button v-if="record" type="danger" plain @click="handleDelete">删除</el-button>
      </div>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" class="load-error">
      <template #default>
        <el-button link type="primary" size="small" @click="loadDetail">重新加载</el-button>
      </template>
    </el-alert>

    <div v-loading="loading">
      <!-- 概况 -->
      <el-card v-if="record" shadow="never" class="panel">
        <div class="hero">
          <div class="hero-main">
            <div class="hero-title">
              {{ record.title || '未命名训练' }}
              <el-tag
                size="small"
                effect="dark"
                :color="workoutTypeColor(record.workout_type)"
                style="border: none; margin-left: 8px"
              >
                {{ workoutTypeLabel(record.workout_type) }}
              </el-tag>
            </div>
            <div class="hero-meta">
              <span>📅 {{ record.workout_date || '—' }}</span>
              <span>⏱ {{ record.duration_min || 0 }} 分钟</span>
              <span>🔥 {{ record.calories || 0 }} 千卡</span>
              <span class="hero-rate">
                感受
                <el-rate :model-value="Number(record.feeling) || 0" disabled size="small" />
              </span>
            </div>
          </div>
          <div class="hero-stats">
            <div class="hero-stat">
              <div class="hero-stat-value">{{ groups.length }}</div>
              <div class="hero-stat-label">动作数</div>
            </div>
            <div class="hero-stat">
              <div class="hero-stat-value">{{ totalSets }}</div>
              <div class="hero-stat-label">总组数</div>
            </div>
            <div class="hero-stat">
              <div class="hero-stat-value">{{ totalVolume }}</div>
              <div class="hero-stat-label">总容量(kg)</div>
            </div>
          </div>
        </div>
        <el-divider v-if="record.note" />
        <div v-if="record.note" class="hero-note">备注：{{ record.note }}</div>
      </el-card>

      <!-- 按动作分组 -->
      <el-card v-if="record" shadow="never" class="panel">
        <template #header>
          <span class="panel-title">动作明细</span>
        </template>

        <el-empty v-if="groups.length === 0" description="这次训练没有记录动作明细" :image-size="80" />

        <div v-for="group in groups" :key="group.key" class="group-block">
          <div class="group-head">
            <div class="group-name">
              <span class="dot"></span>
              {{ group.name }}
              <el-tag v-if="group.exerciseId" size="small" type="info" effect="plain">动作库 #{{ group.exerciseId }}</el-tag>
            </div>
            <div class="group-summary">
              共 {{ group.sets.length }} 组
              <template v-if="group.volume > 0"> · 容量 {{ group.volume }} kg</template>
              <template v-if="group.totalReps > 0"> · 总次数 {{ group.totalReps }}</template>
              <template v-if="group.totalDuration > 0"> · 总时长 {{ group.totalDuration }} 秒</template>
              <template v-if="group.totalDistance > 0"> · 总距离 {{ group.totalDistance }} km</template>
            </div>
          </div>
          <el-table :data="group.sets" size="small" style="width: 100%">
            <el-table-column label="第几组" width="90">
              <template #default="{ row }">{{ row.set_index }}</template>
            </el-table-column>
            <el-table-column label="重量(kg)" width="110">
              <template #default="{ row }">{{ formatNumber(row.weight) }}</template>
            </el-table-column>
            <el-table-column label="次数" width="90">
              <template #default="{ row }">{{ row.reps || 0 }}</template>
            </el-table-column>
            <el-table-column label="时长(秒)" width="110">
              <template #default="{ row }">{{ row.duration_sec ? row.duration_sec : '—' }}</template>
            </el-table-column>
            <el-table-column label="距离(km)" width="110">
              <template #default="{ row }">{{ row.distance_km ? row.distance_km : '—' }}</template>
            </el-table-column>
            <el-table-column label="容量(kg)" width="120">
              <template #default="{ row }">{{ (Number(row.weight || 0) * Number(row.reps || 0)).toFixed(1) }}</template>
            </el-table-column>
            <el-table-column label="备注" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.note || '—' }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteRecord, getRecordDetail, workoutTypeColor, workoutTypeLabel } from '@/api/record'

const route = useRoute()
const router = useRouter()

const recordId = computed(() => route.params.id || route.query.id || '')

const record = ref(null)
const rawSets = ref([])
const loading = ref(false)
const loadError = ref('')

function formatNumber(value) {
  const num = Number(value)
  if (!num) return '0'
  return Number.isInteger(num) ? String(num) : num.toFixed(1)
}

/** 归一化组次数组 */
function normalizeSets(data) {
  if (Array.isArray(data)) return data
  if (!data || typeof data !== 'object') return []
  for (const key of ['sets', 'items', 'details', 'records']) {
    if (Array.isArray(data[key])) return data[key]
  }
  return []
}

const groups = computed(() => {
  const map = new Map()
  rawSets.value.forEach((item) => {
    const name = item.exercise_name || '未命名动作'
    const key = item.exercise_id ? `id-${item.exercise_id}` : `name-${name}`
    if (!map.has(key)) {
      map.set(key, { key, name, exerciseId: item.exercise_id || null, sets: [] })
    }
    map.get(key).sets.push(item)
  })

  return Array.from(map.values()).map((group) => {
    const sorted = [...group.sets].sort((a, b) => (Number(a.set_index) || 0) - (Number(b.set_index) || 0))
    const volume = sorted.reduce((sum, row) => sum + Number(row.weight || 0) * Number(row.reps || 0), 0)
    const totalReps = sorted.reduce((sum, row) => sum + Number(row.reps || 0), 0)
    const totalDuration = sorted.reduce((sum, row) => sum + Number(row.duration_sec || 0), 0)
    const totalDistance = sorted.reduce((sum, row) => sum + Number(row.distance_km || 0), 0)
    return {
      ...group,
      sets: sorted,
      volume: Number(volume.toFixed(1)),
      totalReps,
      totalDuration,
      totalDistance: Number(totalDistance.toFixed(2))
    }
  })
})

const totalSets = computed(() => rawSets.value.length)

const totalVolume = computed(() => {
  const sum = rawSets.value.reduce((acc, row) => acc + Number(row.weight || 0) * Number(row.reps || 0), 0)
  return Number(sum.toFixed(1))
})

async function loadDetail() {
  if (!recordId.value) {
    loadError.value = '缺少记录 ID'
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const data = await getRecordDetail(recordId.value)
    if (!data) {
      loadError.value = '记录不存在或已被删除'
      record.value = null
      rawSets.value = []
      return
    }
    record.value = data
    rawSets.value = normalizeSets(data.sets ? { sets: data.sets } : data)
  } catch (error) {
    loadError.value = `加载失败：${error.message}`
    record.value = null
    rawSets.value = []
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/records')
}

function goEdit() {
  router.push(`/records/${recordId.value}/edit`)
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确定删除这条训练记录吗？', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteRecord(recordId.value)
    ElMessage.success('已删除')
    router.push('/records')
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

onMounted(loadDetail)
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
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary, #e6edf3);
}
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.hero-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary, #e6edf3);
  display: flex;
  align-items: center;
}
.hero-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.hero-rate {
  display: flex;
  align-items: center;
  gap: 4px;
}
.hero-stats {
  display: flex;
  gap: 22px;
}
.hero-stat {
  text-align: center;
}
.hero-stat-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--el-color-primary, #409eff);
}
.hero-stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
}
.hero-note {
  font-size: 13px;
  color: var(--el-text-color-regular, #c9d1d9);
  line-height: 1.7;
}
.group-block {
  margin-bottom: 18px;
}
.group-block:last-child {
  margin-bottom: 0;
}
.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.group-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary, #e6edf3);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-primary, #409eff);
  display: inline-block;
}
.group-summary {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
}
</style>
