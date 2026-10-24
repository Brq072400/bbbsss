<script setup>
/**
 * MainLayout 主框架布局
 * 左侧菜单 + 顶栏（页面标题、消息通知红点、用户头像下拉、退出登录）
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterView, RouterLink } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import EmptyState from '@/components/EmptyState.vue'
import {
  deleteNotification,
  getNotifications,
  getUnreadCount,
  readAllNotifications,
  readNotification
} from '@/api/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 左侧菜单配置：path 为路由地址，icon 为 svg path 数据 */
const menus = [
  { path: '/home', label: '首页看板', icon: 'M3 11.5 12 4l9 7.5M5.5 10v10h13V10' },
  { path: '/plans', label: '我的计划', icon: 'M6 4h12v16H6zM9 8h6M9 12h6M9 16h4' },
  { path: '/templates', label: '模板库', icon: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z' },
  { path: '/courses', label: '课程中心', icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM10 9l5 3-5 3z' },
  { path: '/checkin', label: '每日签到', icon: 'M4 6h16v14H4zM8 3v4M16 3v4M4 10h16M9 15l2.2 2.2L15 13.6' },
  { path: '/profile', label: '个人中心', icon: 'M12 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM5 20c0-3.4 3-5.5 7-5.5s7 2.1 7 5.5' }
]

/** 侧边栏是否收起（窄屏体验更好） */
const collapsed = ref(false)
/** 当前高亮的菜单（详情页也要高亮父级菜单） */
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/plans')) return '/plans'
  if (path.startsWith('/templates')) return '/templates'
  if (path.startsWith('/courses')) return '/courses'
  if (path.startsWith('/checkin')) return '/checkin'
  if (path.startsWith('/profile')) return '/profile'
  return '/home'
})

/** 顶栏标题取路由 meta.title */
const pageTitle = computed(() => route.meta?.title || 'FitTrack')

// ---------------- 消息通知 ----------------
/** 未读条数（角标） */
const unread = ref(0)
/** 通知面板列表 */
const notices = ref([])
/** 通知列表加载状态 */
const noticeLoading = ref(false)
/** 通知面板是否为打开状态（打开时才轮询刷新） */
const noticeVisible = ref(false)

/** 通知类型对应文案与色调 */
const notifyTypeMap = {
  system: { label: '系统', cls: 'ft-chip--primary' },
  plan: { label: '计划', cls: 'ft-chip--success' },
  course: { label: '课程', cls: 'ft-chip--warning' },
  comment: { label: '评论', cls: 'ft-chip--danger' }
}

/** 拉取未读数量 */
async function loadUnread() {
  try {
    const data = await getUnreadCount()
    if (typeof data === 'number') unread.value = data
    else unread.value = Number(data?.unread ?? data?.count ?? 0) || 0
  } catch (error) {
    // 静默失败：角标不是关键路径
  }
}

/** 拉取最近通知（面板打开时调用） */
async function loadNotices() {
  noticeLoading.value = true
  try {
    const data = await getNotifications({ page: 1, page_size: 6 })
    // 兼容分页与数组两种返回形式
    notices.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    notices.value = []
  } finally {
    noticeLoading.value = false
  }
}

/** 打开通知面板时刷新一次列表与未读数 */
function handleNoticeVisibleChange(visible) {
  noticeVisible.value = visible
  if (visible) {
    loadNotices()
    loadUnread()
  }
}

/** 单条标记已读 */
async function handleReadNotice(item) {
  if (!item || item.is_read) return
  try {
    await readNotification(item.id)
    item.is_read = true
    unread.value = Math.max(0, unread.value - 1)
    ElMessage.success('已标记为已读')
  } catch (error) {
    // 错误提示已由拦截器统一处理
  }
}

/** 全部标记已读 */
async function handleReadAll() {
  if (!unread.value) {
    ElMessage.info('当前没有未读消息')
    return
  }
  try {
    await readAllNotifications()
    notices.value = notices.value.map((item) => ({ ...item, is_read: true }))
    unread.value = 0
    ElMessage.success('已全部标记为已读')
  } catch (error) {
    /* 已提示 */
  }
}

