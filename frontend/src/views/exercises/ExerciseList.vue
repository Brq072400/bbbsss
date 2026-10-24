<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">动作库</h2>
        <p class="page-sub">按肌群 / 器械 / 难度筛选，找到适合今天的动作</p>
      </div>
      <el-input
        v-model="keyword"
        placeholder="搜索动作名称，如 深蹲 / squat"
        clearable
        style="width: 260px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #append>
          <el-button @click="handleSearch">搜索</el-button>
        </template>
      </el-input>
    </div>

    <!-- 分类切换 -->
    <div class="category-bar">
      <el-radio-group v-model="categoryId" size="default" @change="handleFilter">
        <el-radio-button :value="0">全部</el-radio-button>
        <el-radio-button v-for="item in categories" :key="item.id" :value="item.id">
          {{ item.name }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 器械 / 难度 / 排序 -->
    <div class="filter-bar">
      <el-select v-model="equipment" placeholder="器械" clearable size="small" style="width: 130px" @change="handleFilter">
        <el-option v-for="item in equipmentOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="difficulty" placeholder="难度" clearable size="small" style="width: 130px" @change="handleFilter">
        <el-option v-for="item in difficultyOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="sort" placeholder="排序" size="small" style="width: 130px" @change="handleFilter">
        <el-option label="默认排序" value="default" />
        <el-option label="最热门" value="hot" />
        <el-option label="最新收录" value="new" />
      </el-select>
      <el-button size="small" @click="resetFilter">重置</el-button>
      <span class="total-tip">共 {{ total }} 个动作</span>
    </div>

    <!-- 卡片列表 -->
    <div v-loading="loading" class="card-wrap">
      <el-empty v-if="!loading && exercises.length === 0" description="没有找到符合条件的动作，换个筛选条件试试" :image-size="90" />
      <el-row v-else :gutter="12">
        <el-col v-for="item in exercises" :key="item.id" :xs="12" :sm="8" :md="6" :lg="6">
          <div class="ex-card" @click="goDetail(item)">
            <div class="ex-cover">
              <el-image v-if="item.image_url" :src="resolveAsset(item.image_url)" fit="cover" class="ex-img" lazy>
                <template #error>
                  <div class="ex-cover-fallback">{{ firstChar(item.name) }}</div>
                </template>
              </el-image>
              <div v-else class="ex-cover-fallback">{{ firstChar(item.name) }}</div>
              <span class="ex-difficulty">难度 {{ item.difficulty || 1 }}</span>
            </div>
            <div class="ex-body">
              <div class="ex-name">{{ item.name }}</div>
              <div class="ex-en">{{ item.name_en || '—' }}</div>
              <div class="ex-tags">
                <el-tag v-if="item.category?.name" size="small" effect="plain" type="primary">{{ item.category.name }}</el-tag>
                <el-tag v-if="item.equipment" size="small" effect="plain" type="info">{{ item.equipment }}</el-tag>
              </div>
              <div class="ex-muscle">{{ item.primary_muscles || '未标注发力肌群' }}</div>
              <el-rate :model-value="Number(item.difficulty) || 0" disabled size="small" :max="5" />
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[12, 24, 48]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="loadExercises"
        @size-change="loadExercises"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getExerciseCategories, getExerciseFilterOptions, getExercises } from '@/api/exercise'
import { resolveAsset } from '@/api/request'

const router = useRouter()

const categories = ref([])
const exercises = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)

const categoryId = ref(0)
const equipment = ref('')
const difficulty = ref('')
const sort = ref('default')
const keyword = ref('')

// 器械/难度选项：优先用后端 filter/options，拿不到就用内置兜底
const equipmentOptions = ref([
  { label: '杠铃', value: '杠铃' },
  { label: '哑铃', value: '哑铃' },
  { label: '自重', value: '自重' },
  { label: '弹力带', value: '弹力带' },
  { label: '器械', value: '器械' }
])

