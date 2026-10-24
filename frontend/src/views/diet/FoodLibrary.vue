<template>
  <div class="ft-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">食物库</h2>
        <p class="page-sub">每 100 克营养数据，支持添加自己的常用食物</p>
      </div>
      <el-button type="primary" @click="openCreateDialog">＋ 自定义食物</el-button>
    </div>

    <!-- 筛选 -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索食物名称"
        clearable
        style="width: 220px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #append>
          <el-button @click="handleSearch">搜索</el-button>
        </template>
      </el-input>
      <el-select v-model="category" placeholder="全部分类" clearable style="width: 140px" @change="handleSearch">
        <el-option v-for="item in categories" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button @click="resetFilter">重置</el-button>
      <span class="total-tip">共 {{ total }} 种食物</span>
    </div>

    <!-- 列表 -->
    <el-card shadow="never" class="panel">
      <el-table v-loading="loading" :data="foods" size="small" style="width: 100%">
        <el-table-column label="食物名称" min-width="150">
          <template #default="{ row }">
            <span class="food-name">{{ row.name }}</span>
            <el-tag v-if="!row.is_common" size="small" type="warning" effect="plain" style="margin-left: 6px">自定义</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="unit" label="单位" width="90" />
        <el-table-column label="热量(千卡)" width="110">
          <template #default="{ row }">{{ row.calories || 0 }}</template>
        </el-table-column>
        <el-table-column label="蛋白(g)" width="100">
          <template #default="{ row }">{{ row.protein || 0 }}</template>
        </el-table-column>
        <el-table-column label="脂肪(g)" width="100">
          <template #default="{ row }">{{ row.fat || 0 }}</template>
        </el-table-column>
        <el-table-column label="碳水(g)" width="100">
          <template #default="{ row }">{{ row.carbohydrate || 0 }}</template>
        </el-table-column>
        <el-table-column label="纤维(g)" width="100">
          <template #default="{ row }">{{ row.fiber || 0 }}</template>
        </el-table-column>
        <el-table-column label="钠(mg)" width="100">
          <template #default="{ row }">{{ row.sodium || 0 }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-button v-if="canDelete(row)" link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有找到食物，试试其它关键词或添加自定义食物" :image-size="80" />
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
          @current-change="loadFoods"
          @size-change="loadFoods"
        />
      </div>
    </el-card>

    <!-- 食物详情 -->
    <el-dialog v-model="detailVisible" :title="detailFood?.name || '食物详情'" width="420px">
      <el-descriptions v-if="detailFood" :column="1" border size="small" class="ft-desc">
        <el-descriptions-item label="分类">{{ detailFood.category || '—' }}</el-descriptions-item>
        <el-descriptions-item label="计量单位">{{ detailFood.unit || '100g' }}</el-descriptions-item>
        <el-descriptions-item label="热量">{{ detailFood.calories || 0 }} 千卡 / 100g</el-descriptions-item>
        <el-descriptions-item label="蛋白质">{{ detailFood.protein || 0 }} g</el-descriptions-item>
        <el-descriptions-item label="脂肪">{{ detailFood.fat || 0 }} g</el-descriptions-item>
        <el-descriptions-item label="碳水化合物">{{ detailFood.carbohydrate || 0 }} g</el-descriptions-item>
        <el-descriptions-item label="膳食纤维">{{ detailFood.fiber || 0 }} g</el-descriptions-item>
        <el-descriptions-item label="钠">{{ detailFood.sodium || 0 }} mg</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 自定义食物 -->
    <el-dialog v-model="createVisible" title="添加自定义食物" width="480px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="createForm.name" maxlength="100" placeholder="例如：自制鸡胸肉沙拉" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="createForm.category" style="width: 100%">
            <el-option label="主食" value="主食" />
            <el-option label="肉蛋" value="肉蛋" />
            <el-option label="蔬菜" value="蔬菜" />
            <el-option label="水果" value="水果" />
            <el-option label="乳品" value="乳品" />
            <el-option label="零食" value="零食" />
            <el-option label="其他" value="others" />
          </el-select>
        </el-form-item>
        <el-form-item label="计量单位">
          <el-input v-model="createForm.unit" placeholder="默认 100g" />
        </el-form-item>
        <el-form-item label="热量(千卡)" prop="calories">
          <el-input-number v-model="createForm.calories" :min="0" :max="1000" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="蛋白质(g)">
          <el-input-number v-model="createForm.protein" :min="0" :max="100" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="脂肪(g)">
          <el-input-number v-model="createForm.fat" :min="0" :max="100" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="碳水(g)">
          <el-input-number v-model="createForm.carbohydrate" :min="0" :max="100" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="纤维(g)">
          <el-input-number v-model="createForm.fiber" :min="0" :max="100" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="钠(mg)">
          <el-input-number v-model="createForm.sodium" :min="0" :max="10000" :precision="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { createFood, deleteFood, getFoodCategories, getFoods } from '@/api/diet'

