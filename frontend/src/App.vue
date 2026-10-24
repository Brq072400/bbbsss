<script setup>
/**
 * 应用根组件
 * 只负责渲染路由出口，布局由 MainLayout 承担。
 * 使用 <script setup> + 顶层 await 之外的最简写法，保证首屏渲染稳定。
 */
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView v-slot="{ Component, route }">
    <!-- 页面切换时带一点淡入过渡，避免生硬跳变 -->
    <transition name="ft-route" mode="out-in">
      <component :is="Component" :key="route.path" />
    </transition>
  </RouterView>
</template>

<style>
/* 路由切换过渡 */
.ft-route-enter-active,
.ft-route-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.ft-route-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.ft-route-leave-to {
  opacity: 0;
}
</style>
