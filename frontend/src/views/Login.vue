<script setup>
/**
 * Login.vue 登录页
 * 左品牌宣传 + 右登录表单；支持「忘记密码」验证码重置流程
 */
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { confirmPasswordReset, requestPasswordReset } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ---------------- 登录表单 ----------------
const loginFormRef = ref(null)
const loginLoading = ref(false)
/** 登录表单数据：account 支持用户名或手机号 */
const loginForm = reactive({
  account: '',
  password: ''
})

/** 登录校验规则 */
const loginRules = {
  account: [
    { required: true, message: '请输入用户名或手机号', trigger: 'blur' },
    { min: 3, max: 50, message: '长度需在 3 到 50 个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码至少 6 位', trigger: 'blur' }
  ]
}

/** 登录成功后的回跳地址（来自路由 query，非法值兜底首页） */
const redirectPath = computed(() => {
  const target = route.query.redirect
  return typeof target === 'string' && target.startsWith('/') ? target : '/home'
})

/**
 * 提交登录
 * 调用 POST /api/auth/login，成功后写入 token 并跳转
 */
async function handleLogin() {
  if (!loginFormRef.value) return
  try {
    await loginFormRef.value.validate()
  } catch (error) {
    return // 校验未通过
  }

  loginLoading.value = true
  try {
    await userStore.login({ account: loginForm.account.trim(), password: loginForm.password })
    ElMessage.success(`欢迎回来，${userStore.displayName}`)
    router.replace(redirectPath.value)
  } catch (error) {
    // 具体错误信息已在 axios 拦截器里提示
  } finally {
    loginLoading.value = false
  }
}

// ---------------- 忘记密码 ----------------
const resetVisible = ref(false)
const resetFormRef = ref(null)
const resetLoading = ref(false)
const codeLoading = ref(false)
/** 验证码倒计时剩余秒数 */
const countdown = ref(0)
/** 后端在开发环境把验证码返回给前端，这里展示出来方便演示 */
const devCode = ref('')
let countdownTimer = null

/** 重置密码表单 */
const resetForm = reactive({
  target: '',
  code: '',
  newPassword: '',
  confirmPassword: ''
})

