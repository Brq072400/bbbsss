<script setup>
/**
 * CourseList.vue 课程中心
 * 功能：分类 Tab、难度筛选、关键词搜索、排序、分页、收藏切换
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  favoriteCourse,
  getCourseCategories,
  getCourseList,
  unfavoriteCourse
} from '@/api/course'
import { resolveAsset } from '@/api/request'

const router = useRouter()

// ---------------- 筛选条件 ----------------
/** 分类列表（第一个是「全部」占位） */
const categories = ref([])
const categoriesLoading = ref(true)
/** 当前分类 id：'' 表示全部 */
const activeCategory = ref('')
/** 难度：'' 全部 / 1 初级 / 2 中级 / 3 高级 */
const difficulty = ref('')
/** 搜索关键词 */
const keyword = ref('')
/** 排序方式 */
const sort = ref('latest')

const difficultyOptions = [
  { label: '全部难度', value: '' },
  { label: '初级', value: 1 },
  { label: '中级', value: 2 },
  { label: '高级', value: 3 },
  { label: '进阶', value: 4 },
  { label: '极限', value: 5 }
]

const sortOptions = [
  { label: '最热播放', value: 'hot' },
  { label: '最新上架', value: 'new' },
  { label: '评分最高', value: 'rating' }
]

// ---------------- 列表数据 ----------------
const courses = ref([])
const loading = ref(true)
const errorMsg = ref('')
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)
/** 收藏操作中的课程 id 集合 */
const favoriting = ref({})

/** 难度文案 */
const difficultyMap = { 1: '初级', 2: '中级', 3: '高级', 4: '高级', 5: '专家' }
/** 难度对应的标签色 */
const difficultyClass = {
  1: 'ft-chip--success',
  2: 'ft-chip--warning',
  3: 'ft-chip--danger',
  4: 'ft-chip--danger',
  5: 'ft-chip--danger'
}

/** 统一列表结构 */
function normalizeList(data) {
  if (Array.isArray(data)) return data
  return data?.items || data?.list || []
}

/** 加载分类 */
async function loadCategories() {
  categoriesLoading.value = true
  try {
    const data = await getCourseCategories()
    categories.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    categories.value = []
  } finally {
    categoriesLoading.value = false
  }
}

/** 加载课程列表 */
async function loadCourses() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      sort: sort.value
    }
    if (activeCategory.value !== '') params.category_id = activeCategory.value
    if (difficulty.value !== '') params.difficulty = difficulty.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()

    const data = await getCourseList(params)
    courses.value = normalizeList(data)
    total.value = Number(data?.total ?? courses.value.length)
  } catch (error) {
    courses.value = []
    total.value = 0
    errorMsg.value = '课程列表加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// ---------------- 交互 ----------------
/** 切换分类（重置到第一页） */
function handleCategoryChange(id) {
  activeCategory.value = id
  page.value = 1
  loadCourses()
}

/** 难度变化 */
function handleDifficultyChange() {
  page.value = 1
  loadCourses()
}

/** 排序变化 */
function handleSortChange() {
  page.value = 1
  loadCourses()
}

/** 搜索（回车或点击按钮触发） */
function handleSearch() {
  page.value = 1
  loadCourses()
}

/** 清空筛选条件 */
function handleResetFilters() {
  activeCategory.value = ''
  difficulty.value = ''
  keyword.value = ''
  sort.value = 'latest'
  page.value = 1
  loadCourses()
}

/** 分页切换 */
function handlePageChange(nextPage) {
  page.value = nextPage
  loadCourses()
}

/** 收藏 / 取消收藏课程 */
async function handleToggleFavorite(course) {
  const id = course.id
  favoriting.value = { ...favoriting.value, [id]: true }
  try {
    if (course.is_favorited) {
      await unfavoriteCourse(id)
      course.is_favorited = false
      course.favorite_count = Math.max(0, Number(course.favorite_count || 0) - 1)
      ElMessage.success('已取消收藏')
    } else {
      await favoriteCourse(id)
      course.is_favorited = true
      course.favorite_count = Number(course.favorite_count || 0) + 1
      ElMessage.success('已收藏，可在「我的收藏」中查看')
    }
  } catch (error) {
    /* 错误已提示 */
  } finally {
    favoriting.value = { ...favoriting.value, [id]: false }
  }
}

/** 课程封面地址 */
function coverOf(course) {
  return resolveAsset(course.cover || '')
}

/** 分类名称（后端可能内嵌 category 对象） */
function categoryName(course) {
  return course.category?.name || course.category_name || ''
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadCourses()])
})
</script>