const userStore = useUserStore()
const currentUserId = ref(userStore.user?.id ?? null)

const foods = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const keyword = ref('')
const category = ref('')

const categories = ref([])

const detailVisible = ref(false)
const detailFood = ref(null)

const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref(null)
const createForm = ref({
  name: '',
  category: '主食',
  unit: '100g',
  calories: 100,
  protein: 0,
  fat: 0,
  carbohydrate: 0,
  fiber: 0,
  sodium: 0
})

const createRules = {
  name: [{ required: true, message: '请输入食物名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  calories: [{ required: true, message: '请填写热量', trigger: 'blur' }]
}

/** 分类可能是字符串数组，也可能是 {name, value} 对象数组 */
function normalizeCategories(raw) {
  if (!Array.isArray(raw)) return []
  const result = []
  raw.forEach((item) => {
    if (item === null || item === undefined) return
    if (typeof item === 'string' || typeof item === 'number') {
      result.push({ label: String(item), value: item })
      return
    }
    if (typeof item === 'object') {
      const value = item.value !== undefined ? item.value : item.name !== undefined ? item.name : item.category
      const label = item.label !== undefined ? item.label : item.name !== undefined ? item.name : String(value)
      if (value !== undefined) result.push({ label: String(label), value })
    }
  })
  return result
}

async function loadCategories() {
  try {
    const data = await getFoodCategories()
    categories.value = normalizeCategories(Array.isArray(data) ? data : data?.items)
  } catch (error) {
    categories.value = []
    ElMessage.warning(`分类加载失败：${error.message}`)
  }
}

async function loadFoods() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value) params.keyword = keyword.value
    if (category.value) params.category = category.value
    const data = await getFoods(params)
    foods.value = Array.isArray(data) ? data : data?.items || []
    total.value = Array.isArray(data) ? foods.value.length : Number(data?.total) || 0
  } catch (error) {
    foods.value = []
    total.value = 0
    ElMessage.error(`食物加载失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadFoods()
}

function resetFilter() {
  keyword.value = ''
  category.value = ''
  handleSearch()
}

function canDelete(row) {
  if (!row) return false
  if (row.is_common) return false
  if (!row.created_by) return true
  return Number(row.created_by) === Number(currentUserId.value)
}

function openDetail(row) {
  detailFood.value = row
  detailVisible.value = true
}

function openCreateDialog() {
  createForm.value = {
    name: '',
    category: '主食',
    unit: '100g',
    calories: 100,
    protein: 0,
    fat: 0,
    carbohydrate: 0,
    fiber: 0,
    sodium: 0
  }
  createVisible.value = true
}

async function handleCreate() {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch (error) {
    ElMessage.warning('请先补全必填项')
    return
  }
  creating.value = true
  try {
    await createFood({
      name: createForm.value.name,
      category: createForm.value.category,
      unit: createForm.value.unit || '100g',
      calories: Number(createForm.value.calories) || 0,
      protein: Number(createForm.value.protein) || 0,
      fat: Number(createForm.value.fat) || 0,
      carbohydrate: Number(createForm.value.carbohydrate) || 0,
      fiber: Number(createForm.value.fiber) || 0,
      sodium: Number(createForm.value.sodium) || 0,
      is_common: false
    })
    ElMessage.success('自定义食物已添加')
    createVisible.value = false
    page.value = 1
    await loadFoods()
  } catch (error) {
    ElMessage.error(`保存失败：${error.message}`)
  } finally {
    creating.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除自定义食物「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteFood(row.id)
    ElMessage.success('已删除')
    if (foods.value.length === 1 && page.value > 1) page.value -= 1
    await loadFoods()
  } catch (error) {
    ElMessage.error(`删除失败：${error.message}`)
  }
}

onMounted(() => {
  loadCategories()
  loadFoods()
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
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.total-tip {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-left: auto;
}
.panel {
  margin-bottom: 12px;
  background: var(--ft-card);
}
.food-name {
  font-weight: 500;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
