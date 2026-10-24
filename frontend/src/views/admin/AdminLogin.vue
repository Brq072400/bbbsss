<template>
  <div class="admin-login">
    <div class="login-card">
      <div class="login-head">
        <div class="login-logo">🏋️</div>
        <h2 class="login-title">FitTrack 后台管理</h2>
        <p class="login-sub">仅限管理员账号登录</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="管理员账号" prop="username">
          <el-input
            v-model="form.username"
            size="large"
            placeholder="请输入管理员用户名"
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            placeholder="请输入密码"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-alert v-if="errorMsg" type="error" :closable="false" show-icon :title="errorMsg" class="login-error" />
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="handleLogin">
          登录后台
        </el-button>
      </el-form>

      <div class="login-foot">
        <el-button link @click="goHome">← 返回前台</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminLogin, hasAdminLogin, saveAdminAuth } from '@/api/admin'

const route = useRoute()
const router = useRouter()

const formRef = ref(null)
const loading = ref(false)
const errorMsg = ref('')

const form = ref({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入管理员账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (error) {
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await adminLogin({ username: form.value.username, password: form.value.password })
    const token = data?.token || data?.access_token || ''
    if (!token) throw new Error('登录响应中没有 token')
    saveAdminAuth(token, data?.admin || data?.user || null)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' && redirect ? redirect : '/admin/dashboard')
  } catch (error) {
    errorMsg.value = error.message || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}

function goHome() {
  router.push('/')
}

onMounted(() => {
  // 已经登录过就直接进看板
  if (hasAdminLogin()) router.replace('/admin/dashboard')
})
</script>

<style scoped>
.admin-login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 20% 10%, #241a16 0%, #0f1115 55%, #0b0d11 100%);
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 380px;
  padding: 30px 28px 22px;
  border-radius: var(--ft-radius-lg, 20px);
  background: var(--ft-card, #171b24);
  border: 1px solid var(--ft-border, rgba(255, 255, 255, 0.08));
  box-shadow: var(--ft-shadow, 0 10px 30px rgba(0, 0, 0, 0.38));
}
.login-head {
  text-align: center;
  margin-bottom: 20px;
}
.login-logo {
  font-size: 34px;
  line-height: 1;
}
.login-title {
  margin: 10px 0 0;
  font-size: 20px;
}
.login-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--ft-text-dim, #7b8497);
}
.login-error {
  margin-bottom: 12px;
}
.login-foot {
  margin-top: 16px;
  text-align: center;
}
</style>
