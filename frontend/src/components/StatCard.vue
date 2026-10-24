<script setup>
/**
 * StatCard 统计卡片
 * 首页 / 详情页的指标展示：标题 + 主数值 + 单位 + 说明 + 图标
 */
import { computed } from 'vue'

const props = defineProps({
  /** 指标名称，例如「本周训练」 */
  label: { type: String, required: true },
  /** 主数值 */
  value: { type: [Number, String], default: 0 },
  /** 单位，例如「次」「天」「千卡」 */
  unit: { type: String, default: '' },
  /** 数值下方的补充说明 */
  hint: { type: String, default: '' },
  /** 左侧图标（emoji 或短字符） */
  icon: { type: String, default: '' },
  /** 主题色调：primary / success / warning / danger / info */
  tone: { type: String, default: 'primary' },
  /** 是否处于加载中（骨架微光效果） */
  loading: { type: Boolean, default: false },
  /** 是否可点击（显示手型 + hover 上浮） */
  clickable: { type: Boolean, default: false }
})

const emit = defineEmits(['click'])

/** 图标与数值的着色 class */
const toneClass = computed(() => `stat-card--${props.tone}`)

/** 数值为 0 时也正常展示，空值兜底为 0 */
const displayValue = computed(() => {
  const v = props.value
  if (v === null || v === undefined || v === '') return 0
  return v
})

/** 点击卡片（clickable 为 true 时向父组件冒泡） */
function handleClick() {
  if (props.clickable) emit('click')
}
</script>

<template>
  <div
    class="stat-card ft-card"
    :class="[toneClass, { 'stat-card--clickable': clickable, 'stat-card--loading': loading }]"
    @click="handleClick"
  >
    <div class="stat-card__head">
      <span class="stat-card__label">{{ label }}</span>
      <span v-if="icon" class="stat-card__icon">{{ icon }}</span>
    </div>

    <div class="stat-card__value">
      <span class="stat-card__number">{{ displayValue }}</span>
      <span v-if="unit" class="stat-card__unit">{{ unit }}</span>
    </div>

    <div v-if="hint" class="stat-card__hint">{{ hint }}</div>
    <!-- 允许插入进度条等自定义内容 -->
    <slot />
  </div>
</template>

<style scoped>
.stat-card {
  position: relative;
  overflow: hidden;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  --tone: var(--ft-primary);
}

.stat-card::after {
  /* 右上角光晕装饰 */
  content: '';
  position: absolute;
  top: -40px;
  right: -30px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--tone) 0%, transparent 70%);
  opacity: 0.16;
  pointer-events: none;
}

.stat-card--success {
  --tone: var(--ft-success);
}

.stat-card--warning {
  --tone: var(--ft-warning);
}

.stat-card--danger {
  --tone: var(--ft-danger);
}

.stat-card--info {
  --tone: #7c8aa5;
}

.stat-card--clickable {
  cursor: pointer;
}

.stat-card--clickable:hover {
  transform: translateY(-3px);
  border-color: var(--tone);
  box-shadow: var(--ft-shadow);
}

.stat-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.stat-card__label {
  color: var(--ft-text-sub);
  font-size: 13px;
}

.stat-card__icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  font-size: 15px;
  color: var(--tone);
  background: color-mix(in srgb, var(--tone) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--tone) 30%, transparent);
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 10px;
}

.stat-card__number {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: var(--ft-text);
  font-variant-numeric: tabular-nums;
}

.stat-card__unit {
  font-size: 13px;
  color: var(--ft-text-dim);
}

.stat-card__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

/* 加载态：数值区域轻微呼吸 */
.stat-card--loading .stat-card__number {
  color: transparent;
  border-radius: 6px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.06));
  background-size: 200% 100%;
  animation: stat-shimmer 1.2s ease-in-out infinite;
}

@keyframes stat-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
