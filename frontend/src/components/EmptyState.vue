<script setup>
/**
 * EmptyState 空状态 / 错误状态占位
 * 列表为空、请求失败、无搜索结果时统一展示
 */
const props = defineProps({
  /** 说明文案 */
  description: { type: String, default: '暂无数据' },
  /** 顶部图标（emoji） */
  icon: { type: String, default: '📭' },
  /** 尺寸：sm 小号（嵌在卡片里） / md 中号（整页） */
  size: { type: String, default: 'md' },
  /** 是否展示为错误态（红色调） */
  error: { type: Boolean, default: false }
})
</script>

<template>
  <div class="empty-state" :class="[`empty-state--${size}`, { 'empty-state--error': error }]">
    <div class="empty-state__icon">{{ icon }}</div>
    <p class="empty-state__desc">{{ description }}</p>
    <!-- 操作按钮（如「去创建计划」「重试」） -->
    <div v-if="$slots.default" class="empty-state__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 46px 20px;
  gap: 10px;
}

.empty-state--sm {
  padding: 26px 12px;
}

.empty-state__icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed var(--ft-border-strong);
  color: var(--ft-text-sub);
  margin-bottom: 2px;
}

.empty-state--sm .empty-state__icon {
  width: 42px;
  height: 42px;
  font-size: 20px;
  border-radius: 14px;
}

.empty-state__desc {
  color: var(--ft-text-dim);
  font-size: 13px;
  max-width: 420px;
}

.empty-state--error .empty-state__icon {
  border-color: rgba(240, 75, 75, 0.45);
  background: rgba(240, 75, 75, 0.1);
}

.empty-state--error .empty-state__desc {
  color: #f87171;
}

.empty-state__actions {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 6px;
}
</style>
