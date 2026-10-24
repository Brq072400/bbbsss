<script setup>
/**
 * Register.vue 注册页
 * 用户名 / 密码 / 昵称 / 手机号 / 邮箱 注册，带完整的表单校验
 */
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
/** 是否已勾选用户协议 */
const agreed = ref(false)

/** 注册表单数据 */
const form = reactive({
  username: '',
  nickname: '',
  phone: '',
  email: '',
  password: '',
  confirmPassword: ''
})

/**
 * 手机号自定义校验：选填，填了就必须是合法号码
 */
function validatePhone(rule, value, callback) {
  if (!value) return callback()
  if (!/^\d{6,20}$/.test(value.trim())) return callback(new Error('手机号应为 6-20 位数字'))
  callback()
}

/**
 * 邮箱自定义校验：选填，填了就必须符合邮箱格式
 */
function validateEmail(rule, value, callback) {
  if (!value) return callback()
  if (!/^[\w.-]+@[\w-]+(\.[\w-]+)+$/.test(value.trim())) return callback(new Error('邮箱格式不正确'))
  callback()
}

/**
 * 确认密码自定义校验：必须与密码一致
 */
function validateConfirm(rule, value, callback) {
  if (!value) return callback(new Error('请再次输入密码'))
  if (value !== form.password) return callback(new Error('两次输入的密码不一致'))
  callback()
}

/** 表单校验规则（与后端 RegisterRequest 的长度限制保持一致） */
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度需在 3 到 50 个字符之间', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9_]+$/,
      message: '用户名只能包含字母、数字与下划线',
      trigger: 'blur'
    }
  ],
  nickname: [{ max: 50, message: '昵称最多 50 个字符', trigger: 'blur' }],
  phone: [{ validator: validatePhone, trigger: 'blur' }],
  email: [{ validator: validateEmail, trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需在 6 到 64 位之间', trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirm, trigger: 'blur' }]
}

/**
 * 提交注册
 * 调用 POST /api/auth/register；后端若直接返回 token 则自动登录
 */
async function handleRegister() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (error) {
    return // 校验未通过
  }

  if (!agreed.value) {
    ElMessage.warning('请先阅读并同意用户协议')
    return
  }

  loading.value = true
  try {
    const payload = {
      username: form.username.trim(),
      password: form.password,
      nickname: form.nickname.trim() || undefined,
      phone: form.phone.trim() || undefined,
      email: form.email.trim() || undefined
    }
    const data = await userStore.register(payload)
    if (data?.token || data?.access_token) {
      ElMessage.success('注册成功，已自动登录')
      router.replace('/home')
    } else {
      ElMessage.success('注册成功，请使用新账号登录')
      router.replace('/login')
    }
  } catch (error) {
    // 错误提示已由 axios 拦截器统一处理
  } finally {
    loading.value = false
  }
}

/** 重置表单（清空已填写内容） */
function handleReset() {
  formRef.value?.resetFields()
  agreed.value = false
}
</script>

<template>
  <div class="register">
    <section class="register__side">
      <div class="register__brand">
        <div class="register__logo">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M4 9v6M8 7v10M16 7v10M20 9v6M8 12h8" stroke-linecap="round" />
          </svg>
        </div>
        <span>FitTrack</span>
      </div>
      <h1>开始你的<br />第一次系统训练</h1>
      <p>注册后即可创建训练计划、收藏课程、每日签到累积积分，逐步解锁等级。</p>

      <ul class="register__list">
        <li>✅ 计划模板一键套用，告别瞎练</li>
        <li>✅ 课程评分与评论，找到适合的强度</li>
        <li>✅ 签到日历记录坚持的每一天</li>
      </ul>

      <p class="register__login">
        已经有账号了？<RouterLink to="/login">返回登录</RouterLink>
      </p>
    </section>

    <section class="register__panel">
      <div class="register__card">
        <header class="register__head">
          <h2>创建账号</h2>
          <p>带 <span class="ft-primary">*</span> 为必填项，手机号与邮箱可稍后在个人中心补充</p>
        </header>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent="handleRegister"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="3-50 位字母、数字或下划线" clearable />
          </el-form-item>

          <div class="register__grid">
            <el-form-item label="昵称" prop="nickname">
              <el-input v-model="form.nickname" placeholder="展示名，可留空" clearable />
            </el-form-item>
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="form.phone" placeholder="选填，用于找回密码" clearable />
            </el-form-item>
          </div>

          <el-form-item label="邮箱" prop="email">
            <el-input v-model="form.email" placeholder="选填，用于接收通知" clearable />
          </el-form-item>

          <div class="register__grid">
            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="请再次输入密码"
                show-password
                @keyup.enter="handleRegister"
              />
            </el-form-item>
          </div>

          <el-checkbox v-model="agreed" class="register__agree">
            我已阅读并同意《用户协议》与《隐私政策》
          </el-checkbox>

          <div class="register__actions">
            <el-button size="large" @click="handleReset">重置</el-button>
            <el-button
              type="primary"
              size="large"
              class="register__submit"
              :loading="loading"
              native-type="submit"
            >
              {{ loading ? '注册中…' : '注册并登录' }}
            </el-button>
          </div>
        </el-form>
      </div>
    </section>
  </div>
</template>

<style scoped>
.register {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  background:
    radial-gradient(800px 520px at 90% 0%, rgba(255, 90, 31, 0.15), transparent 60%),
    var(--ft-bg);
}

.register__side {
  padding: 54px 52px;
  border-right: 1px solid var(--ft-border);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
}

.register__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 700;
}

.register__logo {
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

.register__side h1 {
  font-size: 32px;
  line-height: 1.3;
  margin-top: 14px;
  background: linear-gradient(120deg, #ffffff 20%, #ffb08a 90%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.register__side > p {
  color: var(--ft-text-sub);
  font-size: 14px;
  max-width: 400px;
}

.register__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
  color: var(--ft-text-sub);
  font-size: 13px;
}

.register__login {
  margin-top: 20px;
  font-size: 13px;
  color: var(--ft-text-dim);
}

.register__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}

.register__card {
  width: 100%;
  max-width: 520px;
  background: var(--ft-card);
  border: 1px solid var(--ft-border);
  border-radius: var(--ft-radius-lg);
  box-shadow: var(--ft-shadow);
  padding: 28px;
}

.register__head {
  margin-bottom: 18px;
}

.register__head h2 {
  font-size: 22px;
}

.register__head p {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

.register__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.register__agree {
  margin: 2px 0 18px;
  font-size: 13px;
}

.register__actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.register__submit {
  min-width: 150px;
}

@media (max-width: 980px) {
  .register {
    grid-template-columns: 1fr;
  }

  .register__side {
    display: none;
  }

  .register__grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
