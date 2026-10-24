import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import { getProfile } from '@/api/user'
import { clearToken, getToken, resolveAsset, setToken } from '@/api/request'

/**
 * 用户状态管理（Pinia）
 * 职责：token 持久化、登录/注册/退出、当前用户信息、个人资料（含等级与签到概况）
 */
export const useUserStore = defineStore('user', () => {
  /** 访问令牌（初始化时从 localStorage 读取，刷新页面不掉线） */
  const token = ref(getToken() || '')
  /** 当前登录用户（来自登录接口 / GET /api/auth/me） */
  const user = ref(null)
  /** 完整个人资料（来自 GET /api/users/profile，含等级、签到统计） */
  const profile = ref(null)
  /** 登录/拉取资料中的 loading 标记 */
  const loading = ref(false)

  /** 是否已登录 */
  const hasLogin = computed(() => Boolean(token.value))

  /** 展示名：昵称 > 用户名 > 兜底 */
  const displayName = computed(() => {
    const info = user.value || profile.value
    return info?.display_name || info?.nickname || info?.username || '训练者'
  })

  /** 头像可访问地址（后端可能返回相对路径） */
  const avatarUrl = computed(() => resolveAsset((user.value || profile.value)?.avatar || ''))

  /** 积分与等级 */
  const points = computed(() => (user.value || profile.value)?.points ?? 0)
  const level = computed(() => (user.value || profile.value)?.level ?? 1)

  /** 更新 token 并同步到 localStorage */
  function applyToken(value) {
    token.value = value || ''
    if (token.value) setToken(token.value)
    else clearToken()
  }

  /** 设置当前用户信息（资料更新后也可复用） */
  function setUser(info) {
    user.value = info || null
  }

  /** 设置完整资料（等级/签到概况），并顺带同步用户基本信息 */
  function setProfile(info) {
    profile.value = info || null
    if (info) user.value = { ...(user.value || {}), ...info }
  }

  /**
   * 登录
   * @param {{account: string, password: string}} payload 账号（用户名/手机号）+ 密码
   * @returns {Promise<object>} 登录返回的数据
   */
  async function login(payload) {
    loading.value = true
    try {
      const data = await authApi.login(payload)
      // 兼容 token / access_token 两种字段命名
      applyToken(data?.token || data?.access_token || '')
      user.value = data?.user || null
      if (!user.value) await fetchMe()
      return data
    } finally {
      loading.value = false
    }
  }

  /**
   * 注册（注册成功后如返回 token 则直接登录）
   * @param {{username: string, password: string, nickname?: string, phone?: string, email?: string}} payload
   */
  async function register(payload) {
    loading.value = true
    try {
      const data = await authApi.register(payload)
      const nextToken = data?.token || data?.access_token || ''
      if (nextToken) {
        applyToken(nextToken)
        user.value = data?.user || null
        if (!user.value) await fetchMe()
      }
      return data
    } finally {
      loading.value = false
    }
  }

  /**
   * 拉取当前登录用户信息
   * @param {boolean} force 为 true 时即使已有用户信息也重新请求
   */
  async function fetchMe(force = false) {
    if (!token.value) return null
    if (user.value && !force) return user.value
    const data = await authApi.getMe()
    // 有的实现直接返回 user 对象，有的包一层 { user: {...} }
    user.value = data?.user || data || null
    return user.value
  }

  /** 拉取完整个人资料（含等级、连续签到等） */
  async function fetchProfile() {
    if (!token.value) return null
    const data = await getProfile()
    setProfile(data)
    return data
  }

  /** 退出登录：先通知后端作废 token，无论成功与否都清空本地状态 */
  async function logout() {
    try {
      if (token.value) await authApi.logout()
    } catch (error) {
      // 后端不可用时也要允许本地退出，这里忽略异常
    } finally {
      reset()
    }
  }

  /** 清空所有登录状态 */
  function reset() {
    applyToken('')
    user.value = null
    profile.value = null
    loading.value = false
  }

  return {
    token,
    user,
    profile,
    loading,
    hasLogin,
    displayName,
    avatarUrl,
    points,
    level,
    login,
    register,
    fetchMe,
    fetchProfile,
    logout,
    reset,
    setUser,
    setProfile,
    applyToken
  }
})
