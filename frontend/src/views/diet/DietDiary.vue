<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">饮食日记</h2>
        <p class="page-sub">记录今天吃了什么，掌握热量与三大营养素</p>
      </div>
      <div class="head-tools">
        <el-date-picker
          v-model="date"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
          style="width: 150px"
          @change="loadDay"
        />
        <el-button @click="goFoodLibrary">食物库</el-button>
        <el-button type="primary" @click="openAddDialog('breakfast')">＋ 添加食物</el-button>
      </div>
    </div>

    <!-- 汇总 -->
    <el-row :gutter="12">
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">{{ date }} 热量汇总</span>
              <span class="panel-hint">共 {{ records.length }} 条记录</span>
            </div>
          </template>
          <div class="chart-wrap">
            <div ref="pieChartRef" v-loading="dayLoading" class="chart"></div>
            <div v-if="!dayLoading && records.length === 0" class="chart-empty">今天还没有饮食记录</div>
          </div>
          <div class="macro-row">
            <div class="macro-item">
              <div class="macro-value">{{ totals.calories }}</div>
              <div class="macro-label">总热量(千卡)</div>
            </div>
            <div class="macro-item">
              <div class="macro-value" style="color: #22c55e">{{ totals.protein }}g</div>
              <div class="macro-label">蛋白质</div>
            </div>
            <div class="macro-item">
              <div class="macro-value" style="color: #f9b73c">{{ totals.fat }}g</div>
              <div class="macro-label">脂肪</div>
            </div>
            <div class="macro-item">
              <div class="macro-value" style="color: #38bdf8">{{ totals.carbohydrate }}g</div>
              <div class="macro-label">碳水</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="panel" v-loading="dayLoading">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">三餐明细</span>
              <el-button size="small" @click="loadDay">刷新</el-button>
            </div>
          </template>

          <div v-for="meal in MEAL_TYPES" :key="meal.value" class="meal-block">
            <div class="meal-head">
              <div class="meal-title">
                <span class="meal-icon">{{ meal.icon }}</span>
                <span>{{ meal.label }}</span>
                <el-tag size="small" effect="plain" :color="'transparent'" :style="{ color: meal.color, borderColor: meal.color }">
                  {{ mealCalories(meal.value) }} 千卡
                </el-tag>
              </div>
              <el-button link type="primary" size="small" @click="openAddDialog(meal.value)">＋ 添加</el-button>
            </div>

            <div v-if="grouped[meal.value].length === 0" class="meal-empty">暂无记录</div>
            <div v-else class="meal-items">
              <div v-for="item in grouped[meal.value]" :key="item.id" class="meal-item">
                <div class="meal-item-main">
                  <span class="meal-item-name">{{ item.food_name }}</span>
                  <span class="meal-item-amount">{{ item.amount_g }}g</span>
                </div>
                <div class="meal-item-nutri">
                  {{ item.calories || 0 }} 千卡 · 蛋白 {{ item.protein || 0 }}g · 脂肪 {{ item.fat || 0 }}g · 碳水
                  {{ item.carbohydrate || 0 }}g
                </div>
                <el-button link type="danger" size="small" @click="handleDeleteRecord(item)">删除</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加食物弹窗 -->
    <el-dialog v-model="addVisible" :title="`添加食物到${currentMealLabel}`" width="560px">
      <div class="dialog-toolbar">
        <el-select v-model="addMealType" size="small" style="width: 110px">
          <el-option v-for="meal in MEAL_TYPES" :key="meal.value" :label="meal.label" :value="meal.value" />
        </el-select>
        <el-input
          v-model="foodKeyword"
          size="small"
          placeholder="搜索食物名称"
          clearable
          style="width: 200px"
          @keyup.enter="loadFoods"
          @clear="loadFoods"
        >
          <template #append>
            <el-button @click="loadFoods">搜索</el-button>
          </template>
        </el-input>
      </div>

      <div v-loading="foodLoading" class="food-pick-list">
        <el-empty v-if="!foodLoading && foods.length === 0" description="没有找到食物，去食物库添加一个吧" :image-size="60" />
        <div
          v-for="food in foods"
          :key="food.id"
          class="food-pick-item"
          :class="{ selected: selectedFood && selectedFood.id === food.id }"
          @click="selectFood(food)"
        >
          <div class="food-pick-main">
            <span class="food-pick-name">{{ food.name }}</span>
            <span class="food-pick-cat">{{ food.category }}</span>
          </div>
          <div class="food-pick-cal">{{ food.calories }} 千卡/100g</div>
        </div>
      </div>

      <div class="amount-bar">
        <span class="amount-label">食用量</span>
        <el-input-number v-model="amountG" :min="1" :max="5000" :step="10" size="small" />
        <span class="amount-unit">克</span>
        <span v-if="selectedFood" class="amount-cal">
          预计 {{ estimatedCalories }} 千卡
        </span>
      </div>

      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" :disabled="!selectedFood" @click="handleAddRecord">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  MEAL_TYPES,
  createDietRecord,
  deleteDietRecord,
  getDietDay,
  getFoods,
  mealLabel
} from '@/api/diet'

