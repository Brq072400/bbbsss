<template>
  <div class="ft-page">
    <div class="page-head">
      <el-button @click="goBack">← 返回动作库</el-button>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" class="load-error">
      <template #default>
        <el-button link type="primary" size="small" @click="loadDetail">重新加载</el-button>
      </template>
    </el-alert>

    <div v-loading="loading">
      <el-empty v-if="!loading && !exercise" description="动作不存在或已下架" :image-size="90" />

      <template v-if="exercise">
        <!-- 头部信息 -->
        <el-card shadow="never" class="panel hero-card">
          <div class="hero">
            <div class="hero-media">
              <el-image
                v-if="exercise.gif_url || exercise.image_url"
                :src="resolveAsset(exercise.gif_url || exercise.image_url)"
                fit="cover"
                class="hero-img"
              >
                <template #error>
                  <div class="hero-fallback">{{ firstChar(exercise.name) }}</div>
                </template>
              </el-image>
              <div v-else class="hero-fallback">{{ firstChar(exercise.name) }}</div>
            </div>
            <div class="hero-info">
              <h2 class="hero-name">{{ exercise.name }}</h2>
              <p class="hero-en">{{ exercise.name_en || '—' }}</p>
              <div class="hero-tags">
                <el-tag v-if="exercise.category?.name" type="primary" effect="dark">
                  {{ exercise.category.name }}
                </el-tag>
                <el-tag v-if="exercise.equipment" type="info" effect="plain">{{ exercise.equipment }}</el-tag>
                <el-tag v-if="exercise.category?.body_part" type="success" effect="plain">
                  {{ exercise.category.body_part }}
                </el-tag>
              </div>
              <div class="hero-rate">
                <span class="rate-label">难度：{{ difficultyLabel(exercise.difficulty) }}</span>
                <el-rate :model-value="Number(exercise.difficulty) || 0" disabled :max="5" />
              </div>
              <div class="muscle-row">
                <div class="muscle-item">
                  <span class="muscle-label">主要肌群</span>
                  <span class="muscle-value">{{ exercise.primary_muscles || '未标注' }}</span>
                </div>
                <div class="muscle-item">
                  <span class="muscle-label">协同肌群</span>
                  <span class="muscle-value">{{ exercise.secondary_muscles || '未标注' }}</span>
                </div>
              </div>
              <div class="hero-view">👁 浏览 {{ exercise.view_count || 0 }} 次</div>
            </div>
          </div>
        </el-card>

        <!-- 讲解 / 要点 / 易错 / 呼吸 -->
        <el-row :gutter="12">
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="panel">
              <template #header><span class="panel-title">📖 动作讲解</span></template>
              <el-empty v-if="descriptionLines.length === 0" description="暂无讲解内容" :image-size="60" />
              <p v-for="(line, index) in descriptionLines" :key="`d-${index}`" class="paragraph">{{ line }}</p>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="panel">
              <template #header><span class="panel-title">🎯 发力要点</span></template>
              <el-empty v-if="keyPointLines.length === 0" description="暂无发力要点" :image-size="60" />
              <ul class="point-list">
                <li v-for="(line, index) in keyPointLines" :key="`k-${index}`">
                  <span class="point-index">{{ index + 1 }}</span>
                  <span>{{ line }}</span>
                </li>
              </ul>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="panel">
              <template #header><span class="panel-title">⚠️ 易错提醒</span></template>
              <el-empty v-if="mistakeLines.length === 0" description="暂无易错提醒" :image-size="60" />
              <div v-for="(line, index) in mistakeLines" :key="`m-${index}`" class="mistake-item">
                <span class="mistake-icon">!</span>
                <span>{{ line }}</span>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="panel">
              <template #header><span class="panel-title">🫁 呼吸与节奏</span></template>
              <el-empty v-if="tipsLines.length === 0" description="暂无呼吸提示" :image-size="60" />
              <p v-for="(line, index) in tipsLines" :key="`t-${index}`" class="paragraph">{{ line }}</p>
            </el-card>
          </el-col>
        </el-row>

        <!-- 相似动作 -->
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">🔁 相似动作</span></template>
          <el-empty v-if="related.length === 0" description="暂无相似动作推荐" :image-size="60" />
          <el-row v-else :gutter="12">
            <el-col v-for="item in related" :key="item.id" :xs="12" :sm="8" :md="6">
              <div class="rel-card" @click="goDetail(item.id)">
                <div class="rel-name">{{ item.name }}</div>
                <div class="rel-meta">
                  {{ item.equipment || '—' }} · 难度 {{ item.difficulty || 1 }}
                </div>
                <div class="rel-muscle">{{ item.primary_muscles || item.category?.name || '' }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { difficultyLabel, getExerciseDetail, getRelatedExercises } from '@/api/exercise'
import { resolveAsset } from '@/api/request'

const route = useRoute()
const router = useRouter()

const exercise = ref(null)
const related = ref([])
const loading = ref(false)
const loadError = ref('')

const exerciseId = computed(() => route.params.id || route.query.id || '')

/** 多行文本 → 列表（兼容换行 / 分号分隔） */
function splitLines(text) {
  if (!text) return []
  const raw = String(text).trim()
  if (!raw) return []
  let lines = raw.split(/\r?\n/)
  if (lines.length === 1) {
    const bySemicolon = raw.split(/[；;]/)
    if (bySemicolon.length > 1) lines = bySemicolon
  }
  return lines.map((item) => item.replace(/^[\s\-*·•]+/, '').trim()).filter(Boolean)
}

const descriptionLines = computed(() => splitLines(exercise.value?.description))
const keyPointLines = computed(() => splitLines(exercise.value?.key_points))
const mistakeLines = computed(() => splitLines(exercise.value?.common_mistakes))
const tipsLines = computed(() => splitLines(exercise.value?.tips))

function firstChar(name) {
  if (!name) return '动'
  return String(name).slice(0, 1)
}

async function loadDetail() {
  if (!exerciseId.value) {
    loadError.value = '缺少动作 ID'
    return
  }
  loading.value = true
  loadError.value = ''
  exercise.value = null
  related.value = []
  try {
    const data = await getExerciseDetail(exerciseId.value)
    if (!data) {
      loadError.value = '动作不存在或已下架'
      return
    }
    exercise.value = data
    loadRelated()
  } catch (error) {
    loadError.value = `加载失败：${error.message}`
  } finally {
    loading.value = false
  }
}

async function loadRelated() {
  try {
    const data = await getRelatedExercises(exerciseId.value)
    related.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    related.value = []
    ElMessage.warning(`相似动作加载失败：${error.message}`)
  }
}

function goBack() {
  router.push('/exercises')
}

function goDetail(id) {
  if (!id) return
  router.push(`/exercises/${id}`)
  if (String(id) !== String(exerciseId.value)) {
    loadDetail()
  }
}

// 同一路由切换 id 时重新加载
watch(exerciseId, (value, oldValue) => {
  if (value && value !== oldValue) loadDetail()
})

onMounted(loadDetail)
</script>

<style scoped>
.page-head {
  margin-bottom: 14px;
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
  gap: 18px;
  flex-wrap: wrap;
}
.hero-media {
  width: 220px;
  height: 160px;
  border-radius: 10px;
  overflow: hidden;
  flex: 0 0 auto;
  background: #223047;
}
.hero-img {
  width: 100%;
  height: 100%;
}
.hero-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.5);
  background: linear-gradient(135deg, #223047, #33425c);
}
.hero-info {
  flex: 1 1 260px;
  min-width: 240px;
}
.hero-name {
  margin: 0;
  font-size: 22px;
  color: var(--el-text-color-primary, #e6edf3);
}
.hero-en {
  margin: 4px 0 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.hero-rate {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.rate-label {
  font-size: 13px;
  color: var(--el-text-color-secondary, #8b949e);
}
.muscle-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.muscle-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.muscle-label {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
}
.muscle-value {
  font-size: 14px;
  color: var(--el-color-primary, #ff5a1f);
  font-weight: 600;
}
.hero-view {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
}
.paragraph {
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-regular, #c9d1d9);
}
.point-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.point-list li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-regular, #c9d1d9);
  margin-bottom: 8px;
}
.point-index {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--el-color-primary, #ff5a1f);
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
}
.mistake-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-regular, #c9d1d9);
  margin-bottom: 8px;
}
.mistake-icon {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(240, 75, 75, 0.18);
  color: #f04b4b;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
}
.rel-card {
  border: 1px solid var(--el-border-color, #2c3444);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: border-color 0.18s ease;
}
.rel-card:hover {
  border-color: var(--el-color-primary, #ff5a1f);
}
.rel-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary, #e6edf3);
}
.rel-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
  margin: 4px 0 2px;
}
.rel-muscle {
  font-size: 12px;
  color: var(--el-color-primary, #ff5a1f);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
