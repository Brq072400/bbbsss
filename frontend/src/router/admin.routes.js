/**
 * 后台管理路由
 *
 * 使用方法：在主路由里合并
 *   import adminRoutes from '@/router/admin.routes'
 *   const routes = [ ...业务路由, ...adminRoutes ]
 *
 * 说明：
 * 1. 后台路由全部是**顶级路由**（不套 MainLayout），页脚/导航由各后台页面自带的顶栏负责；
 * 2. 未登录后台时统一由 beforeEnter 守卫跳到 /admin/login，并带上 redirect 便于登录后回跳；
 * 3. 管理员令牌与普通用户令牌分离，存放在 localStorage 的 fittrack_admin_token。
 */
import { hasAdminLogin } from '@/api/admin'

/** 后台登录守卫 */
function requireAdmin(to, from, next) {
  if (hasAdminLogin()) {
    next()
    return
  }
  next({ path: '/admin/login', query: { redirect: to.fullPath } })
}

/** 各后台页面的统一 meta（需要管理员身份） */
const adminMeta = (title) => ({ title, requiresAdmin: true, adminPage: true })

const adminRoutes = [
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/admin/AdminLogin.vue'),
    meta: { title: '管理员登录', adminPage: true, hideLayout: true }
  },
  {
    path: '/admin',
    redirect: '/admin/dashboard'
  },
  {
    path: '/admin/dashboard',
    name: 'AdminDashboard',
    component: () => import('@/views/admin/AdminDashboard.vue'),
    beforeEnter: requireAdmin,
    meta: adminMeta('数据看板')
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('@/views/admin/AdminUsers.vue'),
    beforeEnter: requireAdmin,
    meta: adminMeta('用户管理')
  },
  {
    path: '/admin/courses',
    name: 'AdminCourses',
    component: () => import('@/views/admin/AdminCourses.vue'),
    beforeEnter: requireAdmin,
    meta: adminMeta('课程管理')
  },
  {
    path: '/admin/comments',
    name: 'AdminComments',
    component: () => import('@/views/admin/AdminComments.vue'),
    beforeEnter: requireAdmin,
    meta: adminMeta('评论审核')
  },
  {
    path: '/admin/posts',
    name: 'AdminPosts',
    component: () => import('@/views/admin/AdminPosts.vue'),
    beforeEnter: requireAdmin,
    meta: adminMeta('动态管理')
  },
  {
    path: '/admin/realnames',
    name: 'AdminRealnames',
    component: () => import('@/views/admin/AdminRealnames.vue'),
    beforeEnter: requireAdmin,
    meta: adminMeta('实名审核')
  }
]

export default adminRoutes