/** 删除一条通知 */
async function handleDeleteNotice(item) {
  try {
    await deleteNotification(item.id)
    notices.value = notices.value.filter((n) => n.id !== item.id)
    if (!item.is_read) unread.value = Math.max(0, unread.value - 1)
    ElMessage.success('已删除')
  } catch (error) {
    /* 已提示 */
  }
}

/** 通知时间友好显示（今天只显示时分） */
function noticeTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  const pad = (n) => String(n).padStart(2, '0')
  if (sameDay) return `${pad(date.getHours())}:${pad(date.getMinutes())}`
  return `${date.getMonth() + 1}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// ---------------- 用户操作 ----------------
/** 退出登录（二次确认后清空状态并回登录页） */
async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出当前账号吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch (error) {
    return // 用户点了取消
  }
  await userStore.logout()
  ElMessage.success('已退出登录')
  router.replace('/login')
}

/** 头像加载失败时降级成首字母 */
const avatarError = ref(false)

/** 用户展示名首字（无头像时用作占位） */
const avatarInitial = computed(() => (userStore.displayName || 'F').slice(0, 1).toUpperCase())

/** 头像地址变化后重置失败标记 */
watch(
  () => userStore.avatarUrl,
  () => {
    avatarError.value = false
  }
)

/** 下拉菜单点击：支持 jump 跳转与 logout 退出 */
function handleUserCommand(command) {
  if (command === 'logout') handleLogout()
  else if (command) router.push(command)
}

// ---------------- 生命周期 ----------------
/** 未读数轮询定时器 */
let unreadTimer = null

onMounted(async () => {
  // 首次进入拉取用户信息与未读数
  if (userStore.hasLogin && !userStore.user) {
    try {
      await userStore.fetchMe()
    } catch (error) {
      /* 401 已由拦截器处理 */
    }
  }
  loadUnread()
  // 每 60 秒刷新一次未读数，保证红点及时
  unreadTimer = window.setInterval(() => {
    if (!document.hidden) loadUnread()
  }, 60000)
})

onBeforeUnmount(() => {
  if (unreadTimer) window.clearInterval(unreadTimer)
  unreadTimer = null
})

/** 路由变化时刷新未读数（用户可能在别的操作里产生了通知） */
watch(
  () => route.fullPath,
  () => loadUnread()
)
</script>

<template>
  <div class="layout" :class="{ 'layout--collapsed': collapsed }">
    <!-- ================= 左侧菜单 ================= -->
    <aside class="layout__sidebar">
      <div class="brand">
        <div class="brand__logo">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M4 9v6M8 7v10M16 7v10M20 9v6M8 12h8" stroke-linecap="round" />
          </svg>
        </div>
        <transition name="brand-fade">
          <div v-if="!collapsed" class="brand__text">
            <strong>FitTrack</strong>
            <span>训练 · 计划 · 课程</span>
          </div>
        </transition>
      </div>

      <nav class="nav">
        <RouterLink
          v-for="item in menus"
          :key="item.path"
          :to="item.path"
          class="nav__item"
          :class="{ 'nav__item--active': activeMenu === item.path }"
          :title="collapsed ? item.label : ''"
        >
          <svg class="nav__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path :d="item.icon" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span v-if="!collapsed" class="nav__label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar__footer">
        <button class="collapse-btn" type="button" @click="collapsed = !collapsed">
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            :style="{ transform: collapsed ? 'rotate(180deg)' : 'none' }"
          >
            <path d="M15 5l-7 7 7 7" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span v-if="!collapsed">收起菜单</span>
        </button>
      </div>
    </aside>

    <!-- ================= 右侧主体 ================= -->
    <div class="layout__main">
      <header class="topbar">
        <div class="topbar__left">
          <h2 class="topbar__title">{{ pageTitle }}</h2>
          <span class="ft-chip ft-chip--primary">训练者 Lv.{{ userStore.level }}</span>
        </div>

        <div class="topbar__right">
          <!-- 签到快捷入口 -->
          <el-button class="topbar__checkin" size="small" @click="router.push('/checkin')">
            每日签到
          </el-button>

          <!-- 消息通知 -->
          <el-popover
            placement="bottom-end"
            :width="340"
            trigger="click"
            popper-class="notice-popper"
            @show="handleNoticeVisibleChange(true)"
            @hide="handleNoticeVisibleChange(false)"
          >
            <template #reference>
              <button class="icon-btn" type="button" title="消息通知">
                <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path
                    d="M18 15V10a6 6 0 10-12 0v5l-1.6 2.4h15.2L18 15z"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <path d="M10 20a2 2 0 004 0" stroke-linecap="round" />
                </svg>
                <span v-if="unread > 0" class="icon-btn__dot">{{ unread > 99 ? '99+' : unread }}</span>
              </button>
            </template>

            <div class="notice">
              <div class="notice__head">
                <span>消息通知</span>
                <div class="notice__head-actions">
                  <el-button link size="small" @click="loadNotices">刷新</el-button>
                  <el-button link size="small" @click="handleReadAll">全部已读</el-button>
                </div>
              </div>

              <div v-if="noticeLoading" class="ft-loading-text" style="padding: 26px 0">
                <el-icon class="is-loading"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a9 9 0 109 9" stroke-linecap="round" /></svg></el-icon>
                加载中…
              </div>

              <EmptyState
                v-else-if="!notices.length"
                size="sm"
                icon="🔔"
                description="暂无消息通知"
              />

              <ul v-else class="notice__list">
                <li
                  v-for="item in notices"
                  :key="item.id"
                  class="notice__item"
                  :class="{ 'notice__item--unread': !item.is_read }"
                >
                  <div class="notice__item-head">
                    <span class="ft-chip" :class="notifyTypeMap[item.notify_type]?.cls || ''">
                      {{ notifyTypeMap[item.notify_type]?.label || '通知' }}
                    </span>
                    <span class="notice__time">{{ noticeTime(item.created_at) }}</span>
                  </div>
                  <p class="notice__title">{{ item.title }}</p>
                  <p class="notice__content">{{ item.content }}</p>
                  <div class="notice__actions">
                    <el-button v-if="!item.is_read" link size="small" @click="handleReadNotice(item)">
                      标为已读
                    </el-button>
                    <el-button link size="small" type="danger" @click="handleDeleteNotice(item)">
                      删除
                    </el-button>
                  </div>
                </li>
              </ul>
            </div>
          </el-popover>

          <!-- 用户头像下拉 -->
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-chip">
              <el-avatar :size="32" :src="avatarError ? '' : userStore.avatarUrl" class="user-chip__avatar">
                {{ avatarInitial }}
              </el-avatar>
              <div class="user-chip__info">
                <span class="user-chip__name">{{ userStore.displayName }}</span>
                <span class="user-chip__points">{{ userStore.points }} 积分</span>
              </div>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="/profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="/checkin">每日签到</el-dropdown-item>
                <el-dropdown-item command="/plans">我的计划</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="layout__content">
        <RouterView v-slot="{ Component }">
          <transition name="ft-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  background:
    radial-gradient(900px 500px at 12% -10%, rgba(255, 90, 31, 0.1), transparent 60%),
    radial-gradient(700px 420px at 100% 0%, rgba(60, 110, 255, 0.06), transparent 55%),
    var(--ft-bg);
}

/* ---------------- 侧边栏 ---------------- */
.layout__sidebar {
  width: 214px;
  flex: 0 0 214px;
  background: var(--ft-sidebar);
  border-right: 1px solid var(--ft-border);
  display: flex;
  flex-direction: column;
  padding: 18px 12px;
  position: sticky;
  top: 0;
  height: 100vh;
  transition: width 0.22s ease, flex-basis 0.22s ease;
}

.layout--collapsed .layout__sidebar {
  width: 74px;
  flex: 0 0 74px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 18px;
  overflow: hidden;
}

.brand__logo {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--ft-primary), #ff9248);
  box-shadow: 0 6px 18px rgba(255, 90, 31, 0.35);
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  white-space: nowrap;
}

.brand__text strong {
  font-size: 15px;
  letter-spacing: 0.4px;
}

.brand__text span {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.brand-fade-enter-active,
.brand-fade-leave-active {
  transition: opacity 0.16s ease;
}

.brand-fade-enter-from,
.brand-fade-leave-to {
  opacity: 0;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  overflow-y: auto;
}

.nav__item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 12px;
  border-radius: 11px;
  color: var(--ft-text-sub);
  font-size: 14px;
  white-space: nowrap;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.nav__item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--ft-text);
}

.nav__item--active {
  background: var(--ft-primary-soft);
  color: var(--ft-primary);
  font-weight: 600;
}

.nav__item--active .nav__icon {
  filter: drop-shadow(0 0 6px rgba(255, 90, 31, 0.6));
}

.nav__icon {
  width: 19px;
  height: 19px;
  flex: 0 0 19px;
}

.sidebar__footer {
  padding-top: 12px;
  border-top: 1px solid var(--ft-border);
}

.collapse-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid var(--ft-border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--ft-text-dim);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.collapse-btn:hover {
  color: var(--ft-primary);
  border-color: rgba(255, 90, 31, 0.4);
}

/* ---------------- 主体 ---------------- */
.layout__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 62px;
  flex: 0 0 62px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--ft-border);
  background: rgba(15, 17, 21, 0.72);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 20;
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.topbar__title {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar__checkin {
  border-radius: 9px;
}

.icon-btn {
  position: relative;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.04);
  color: var(--ft-text-sub);
  cursor: pointer;
  transition: all 0.18s ease;
}

.icon-btn:hover {
  color: var(--ft-primary);
  border-color: rgba(255, 90, 31, 0.45);
}

.icon-btn__dot {
  position: absolute;
  top: -5px;
  right: -6px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 9px;
  background: var(--ft-danger);
  color: #fff;
  font-size: 10px;
  line-height: 17px;
  text-align: center;
  box-shadow: 0 0 0 2px var(--ft-bg);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 4px 10px 4px 4px;
  border-radius: 999px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: all 0.18s ease;
  color: var(--ft-text-sub);
}

.user-chip:hover {
  border-color: rgba(255, 90, 31, 0.45);
  color: var(--ft-text);
}

.user-chip__avatar {
  background: linear-gradient(135deg, var(--ft-primary), #ff9248);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}

.user-chip__info {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  max-width: 120px;
}

.user-chip__name {
  font-size: 13px;
  color: var(--ft-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-chip__points {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.layout__content {
  flex: 1;
  min-width: 0;
}

/* ---------------- 通知面板 ---------------- */
.notice__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--ft-border);
  font-size: 13px;
  font-weight: 600;
}

.notice__head-actions {
  display: flex;
  gap: 4px;
}

.notice__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
  margin-top: 10px;
}

.notice__item {
  padding: 10px 12px;
  border-radius: 11px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
}

.notice__item--unread {
  border-color: rgba(255, 90, 31, 0.35);
  background: var(--ft-primary-soft);
}

.notice__item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.notice__time {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.notice__title {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ft-text);
}

.notice__content {
  margin-top: 2px;
  font-size: 12px;
  color: var(--ft-text-dim);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notice__actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 6px;
}

/* ---------------- 路由过渡 ---------------- */
.ft-fade-enter-active,
.ft-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.ft-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.ft-fade-leave-to {
  opacity: 0;
}

/* ---------------- 响应式 ---------------- */
@media (max-width: 820px) {
  .layout__sidebar {
    width: 74px;
    flex: 0 0 74px;
  }

  .nav__label,
  .brand__text,
  .collapse-btn span {
    display: none;
  }

  .user-chip__info {
    display: none;
  }

  .topbar {
    padding: 0 14px;
  }

  .topbar__checkin {
    display: none;
  }
}
</style>