const router = useRouter()

const todayStr = () => new Date().toISOString().slice(0, 10)

const date = ref(todayStr())
const dayLoading = ref(false)
const records = ref([])

/* ------------------------------------------------------------------ 分组与汇总 */
const grouped = computed(() => {
  const result = { breakfast: [], lunch: [], dinner: [], snack: [] }
  records.value.forEach((item) => {
    const key = MEAL_TYPES.some((meal) => meal.value === item.meal_type) ? item.meal_type : 'snack'
    result[key].push(item)
  })
  return result
})

const totals = computed(() => {
  const sum = (key) => records.value.reduce((acc, item) => acc + (Number(item[key]) || 0), 0)
  return {
    calories: Number(sum('calories').toFixed(1)),
    protein: Number(sum('protein').toFixed(1)),
    fat: Number(sum('fat').toFixed(1)),
    carbohydrate: Number(sum('carbohydrate').toFixed(1))
  }
})

function mealCalories(mealType) {
  const list = grouped.value[mealType] || []
  return Number(list.reduce((acc, item) => acc + (Number(item.calories) || 0), 0).toFixed(1))
}

/** 把后端返回的当日数据统一成记录数组 */
function collectRecords(data) {
  if (!data) return []
  if (Array.isArray(data)) return data
  if (Array.isArray(data.records)) return data.records
  if (Array.isArray(data.items)) return data.items
  if (Array.isArray(data.list)) return data.list
  if (data.meals && typeof data.meals === 'object') {
    const flat = []
    Object.keys(data.meals).forEach((key) => {
      const value = data.meals[key]
      if (Array.isArray(value)) flat.push(...value.map((item) => ({ meal_type: item.meal_type || key, ...item })))
    })
    return flat
  }
  return []
}

/* ------------------------------------------------------------------ 环形图 */
const pieChartRef = ref(null)
let pieChart = null

function renderPie() {
  if (!pieChartRef.value) return
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)

  const data = MEAL_TYPES.map((meal) => ({
    name: meal.label,
    value: mealCalories(meal.value),
    itemStyle: { color: meal.color }
  })).filter((item) => item.value > 0)

  pieChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} 千卡 ({d}%)'
      },
      legend: {
        bottom: 0,
        textStyle: { color: '#8b93a7' },
        itemWidth: 10,
        itemHeight: 10
      },
      series: [
        {
          name: '热量来源',
          type: 'pie',
          radius: ['48%', '70%'],
          center: ['50%', '44%'],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: '#171b24', borderWidth: 2 },
          label: {
            show: true,
            position: 'center',
            formatter: () => `${totals.value.calories}\n千卡`,
            color: '#e9edf5',
            fontSize: 16,
            fontWeight: 600,
            lineHeight: 22
          },
          labelLine: { show: false },
          emphasis: { label: { show: true, fontSize: 18 } },
          data
        }
      ]
    },
    true
  )
}

/* ------------------------------------------------------------------ 加载当日 */
async function loadDay() {
  dayLoading.value = true
  try {
    const data = await getDietDay({ date: date.value })
    records.value = collectRecords(data)
    renderPie()
  } catch (error) {
    records.value = []
    renderPie()
    ElMessage.error(`饮食记录加载失败：${error.message}`)
  } finally {
    dayLoading.value = false
  }
}

/* ------------------------------------------------------------------ 添加食物 */
const addVisible = ref(false)
const addMealType = ref('breakfast')
const foodKeyword = ref('')
const foods = ref([])
const foodLoading = ref(false)
const selectedFood = ref(null)
const amountG = ref(100)
const adding = ref(false)

const currentMealLabel = computed(() => mealLabel(addMealType.value))