<template>
  <div class="ft-page">
    <PageHeader title="课程中心" subtitle="跟练专业课程，按分类、难度与评分快速找到适合你的训练">
      <template #actions>
        <el-input
          v-model="keyword"
          placeholder="搜索课程名称 / 教练"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">搜索</el-button>
          </template>
        </el-input>
      </template>
    </PageHeader>

    <!-- ============ 分类 Tab ============ -->
    <div class="course-tabs">
      <div v-if="categoriesLoading" class="ft-loading-text" style="padding: 12px 0">分类加载中…</div>
      <div v-else class="course-tabs__list">
        <button
          type="button"
          class="course-tabs__item"
          :class="{ 'course-tabs__item--active': activeCategory === '' }"
          @click="handleCategoryChange('')"
        >
          全部
        </button>
        <button
          v-for="cat in categories"
          :key="cat.id"
          type="button"
          class="course-tabs__item"
          :class="{ 'course-tabs__item--active': activeCategory === cat.id }"
          @click="handleCategoryChange(cat.id)"
        >
          <span v-if="cat.icon" class="course-tabs__icon">{{ cat.icon }}</span>
          {{ cat.name }}
        </button>
      </div>
    </div>

    <!-- ============ 筛选工具条 ============ -->
    <div class="ft-toolbar">
      <el-select v-model="difficulty" placeholder="难度" style="width: 130px" @change="handleDifficultyChange">
        <el-option
          v-for="opt in difficultyOptions"
          :key="String(opt.value)"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-select v-model="sort" placeholder="排序" style="width: 140px" @change="handleSortChange">
        <el-option v-for="opt in sortOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>

      <el-button @click="handleResetFilters">重置筛选</el-button>
      <span class="ft-toolbar__spacer"></span>
      <span class="ft-muted" style="font-size: 12px">共 {{ total }} 门课程</span>
    </div>

    <!-- ============ 列表 ============ -->
    <div v-if="loading" class="course-grid">
      <div v-for="i in 8" :key="i" class="ft-card course-card course-card--skeleton">
        <el-skeleton :rows="4" animated />
      </div>
    </div>

    <EmptyState v-else-if="errorMsg" icon="⚠️" :description="errorMsg" error>
      <el-button @click="loadCourses">重新加载</el-button>
    </EmptyState>

    <EmptyState
      v-else-if="!courses.length"
      icon="🎬"
      description="没有找到符合条件的课程，换个筛选条件试试"
    >
      <el-button @click="handleResetFilters">重置筛选</el-button>
    </EmptyState>

    <template v-else>
      <div class="course-grid">
        <article
          v-for="course in courses"
          :key="course.id"
          class="ft-card ft-card--hover course-card"
          @click="router.push(`/courses/${course.id}`)"
        >
          <div
            class="course-card__cover"
            :style="coverOf(course) ? { backgroundImage: `url(${coverOf(course)})` } : {}"
          >
            <span v-if="!coverOf(course)" class="course-card__cover-fallback">🎬</span>
            <span class="course-card__play">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </span>
            <span class="course-card__duration">{{ course.duration_min || 0 }} 分钟</span>
          </div>

          <div class="course-card__body">
            <div class="course-card__head">
              <h3 class="course-card__title" :title="course.title">{{ course.title }}</h3>
              <button
                type="button"
                class="course-card__fav"
                :class="{ 'course-card__fav--on': course.is_favorited }"
                :disabled="favoriting[course.id]"
                :title="course.is_favorited ? '取消收藏' : '收藏课程'"
                @click.stop="handleToggleFavorite(course)"
              >
                {{ course.is_favorited ? '★' : '☆' }}
              </button>
            </div>

            <p class="course-card__subtitle ft-ellipsis-2">
              {{ course.subtitle || course.description || '暂无课程简介' }}
            </p>

            <div class="course-card__chips">
              <span v-if="categoryName(course)" class="ft-chip ft-chip--primary">{{ categoryName(course) }}</span>
              <span class="ft-chip" :class="difficultyClass[course.difficulty] || ''">
                {{ difficultyMap[course.difficulty] || '初级' }}
              </span>
              <span v-if="course.calories" class="ft-chip">🔥 {{ course.calories }} 千卡</span>
              <span v-if="course.equipment" class="ft-chip">🏋️ {{ course.equipment }}</span>
            </div>

            <div class="course-card__meta">
              <span class="course-card__rating">
                ⭐ {{ Number(course.rating_avg || 0).toFixed(1) }}
                <em>({{ course.rating_count || 0 }})</em>
              </span>
              <span class="ft-muted">
                {{ course.coach_name ? `教练 ${course.coach_name}` : '暂无教练信息' }}
              </span>
            </div>
          </div>
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
  </div>
</template>

<style scoped>
/* 分类 Tab */
.course-tabs {
  margin-bottom: 14px;
}

.course-tabs__list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.course-tabs__item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 15px;
  border-radius: 999px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--ft-text-sub);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.course-tabs__item:hover {
  color: var(--ft-text);
  border-color: var(--ft-border-strong);
}

.course-tabs__item--active {
  background: var(--ft-primary);
  border-color: var(--ft-primary);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 6px 18px rgba(255, 90, 31, 0.32);
}

.course-tabs__icon {
  font-size: 13px;
}

/* 课程卡片 */
.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.course-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.course-card--skeleton {
  padding: 16px;
  cursor: default;
}

.course-card__cover {
  position: relative;
  height: 132px;
  background: linear-gradient(135deg, rgba(255, 90, 31, 0.26), rgba(40, 70, 160, 0.22));
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.course-card__cover-fallback {
  font-size: 32px;
  opacity: 0.6;
}

.course-card__play {
  position: absolute;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(255, 90, 31, 0.88);
  box-shadow: 0 6px 20px rgba(255, 90, 31, 0.45);
  transition: transform 0.18s ease;
}

.course-card:hover .course-card__play {
  transform: scale(1.12);
}

.course-card__duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 11px;
  color: #fff;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
}

.course-card__body {
  padding: 13px 15px 15px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.course-card__head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.course-card__title {
  flex: 1;
  font-size: 15px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.course-card__fav {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.04);
  color: var(--ft-text-dim);
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.18s ease;
}

.course-card__fav:hover {
  color: var(--ft-warning);
  border-color: rgba(249, 183, 60, 0.5);
}

.course-card__fav--on {
  color: var(--ft-warning);
  border-color: rgba(249, 183, 60, 0.5);
  background: rgba(249, 183, 60, 0.14);
}

.course-card__subtitle {
  font-size: 12px;
  color: var(--ft-text-dim);
  min-height: 34px;
}

.course-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.course-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--ft-border);
  font-size: 11px;
}

.course-card__rating {
  color: var(--ft-warning);
  font-weight: 600;
}

.course-card__rating em {
  font-style: normal;
  color: var(--ft-text-dim);
  font-weight: 400;
}
</style>
