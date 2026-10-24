<script setup>
/**
 * PageHeader 页面头部
 * 用于每个页面顶部的标题 + 副标题 + 右侧操作区
 * 用法：
 *   <PageHeader title="我的计划" subtitle="共 3 个">
 *     <template #actions><el-button>新建</el-button></template>
 *   </PageHeader>
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  /** 主标题 */
  title: { type: String, required: true },
  /** 副标题 / 描述 */
  subtitle: { type: String, default: '' },
  /** 返回地址，传了就显示返回按钮（例如 '/plans'） */
  backTo: { type: String, default: '' },
  /** 是否显示返回按钮（backTo 为空时也可强制显示，用浏览器后退） */
  showBack: { type: Boolean, default: false }
})

const router = useRouter()

/** 是否渲染返回按钮 */
const canBack = computed(() => props.showBack || Boolean(props.backTo))

/** 返回上一页：优先使用 backTo，否则走浏览器历史 */
function handleBack() {
  if (props.backTo) router.push(props.backTo)
  else router.back()
}
</script>

<template>
  <div class="page-header">
    <div class="page-header__main">
      <div class="page-header__title-row">
        <!-- 返回按钮 -->
        <button v-if="canBack" class="page-header__back" type="button" title="返回" @click="handleBack">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 5l-7 7 7 7" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <h1 class="page-header__title">{{ title }}</h1>
        <!-- 标题右侧标签位 -->
        <slot name="tag" />
      </div>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <!-- 右上角操作区 -->
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.page-header__main {
  min-width: 0;
}

.page-header__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-header__title {
  font-size: 22px;
  line-height: 1.3;
  letter-spacing: 0.2px;
}

.page-header__subtitle {
  margin-top: 6px;
  color: var(--ft-text-dim);
  font-size: 13px;
}

.page-header__back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.04);
  color: var(--ft-text-sub);
  cursor: pointer;
  transition: all 0.18s ease;
}

.page-header__back:hover {
  color: var(--ft-primary);
  border-color: rgba(255, 90, 31, 0.5);
  background: var(--ft-primary-soft);
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