const estimatedCalories = computed(() => {
  if (!selectedFood.value) return 0
  return Number(((Number(selectedFood.value.calories) || 0) * amountG.value) / 100).toFixed(1)
})

function openAddDialog(mealType) {
  addMealType.value = mealType || 'breakfast'
  selectedFood.value = null
  amountG.value = 100
  addVisible.value = true
  if (foods.value.length === 0) loadFoods()
}

async function loadFoods() {
  foodLoading.value = true
  try {
    const data = await getFoods({ page: 1, page_size: 20, keyword: foodKeyword.value || '' })
    foods.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    foods.value = []
    ElMessage.error(`食物加载失败：${error.message}`)
  } finally {
    foodLoading.value = false
  }
}

function selectFood(food) {
  selectedFood.value = food
}

async function handleAddRecord() {
  if (!selectedFood.value) {
    ElMessage.warning('请先选择一个食物')
    return
  }
  const amount = Number(amountG.value) || 0
  if (amount <= 0) {
    ElMessage.warning('请输入有效的食用量')
    return
  }
  const food = selectedFood.value
  const ratio = amount / 100
  const round1 = (value) => Number(((Number(value) || 0) * ratio).toFixed(1))

  const payload = {
    diet_date: date.value,
    meal_type: addMealType.value,
    food_id: food.id,
    food_name: food.name,
    amount_g: amount,
    calories: round1(food.calories),
    protein: round1(food.protein),
    fat: round1(food.fat),
    carbohydrate: round1(food.carbohydrate)
  }

  adding.value = true
  try {
    await createDietRecord(payload)
    ElMessage.success('已添加')
    addVisible.value = false
    await loadDay()
  } catch (error) {
    ElMessage.error(`添加失败：${error.message}`)
  } finally {
    adding.value = false
  }
}

/* ------------------------------------------------------------------ 删除 */
async function handleDeleteRecord(item) {
  try {
    await ElMessageBox.confirm(`确定删除「${item.food_name}」这条饮食记录吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteDietRecord(item.id)
    ElMessage.success('已删除')
    await loadDay()
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

function goFoodLibrary() {
  router.push('/diet/foods')
}

function handleResize() {
  if (pieChart) pieChart.resize()
}

onMounted(() => {
  loadDay()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (pieChart) {
    pieChart.dispose()
    pieChart = null
  }
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
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
.head-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
.chart-wrap {
  position: relative;
}
.chart {
  width: 100%;
  height: 240px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--ft-text-dim);
}
.macro-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.macro-item {
  flex: 1 1 90px;
  padding: 10px 12px;
  border-radius: var(--ft-radius-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border);
  text-align: center;
}
.macro-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--ft-primary);
}
.macro-label {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 2px;
}
.meal-block {
  padding: 10px 0;
  border-top: 1px solid var(--ft-border);
}
.meal-block:first-child {
  border-top: none;
  padding-top: 0;
}
.meal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.meal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}
.meal-icon {
  font-size: 15px;
}
.meal-empty {
  font-size: 12px;
  color: var(--ft-text-dim);
  padding: 6px 0 2px;
}
.meal-items {
  margin-top: 6px;
}
.meal-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--ft-radius-sm);
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.meal-item-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 140px;
  flex: 0 0 auto;
}
.meal-item-name {
  font-size: 14px;
  font-weight: 500;
}
.meal-item-amount {
  font-size: 12px;
  color: var(--ft-primary);
}
.meal-item-nutri {
  flex: 1;
  font-size: 12px;
  color: var(--ft-text-dim);
  min-width: 180px;
}
.dialog-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.food-pick-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--ft-border);
  border-radius: var(--ft-radius-sm);
  padding: 6px;
  min-height: 120px;
}
.food-pick-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
}
.food-pick-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.food-pick-item.selected {
  background: var(--ft-primary-soft);
  border: 1px solid rgba(255, 90, 31, 0.4);
}
.food-pick-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.food-pick-name {
  font-size: 14px;
}
.food-pick-cat {
  font-size: 12px;
  color: var(--ft-text-dim);
}
.food-pick-cal {
  font-size: 12px;
  color: var(--ft-text-sub);
}
.amount-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.amount-label {
  font-size: 13px;
  color: var(--ft-text-sub);
}
.amount-unit {
  font-size: 13px;
  color: var(--ft-text-dim);
}
.amount-cal {
  font-size: 13px;
  color: var(--ft-primary);
  margin-left: auto;
}
</style>
