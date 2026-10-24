import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import adminRoutes from './admin.routes'

/**
 * 路由表（合并前台业务页面与后台管理页面）
 *
 * 前台：登录注册 / 首页 / 个人中心 / 签到 / 计划 / 课程 / 记录 / 动作库 / 统计 / 社区 / 饮食
 * 后台：/admin/*（由 admin.routes.js 提供，自带管理员登录守卫）
 */
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', guestOnly: true }
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '注册', guestOnly: true }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '首页看板' }
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'checkin',
        name: 'checkin',
        component: () => import('@/views/Checkin.vue'),
        meta: { title: '每日签到' }
      },
      {
        path: 'plans',
        name: 'plan-list',
        component: () => import('@/views/plans/PlanList.vue'),
        meta: { title: '我的计划' }
      },
      {
        path: 'plans/new',
        name: 'plan-create',
        component: () => import('@/views/plans/PlanEdit.vue'),
        meta: { title: '新建计划' }
      },
      {
        path: 'plans/:id',
        name: 'plan-detail',
        component: () => import('@/views/plans/PlanDetail.vue'),
        meta: { title: '计划详情' }
      },
      {
        path: 'plans/:id/edit',
        name: 'plan-edit',
        component: () => import('@/views/plans/PlanEdit.vue'),
        meta: { title: '编辑计划' }
      },
      {
        path: 'templates',
        name: 'template-library',
        component: () => import('@/views/plans/TemplateLibrary.vue'),
        meta: { title: '计划模板库' }
      },
      {
        path: 'courses',
        name: 'course-list',
        component: () => import('@/views/courses/CourseList.vue'),
        meta: { title: '课程中心' }
      },
      {
        path: 'courses/:id',
        name: 'course-detail',
        component: () => import('@/views/courses/CourseDetail.vue'),
        meta: { title: '课程详情' }
      },
      // ---------- 运动记录 ----------
      {
        path: 'records',
        name: 'record-list',
        component: () => import('@/views/records/RecordList.vue'),
        meta: { title: '运动记录' }
      },
      {
        path: 'records/create',
        name: 'record-create',
        component: () => import('@/views/records/RecordEdit.vue'),
        meta: { title: '新增记录' }
      },
      {
        path: 'records/:id',
        name: 'record-detail',
        component: () => import('@/views/records/RecordDetail.vue'),
        meta: { title: '记录详情' }
      },
      {
        path: 'records/:id/edit',
        name: 'record-edit',
        component: () => import('@/views/records/RecordEdit.vue'),
        meta: { title: '编辑记录' }
      },
      // ---------- 动作库 ----------
      {
        path: 'exercises',
        name: 'exercise-list',
        component: () => import('@/views/exercises/ExerciseList.vue'),
        meta: { title: '动作库' }
      },
      {
        path: 'exercises/:id',
        name: 'exercise-detail',
        component: () => import('@/views/exercises/ExerciseDetail.vue'),
        meta: { title: '动作详情' }
      },
      // ---------- 数据统计 ----------
      {
        path: 'stats',
        name: 'stats',
        component: () => import('@/views/stats/Stats.vue'),
        meta: { title: '数据统计' }
      },
      // ---------- 社区 ----------
      {
        path: 'community',
        name: 'community-feed',
        component: () => import('@/views/community/Feed.vue'),
        meta: { title: '健身社区' }
      },
      {
        path: 'community/posts/:id',
        name: 'community-post',
        component: () => import('@/views/community/PostDetail.vue'),
        meta: { title: '动态详情' }
      },
      {
        path: 'community/users/:id',
        name: 'community-user',
        component: () => import('@/views/community/UserProfile.vue'),
        meta: { title: '用户主页' }
      },
      // ---------- 饮食 ----------
      {
        path: 'diet',
        name: 'diet-diary',
        component: () => import('@/views/diet/DietDiary.vue'),
        meta: { title: '饮食日记' }
      },
      {
        path: 'diet/foods',
        name: 'diet-foods',
        component: () => import('@/views/diet/FoodLibrary.vue'),
        meta: { title: '食物库' }
      }
    ]
  },
  // 后台管理（独立布局 + 管理员守卫）
  ...adminRoutes,
  // 兜底：未匹配的地址回到首页
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/home'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 切换路由时回到顶部，保证详情页从头部开始阅读
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  }
})

/** 无需登录即可访问的路径 */
const WHITE_LIST = ['/login', '/register']

/**
 * 全局前置守卫
 * 1. /admin 前缀（后台管理）交给后台模块自己校验，这里直接放行
 * 2. 未登录访问受保护页面 → 跳登录页并记录回跳地址
 * 3. 已登录还访问登录/注册页 → 回到首页
 * 4. 已登录但没有用户信息（如刷新页面）→ 补拉一次 /auth/me
 */
router.beforeEach(async (to) => {
  const userStore = useUserStore()

  // 后台前缀例外：不做前台登录校验
  if (to.path.startsWith('/admin')) return true

  const logged = userStore.hasLogin

  if (!logged) {
    if (WHITE_LIST.includes(to.path)) return true
    const redirect = to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : {}
    return { path: '/login', query: redirect }
  }

  // 已登录无需再看登录/注册页
  if (WHITE_LIST.includes(to.path)) return { path: '/home' }

  // 刷新页面后 store 是空的，补拉当前用户信息（失败由响应拦截器统一处理 401）
  if (!userStore.user) {
    try {
      await userStore.fetchMe(true)
    } catch (error) {
      // 忽略异常：token 失效时会由 request.js 跳转登录页
    }
  }

  return true
})

/** 全局后置钩子：同步浏览器标题 */
router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} · FitTrack` : 'FitTrack · 健身训练'
})

export default router