/** 重置密码校验规则（确认密码用自定义校验保证与密码一致） */
const resetRules = {
  target: [
    { required: true, message: '请输入注册时使用的手机号或邮箱', trigger: 'blur' },
    { min: 4, max: 120, message: '长度需在 4 到 120 个字符之间', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 10, message: '验证码为 4-10 位', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码至少 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      // 自定义校验：两次输入必须一致
      validator: (rule, value, callback) => {
        if (value !== resetForm.newPassword) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

/** 判断输入的是邮箱还是手机号，决定请求字段 */
function buildTargetPayload() {
  const target = resetForm.target.trim()
  const isEmail = target.includes('@')
  return isEmail ? { email: target } : { phone: target }
}

/** 打开重置密码弹窗 */
function openResetDialog() {
  resetVisible.value = true
  devCode.value = ''
  resetForm.code = ''
}

/** 启动 60 秒验证码倒计时 */
function startCountdown() {
  countdown.value = 60
  if (countdownTimer) window.clearInterval(countdownTimer)
  countdownTimer = window.setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      window.clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

/** 请求重置密码验证码 */
async function handleSendResetCode() {
  const target = resetForm.target.trim()
  if (!target) {
    ElMessage.warning('请先填写手机号或邮箱')
    return
  }
  codeLoading.value = true
  try {
    const data = await requestPasswordReset(buildTargetPayload())
    // 兼容 { code, target, expires_in } 或直接返回验证码字符串
    devCode.value = typeof data === 'string' ? data : data?.code || ''
    ElMessage.success(
      devCode.value ? `验证码已发送，演示环境验证码：${devCode.value}` : '验证码已发送，请查收手机/邮箱'
    )
    startCountdown()
  } catch (error) {
    /* 错误已提示 */
  } finally {
    codeLoading.value = false
  }
}

/** 提交重置密码 */
async function handleResetPassword() {
  if (!resetFormRef.value) return
  try {
    await resetFormRef.value.validate()
  } catch (error) {
    return
  }
  resetLoading.value = true
  try {
    await confirmPasswordReset({
      ...buildTargetPayload(),
      code: resetForm.code.trim(),
      new_password: resetForm.newPassword
    })
    ElMessage.success('密码重置成功，请用新密码登录')
    resetVisible.value = false
    loginForm.account = resetForm.target
    loginForm.password = ''
    resetForm.target = ''
    resetForm.code = ''
    resetForm.newPassword = ''
    resetForm.confirmPassword = ''
  } catch (error) {
    /* 错误已提示 */
  } finally {
    resetLoading.value = false
  }
}

/** 弹窗关闭时清理倒计时 */
function handleResetClosed() {
  if (countdownTimer) {
    window.clearInterval(countdownTimer)
    countdownTimer = null
  }
  countdown.value = 0
}

onBeforeUnmount(() => {
  if (countdownTimer) window.clearInterval(countdownTimer)
})

/** 遮罩上的装饰数据（纯展示，不走接口） */
const highlights = [
  { icon: '🏋️', title: '自建训练计划', desc: '按周安排动作、组次与组间休息' },
  { icon: '🎬', title: '专业课程库', desc: '分级课程搭配教练讲解与评分' },
  { icon: '🔥', title: '连续签到成长', desc: '每日签到累积积分，等级自动升级' }
]
</script>

<template>
  <div class="auth">
    <!-- 左侧品牌区 -->
    <section class="auth__hero">
      <div class="auth__brand">
        <div class="auth__logo">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M4 9v6M8 7v10M16 7v10M20 9v6M8 12h8" stroke-linecap="round" />
          </svg>
        </div>
        <span>FitTrack</span>
      </div>

      <h1 class="auth__hero-title">训练有据可依<br />进步看得见</h1>
      <p class="auth__hero-desc">
        从零基础到进阶，FitTrack 用计划、课程与数据陪你练下去。
      </p>

      <ul class="auth__highlights">
        <li v-for="item in highlights" :key="item.title">
          <span class="auth__highlight-icon">{{ item.icon }}</span>
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.desc }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- 右侧登录卡片 -->
    <section class="auth__panel">
      <div class="auth__card">
        <header class="auth__card-head">
          <h2>登录</h2>
          <p>还没有账号？<RouterLink to="/register">立即注册</RouterLink></p>
        </header>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          label-position="top"
          size="large"
          @submit.prevent="handleLogin"
        >
          <el-form-item label="账号" prop="account">
            <el-input
              v-model="loginForm.account"
              placeholder="请输入用户名或手机号"
              autocomplete="username"
              clearable
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <div class="auth__form-extra">
            <el-checkbox disabled>记住账号（由浏览器保存登录状态）</el-checkbox>
            <el-button link type="primary" @click="openResetDialog">忘记密码？</el-button>
          </div>

          <el-button
            type="primary"
            class="auth__submit"
            size="large"
            :loading="loginLoading"
            native-type="submit"
          >
            {{ loginLoading ? '登录中…' : '登录' }}
          </el-button>
        </el-form>

        <p class="auth__tip">
          登录即表示同意 FitTrack 的用户协议与隐私政策。忘记密码可通过注册手机号 / 邮箱重置。
        </p>
      </div>
    </section>

    <!-- 重置密码弹窗 -->
    <el-dialog
      v-model="resetVisible"
      title="重置登录密码"
      width="440px"
      :close-on-click-modal="false"
      @closed="handleResetClosed"
    >
      <el-alert
        v-if="devCode"
        type="success"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        :title="`演示环境验证码：${devCode}`"
        description="正式环境该验证码会通过短信或邮件下发，不会直接返回给前端。"
      />

      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="注册手机号 / 邮箱" prop="target">
          <el-input v-model="resetForm.target" placeholder="请输入注册时使用的手机号或邮箱" clearable />
        </el-form-item>

        <el-form-item label="验证码" prop="code">
          <div class="auth__code-row">
            <el-input v-model="resetForm.code" placeholder="请输入验证码" maxlength="10" />
            <el-button
              :loading="codeLoading"
              :disabled="countdown > 0"
              class="auth__code-btn"
              @click="handleSendResetCode"
            >
              {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="resetForm.newPassword" type="password" placeholder="至少 6 位" show-password />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="resetForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetLoading" @click="handleResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.auth {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background:
    radial-gradient(800px 500px at 8% 0%, rgba(255, 90, 31, 0.16), transparent 60%),
    radial-gradient(700px 500px at 90% 100%, rgba(60, 110, 255, 0.1), transparent 55%),
    var(--ft-bg);
}

/* ---------------- 左侧 ---------------- */
.auth__hero {
  padding: 54px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  border-right: 1px solid var(--ft-border);
}

.auth__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.auth__logo {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--ft-primary), #ff9248);
  box-shadow: 0 8px 22px rgba(255, 90, 31, 0.4);
}

.auth__hero-title {
  font-size: 38px;
  line-height: 1.25;
  margin-top: 12px;
  background: linear-gradient(120deg, #ffffff 20%, #ffb08a 90%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.auth__hero-desc {
  color: var(--ft-text-sub);
  font-size: 14px;
  max-width: 430px;
}

.auth__highlights {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 10px;
}

.auth__highlights li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: var(--ft-radius);
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.03);
}

.auth__highlight-icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--ft-primary-soft);
  font-size: 16px;
}

.auth__highlights strong {
  font-size: 14px;
}

.auth__highlights p {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 2px;
}

/* ---------------- 右侧表单 ---------------- */
.auth__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}

.auth__card {
  width: 100%;
  max-width: 400px;
  background: var(--ft-card);
  border: 1px solid var(--ft-border);
  border-radius: var(--ft-radius-lg);
  box-shadow: var(--ft-shadow);
  padding: 30px 28px;
}

.auth__card-head {
  margin-bottom: 20px;
}

.auth__card-head h2 {
  font-size: 22px;
}

.auth__card-head p {
  margin-top: 6px;
  font-size: 13px;
  color: var(--ft-text-dim);
}

.auth__form-extra {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -4px 0 16px;
}

.auth__submit {
  width: 100%;
  height: 44px;
  font-size: 15px;
  letter-spacing: 1px;
}

.auth__tip {
  margin-top: 16px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ft-text-dim);
}

.auth__code-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.auth__code-btn {
  flex: 0 0 118px;
}

/* ---------------- 响应式 ---------------- */
@media (max-width: 960px) {
  .auth {
    grid-template-columns: 1fr;
  }

  .auth__hero {
    display: none;
  }
}
</style>