const difficultyOptions = [
  { label: '入门 (1)', value: 1 },
  { label: '初级 (2)', value: 2 },
  { label: '中级 (3)', value: 3 },
  { label: '高级 (4)', value: 4 },
  { label: '大神 (5)', value: 5 }
]

/** 把后端返回的选项结构统一成 [{label, value}] */
function normalizeOptions(raw) {
  if (!Array.isArray(raw)) return []
  const result = []
  raw.forEach((item) => {
    if (item === null || item === undefined) return
    if (typeof item === 'string' || typeof item === 'number') {
      result.push({ label: String(item), value: item })
      return
    }
    if (typeof item === 'object') {
      const value = item.value !== undefined ? item.value : item.id !== undefined ? item.id : item.name
      const label = item.label !== undefined ? item.label : item.name !== undefined ? item.name : String(value)
      if (value !== undefined) result.push({ label: String(label), value })
    }
  })
  return result
}

async function loadCategories() {
  try {
    const data = await getExerciseCategories()
    categories.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    categories.value = []
    ElMessage.warning(`分类加载失败：${error.message}`)
  }
}

async function loadFilterOptions() {
  try {
    const data = await getExerciseFilterOptions()
    const list = normalizeOptions(data?.equipment || data?.equipments)
    if (list.length > 0) equipmentOptions.value = list
  } catch (error) {
    // 拿不到筛选项不影响主流程，用兜底选项即可
  }
}

async function loadExercises() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (categoryId.value) params.category_id = categoryId.value
    if (equipment.value) params.equipment = equipment.value
    if (difficulty.value !== '' && difficulty.value !== null) params.difficulty = difficulty.value
    if (keyword.value) params.keyword = keyword.value
    // 默认排序不传，避免后端枚举校验报错
    if (sort.value && sort.value !== 'default') params.sort = sort.value

    const data = await getExercises(params)
    exercises.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? exercises.value.length : Number(data?.total) || 0
  } catch (error) {
    exercises.value = []
    total.value = 0
    ElMessage.error(`动作加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function handleFilter() {
  page.value = 1
  loadExercises()
}

function handleSearch() {
  handleFilter()
}

function resetFilter() {
  categoryId.value = 0
  equipment.value = ''
  difficulty.value = ''
  sort.value = 'default'
  keyword.value = ''
  handleFilter()
}

function firstChar(name) {
  if (!name) return '动'
  return String(name).slice(0, 1)
}

function goDetail(item) {
  if (!item || !item.id) return
  router.push(`/exercises/${item.id}`)
}

onMounted(() => {
  loadCategories()
  loadFilterOptions()
  loadExercises()
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
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
.category-bar {
  margin-bottom: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.total-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
  margin-left: auto;
}
.card-wrap {
  min-height: 200px;
}
.ex-card {
  margin-bottom: 12px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--el-bg-color-overlay, #1b2230);
  border: 1px solid var(--el-border-color, #2c3444);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease;
}
.ex-card:hover {
  transform: translateY(-3px);
  border-color: var(--el-color-primary, #ff5a1f);
}
.ex-cover {
  position: relative;
  height: 120px;
  background: linear-gradient(135deg, #223047, #2f3d55);
}
.ex-img {
  width: 100%;
  height: 100%;
}
.ex-cover-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.55);
  background: linear-gradient(135deg, #223047, #33425c);
}
.ex-difficulty {
  position: absolute;
  right: 8px;
  top: 8px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
}
.ex-body {
  padding: 10px 12px 12px;
}
.ex-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary, #e6edf3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ex-en {
  font-size: 12px;
  color: var(--el-text-color-secondary, #8b949e);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ex-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 8px 0 6px;
}
.ex-muscle {
  font-size: 12px;
  color: var(--el-text-color-regular, #c9d1d9);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin: 8px 0 24px;
}
</style>
