<script setup>
/**
 * Profile.vue 个人中心
 * 模块：基本资料编辑（含头像上传）、等级与积分规则、实名认证、修改密码、绑定手机号
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'
import {
  getLevel,
  getLevelRules,
  getRealName,
  resubmitRealName,
  submitRealName,
  updateProfile,
  uploadAvatar
} from '@/api/user'
import { changePassword, confirmPhoneBind, requestPhoneBind } from '@/api/auth'
import { resolveAsset } from '@/api/request'

const router = useRouter()
const userStore = useUserStore()

/** 当前激活的标签页 */
const activeTab = ref('basic')

// ---------------- 资料 ----------------
const profileFormRef = ref(null)
const profileLoading = ref(true)
const profileSaving = ref(false)
const avatarUploading = ref(false)
/** 文件选择框（隐藏，点击头像触发） */
const fileInputRef = ref(null)

/** 资料表单（与后端 ProfileUpdateRequest 字段一致） */
const profileForm = reactive({
  nickname: '',
  gender: 0,
  birthday: '',
  height: null,
  target_weight: null,
  signature: '',
  city: '',
  email: ''
})

/** 资料表单校验规则 */
const profileRules = {
  nickname: [{ max: 50, message: '昵称最多 50 个字符', trigger: 'blur' }],
  birthday: [
    {
      validator: (rule, value, callback) => {
        if (!value) return callback()
        const picked = new Date(value)
        if (Number.isNaN(picked.getTime())) return callback(new Error('生日格式不正确'))
        if (picked > new Date()) return callback(new Error('生日不能晚于今天'))
        callback()
      },
      trigger: 'change'
    }
  ],
  height: [{ type: 'number', min: 0, max: 300, message: '身高需在 0-300 cm 之间', trigger: 'blur' }],
  target_weight: [
    { type: 'number', min: 0, max: 500, message: '目标体重需在 0-500 kg 之间', trigger: 'blur' }
  ],
  signature: [{ max: 200, message: '个性签名最多 200 个字符', trigger: 'blur' }],
  city: [{ max: 50, message: '城市最多 50 个字符', trigger: 'blur' }],
  email: [
    {
      validator: (rule, value, callback) => {
        if (!value) return callback()
        if (!/^[\w.-]+@[\w-]+(\.[\w-]+)+$/.test(value.trim())) {
          return callback(new Error('邮箱格式不正确'))
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

/** 头像可访问地址 */
const avatarSrc = computed(() => userStore.avatarUrl)
/** 无头像时的首字母占位 */
const avatarInitial = computed(() => (userStore.displayName || 'F').slice(0, 1).toUpperCase())

/** 加载个人资料并回填表单 */
async function loadProfile() {
  profileLoading.value = true
  try {
    const data = await userStore.fetchProfile()
    if (data) {
      profileForm.nickname = data.nickname || ''
      profileForm.gender = Number(data.gender ?? 0)
      profileForm.birthday = data.birthday ? String(data.birthday).slice(0, 10) : ''
      profileForm.height = data.height ?? null
      profileForm.target_weight = data.target_weight ?? null
      profileForm.signature = data.signature || ''
      profileForm.city = data.city || ''
      profileForm.email = data.email || ''
    }
  } catch (error) {
    /* 错误已提示 */
  } finally {
    profileLoading.value = false
  }
}

/** 保存资料（PUT /api/users/profile） */
async function handleSaveProfile() {
  if (!profileFormRef.value) return
  try {
    await profileFormRef.value.validate()
  } catch (error) {
    return
  }
  profileSaving.value = true
  try {
    const payload = {
      nickname: profileForm.nickname.trim() || null,
      gender: Number(profileForm.gender ?? 0),
      birthday: profileForm.birthday || null,
      height: profileForm.height === '' ? null : profileForm.height,
      target_weight: profileForm.target_weight === '' ? null : profileForm.target_weight,
      signature: profileForm.signature.trim() || null,
      city: profileForm.city.trim() || null,
      email: profileForm.email.trim() || null
    }
    const data = await updateProfile(payload)
    // 后端可能返回更新后的资料，没有就用本地表单值兜底刷新
    if (data) userStore.setProfile(data)
    else await userStore.fetchProfile()
    ElMessage.success('资料已保存')
  } catch (error) {
    /* 错误已提示 */
  } finally {
    profileSaving.value = false
  }
}

/** 点击头像区域，打开文件选择 */
function triggerAvatarPick() {
  fileInputRef.value?.click()
}

/** 选择文件后立即上传头像 */
async function handleAvatarChange(event) {
  const file = event.target?.files?.[0]
  if (!file) return
  // 前端先做一次大小与类型校验（后端同样会校验）
  if (!/^image\//.test(file.type)) {
    ElMessage.warning('请选择图片文件（jpg / png / webp）')
    event.target.value = ''
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片不能超过 5MB')
    event.target.value = ''
    return
  }
  avatarUploading.value = true
  try {
    const data = await uploadAvatar(file)
    // 兼容返回 { url } / { avatar } / 直接字符串
    const url = typeof data === 'string' ? data : data?.avatar || data?.url || ''
    if (url) {
      userStore.setUser({ ...(userStore.user || {}), avatar: url })
      if (userStore.profile) userStore.profile.avatar = url
    }
    ElMessage.success('头像更新成功')
  } catch (error) {
    /* 错误已提示 */
  } finally {
    avatarUploading.value = false
    event.target.value = ''
  }
}

// ---------------- 等级 ----------------
const levelInfo = ref(null)
const levelRules = ref(null)
const levelLoading = ref(true)

/** 加载等级信息与等级规则 */
async function loadLevel() {
  levelLoading.value = true
  try {
    const [info, rules] = await Promise.all([getLevel(), getLevelRules()])
    levelInfo.value = info
    levelRules.value = rules
  } catch (error) {
    levelInfo.value = null
    levelRules.value = null
  } finally {
    levelLoading.value = false
  }
}

/** 等级进度百分比 */
const levelProgress = computed(() => {
  const info = levelInfo.value
  if (!info) return 0
  if (info.is_max_level) return 100
  if (typeof info.progress === 'number') return Math.min(100, Math.round(info.progress))
  const min = Number(info.level_min_points ?? 0)
  const next = Number(info.next_level_points ?? 0)
  if (next > min) return Math.min(100, Math.round(((info.points - min) / (next - min)) * 100))
  return 0
})

/** 等级规则列表（后端返回 rules 数组） */
const ruleList = computed(() => levelRules.value?.rules || [])

// ---------------- 实名认证 ----------------
const realNameLoading = ref(true)
const realNameSaving = ref(false)
const realNameFormRef = ref(null)
/** 实名状态数据 */
const realNameInfo = ref({ status: 'none', real_name: '', id_card: '', reject_reason: '' })

/** 实名认证表单 */
const realNameForm = reactive({
  real_name: '',
  id_card: ''
})

/** 实名状态文案与标签色 */
const realNameStatusMap = {
  none: { label: '未认证', cls: 'ft-chip' },
  pending: { label: '审核中', cls: 'ft-chip--warning' },
  approved: { label: '已认证', cls: 'ft-chip--success' },
  rejected: { label: '已驳回', cls: 'ft-chip--danger' }
}

/** 当前实名状态对应的展示信息 */
const realNameStatus = computed(
  () => realNameStatusMap[realNameInfo.value.status] || realNameStatusMap.none
)

/** 是否允许编辑实名表单（未认证或被驳回时可提交） */
const canSubmitRealName = computed(() =>
  ['none', 'rejected'].includes(realNameInfo.value.status)
)

/** 实名表单校验规则（身份证 15 或 18 位） */
const realNameRules = {
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
    { min: 2, max: 50, message: '姓名长度需在 2 到 50 个字符之间', trigger: 'blur' }
  ],
  id_card: [
    { required: true, message: '请输入身份证号', trigger: 'blur' },
    {
      pattern: /^\d{15}$|^\d{17}[\dXx]$/,
      message: '身份证号应为 15 位或 18 位（末位可为 X）',
      trigger: 'blur'
    }
  ]
}

/** 查询实名认证状态 */
async function loadRealName() {
  realNameLoading.value = true
  try {
    const data = await getRealName()
    realNameInfo.value = {
      status: data?.status || 'none',
      real_name: data?.real_name || '',
      id_card: data?.id_card || '',
      reject_reason: data?.reject_reason || ''
    }
    // 被驳回时把上次填写内容带到表单，方便修改后重新提交
    if (data?.real_name) realNameForm.real_name = data.real_name
  } catch (error) {
    realNameInfo.value = { status: 'none', real_name: '', id_card: '', reject_reason: '' }
  } finally {
    realNameLoading.value = false
  }
}

/** 提交实名认证（被驳回时走 resubmit 接口） */
async function handleSubmitRealName() {
  if (!realNameFormRef.value) return
  try {
    await realNameFormRef.value.validate()
  } catch (error) {
    return
  }
  realNameSaving.value = true
  try {
    const payload = {
      real_name: realNameForm.real_name.trim(),
      id_card: realNameForm.id_card.trim()
    }
    // 被驳回过的走重新提交接口
    if (realNameInfo.value.status === 'rejected') await resubmitRealName(payload)
    else await submitRealName(payload)

    ElMessage.success('实名认证已提交，请等待审核')
    realNameForm.id_card = ''
    await Promise.all([loadRealName(), loadProfile()])
  } catch (error) {
    /* 错误已提示 */
  } finally {
    realNameSaving.value = false
  }
}

// ---------------- 修改密码 ----------------
const passwordFormRef = ref(null)
const passwordSaving = ref(false)

/** 修改密码表单 */
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

/** 修改密码校验规则 */
const passwordRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '新密码至少 6 位', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value && value === passwordForm.old_password) {
          return callback(new Error('新密码不能与原密码相同'))
        }
        callback()
      },
      trigger: 'blur'
    }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.new_password) return callback(new Error('两次输入的密码不一致'))
        callback()
      },
      trigger: 'blur'
    }
  ]
}

/** 提交修改密码 */
async function handleChangePassword() {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
  } catch (error) {
    return
  }
  passwordSaving.value = true
  try {
    await changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })
    ElMessage.success('密码修改成功，请牢记新密码')
    passwordFormRef.value.resetFields()
  } catch (error) {
    /* 错误已提示 */
  } finally {
    passwordSaving.value = false
  }
}

// ---------------- 绑定手机号 ----------------
const phoneFormRef = ref(null)
const phoneSaving = ref(false)
const phoneCodeLoading = ref(false)
const phoneCountdown = ref(0)
let phoneTimer = null
/** 演示环境后端返回的验证码 */
const phoneDevCode = ref('')

/** 绑定手机号表单 */
const phoneForm = reactive({
  phone: '',
  code: ''
})

/** 绑定手机号校验规则 */
const phoneRules = {
  phone: [
    { required: true, message: '请输入要绑定的手机号', trigger: 'blur' },
    { pattern: /^\d{6,20}$/, message: '手机号应为 6-20 位数字', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 10, message: '验证码为 4-10 位', trigger: 'blur' }
  ]
}

/** 启动绑定手机号验证码倒计时 */
function startPhoneCountdown() {
  phoneCountdown.value = 60
  if (phoneTimer) window.clearInterval(phoneTimer)
  phoneTimer = window.setInterval(() => {
    phoneCountdown.value -= 1
    if (phoneCountdown.value <= 0) {
      window.clearInterval(phoneTimer)
      phoneTimer = null
    }
  }, 1000)
}

/** 请求绑定手机号验证码 */
async function handleSendPhoneCode() {
  const phone = phoneForm.phone.trim()
  if (!/^\d{6,20}$/.test(phone)) {
    ElMessage.warning('请先填写正确的手机号')
    return
  }
  phoneCodeLoading.value = true
  try {
    const data = await requestPhoneBind({ phone })
    phoneDevCode.value = typeof data === 'string' ? data : data?.code || ''
    ElMessage.success(
      phoneDevCode.value ? `验证码已发送，演示环境验证码：${phoneDevCode.value}` : '验证码已发送'
    )
    startPhoneCountdown()
  } catch (error) {
    /* 错误已提示 */
  } finally {
    phoneCodeLoading.value = false
  }
}

/** 确认绑定手机号 */
async function handleBindPhone() {
  if (!phoneFormRef.value) return
  try {
    await phoneFormRef.value.validate()
  } catch (error) {
    return
  }
  phoneSaving.value = true
  try {
    await confirmPhoneBind({ phone: phoneForm.phone.trim(), code: phoneForm.code.trim() })
    ElMessage.success('手机号绑定成功')
    phoneForm.code = ''
    await loadProfile()
  } catch (error) {
    /* 错误已提示 */
  } finally {
    phoneSaving.value = false
  }
}

// ---------------- 初始化 ----------------
onMounted(async () => {
  await Promise.all([loadProfile(), loadLevel(), loadRealName()])
})
</script>

<template>
  <div class="ft-page">
    <PageHeader title="个人中心" subtitle="管理你的账号资料、等级积分与账号安全">
      <template #actions>
        <el-button @click="router.push('/checkin')">查看签到日历</el-button>
      </template>
    </PageHeader>

    <div class="profile">
      <!-- ============ 左侧概览 ============ -->
      <aside class="profile__side">
        <!-- 用户卡片 -->
        <section class="ft-card user-card">
          <div v-if="profileLoading" class="ft-loading-text" style="padding: 30px 0">加载中…</div>
          <template v-else>
            <div class="user-card__avatar-wrap" :title="'点击更换头像'" @click="triggerAvatarPick">
              <el-avatar :size="84" :src="avatarSrc" class="user-card__avatar">
                {{ avatarInitial }}
              </el-avatar>
              <span class="user-card__avatar-mask">
                <span v-if="avatarUploading">上传中…</span>
                <span v-else>更换头像</span>
              </span>
            </div>
            <!-- 隐藏的文件输入：选择图片后立即上传 -->
            <input
              ref="fileInputRef"
              type="file"
              accept="image/*"
              class="user-card__file"
              @change="handleAvatarChange"
            />

            <h3 class="user-card__name">{{ userStore.displayName }}</h3>
            <p class="user-card__username">@{{ userStore.user?.username || '-' }}</p>

            <div class="user-card__chips">
              <span class="ft-chip ft-chip--primary">{{ levelInfo?.title || `Lv.${userStore.level}` }}</span>
              <span class="ft-chip">{{ userStore.points }} 积分</span>
              <span class="ft-chip" :class="realNameStatus.cls">{{ realNameStatus.label }}</span>
            </div>

            <ul class="user-card__meta">
              <li>
                <span>连续签到</span>
                <strong>{{ userStore.profile?.checkin_streak ?? 0 }} 天</strong>
              </li>
              <li>
                <span>累计签到</span>
                <strong>{{ userStore.profile?.checkin_total ?? 0 }} 天</strong>
              </li>
              <li>
                <span>本月签到</span>
                <strong>{{ userStore.profile?.checkin_month ?? 0 }} 天</strong>
              </li>
              <li>
                <span>手机号</span>
                <strong>{{ userStore.profile?.phone_masked || userStore.profile?.phone || '未绑定' }}</strong>
              </li>
            </ul>

            <p v-if="userStore.profile?.signature" class="user-card__signature">
              “{{ userStore.profile.signature }}”
            </p>
          </template>
        </section>

        <!-- 等级进度 -->
        <section class="ft-card">
          <h3 class="ft-section-title">等级进度</h3>
          <div v-if="levelLoading" class="ft-loading-text" style="padding: 20px 0">加载中…</div>
          <template v-else>
            <div class="level-row">
              <span class="level-row__title">{{ levelInfo?.title || '—' }}</span>
              <span class="level-row__points">{{ levelInfo?.points ?? userStore.points }} 积分</span>
            </div>
            <el-progress :percentage="levelProgress" :stroke-width="9" :show-text="false" color="#ff5a1f" />
            <p class="level-tip">
              <template v-if="levelInfo?.is_max_level">已达到最高等级 {{ levelInfo?.max_level }} 级</template>
              <template v-else-if="levelInfo?.next_level_points">
                距离下一等级还需
                {{ levelInfo?.points_to_next_level }} 积分（门槛 {{ levelInfo?.next_level_points }}）
              </template>
              <template v-else>暂无等级规则数据</template>
            </p>

            <!-- 等级规则表 -->
            <el-collapse v-if="ruleList.length" class="level-rules">
              <el-collapse-item title="查看等级规则" name="rules">
                <ul class="rule-list">
                  <li v-for="rule in ruleList" :key="rule.level">
                    <span class="rule-list__level">Lv.{{ rule.level }} {{ rule.title }}</span>
                    <span class="rule-list__range">
                      {{ rule.min_points }}<template v-if="rule.max_points"> - {{ rule.max_points }}</template>
                      <template v-else> 以上</template> 积分
                    </span>
                  </li>
                </ul>
                <p v-if="levelRules" class="rule-note">
                  签到基础积分 {{ levelRules.checkin_points }}，连续签到每天额外 +
                  {{ levelRules.checkin_streak_bonus }}（上限 {{ levelRules.checkin_streak_bonus_cap }}）
                </p>
              </el-collapse-item>
            </el-collapse>
          </template>
        </section>
      </aside>

      <!-- ============ 右侧表单区 ============ -->
      <section class="ft-card profile__main">
        <el-tabs v-model="activeTab">
          <!-- ---------- 基本资料 ---------- -->
          <el-tab-pane label="基本资料" name="basic">
            <div v-if="profileLoading" class="ft-loading-text">正在加载资料…</div>
            <el-form
              v-else
              ref="profileFormRef"
              :model="profileForm"
              :rules="profileRules"
              label-width="92px"
              class="profile-form"
            >
              <el-form-item label="昵称" prop="nickname">
                <el-input v-model="profileForm.nickname" placeholder="用于展示的名字" maxlength="50" show-word-limit />
              </el-form-item>

              <el-form-item label="性别" prop="gender">
                <el-radio-group v-model="profileForm.gender">
                  <el-radio :value="0">保密</el-radio>
                  <el-radio :value="1">男</el-radio>
                  <el-radio :value="2">女</el-radio>
                </el-radio-group>
              </el-form-item>

              <el-form-item label="生日" prop="birthday">
                <el-date-picker
                  v-model="profileForm.birthday"
                  type="date"
                  placeholder="选择生日"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                />
              </el-form-item>

              <div class="profile-form__grid">
                <el-form-item label="身高">
                  <el-input v-model.number="profileForm.height" type="number" placeholder="cm">
                    <template #append>cm</template>
                  </el-input>
                </el-form-item>
                <el-form-item label="目标体重">
                  <el-input v-model.number="profileForm.target_weight" type="number" placeholder="kg">
                    <template #append>kg</template>
                  </el-input>
                </el-form-item>
              </div>

              <el-form-item label="城市" prop="city">
                <el-input v-model="profileForm.city" placeholder="如：杭州" maxlength="50" />
              </el-form-item>

              <el-form-item label="邮箱" prop="email">
                <el-input v-model="profileForm.email" placeholder="用于接收通知与找回密码" maxlength="120" />
              </el-form-item>

              <el-form-item label="个性签名" prop="signature">
                <el-input
                  v-model="profileForm.signature"
                  type="textarea"
                  :rows="3"
                  maxlength="200"
                  show-word-limit
                  placeholder="一句话介绍你的训练目标"
                />
              </el-form-item>

              <el-form-item>
                <el-button type="primary" :loading="profileSaving" @click="handleSaveProfile">
                  保存修改
                </el-button>
                <el-button @click="loadProfile">重置</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- ---------- 实名认证 ---------- -->
          <el-tab-pane label="实名认证" name="realname">
            <div v-if="realNameLoading" class="ft-loading-text">正在查询认证状态…</div>
            <template v-else>
              <el-alert
                v-if="realNameInfo.status === 'approved'"
                type="success"
                :closable="false"
                show-icon
                title="实名认证已通过"
                :description="`姓名：${realNameInfo.real_name || '-'}；证件号：${realNameInfo.id_card || '-'}`"
                style="margin-bottom: 16px"
              />
              <el-alert
                v-else-if="realNameInfo.status === 'pending'"
                type="warning"
                :closable="false"
                show-icon
                title="认证资料审核中"
                description="我们正在审核你提交的实名信息，通常 1 个工作日内完成。"
                style="margin-bottom: 16px"
              />
              <el-alert
                v-else-if="realNameInfo.status === 'rejected'"
                type="error"
                :closable="false"
                show-icon
                title="认证被驳回"
                :description="realNameInfo.reject_reason || '请核对姓名与证件号后重新提交。'"
                style="margin-bottom: 16px"
              />
              <el-alert
                v-else
                type="info"
                :closable="false"
                show-icon
                title="尚未实名认证"
                description="实名后可解锁完整训练数据与社区功能，认证信息仅用于身份核验。"
                style="margin-bottom: 16px"
              />

              <el-form
                v-if="canSubmitRealName"
                ref="realNameFormRef"
                :model="realNameForm"
                :rules="realNameRules"
                label-width="92px"
              >
                <el-form-item label="真实姓名" prop="real_name">
                  <el-input v-model="realNameForm.real_name" placeholder="请输入身份证上的姓名" maxlength="50" />
                </el-form-item>
                <el-form-item label="身份证号" prop="id_card">
                  <el-input
                    v-model="realNameForm.id_card"
                    placeholder="15 位或 18 位身份证号"
                    maxlength="18"
                    show-word-limit
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="realNameSaving" @click="handleSubmitRealName">
                    {{ realNameInfo.status === 'rejected' ? '重新提交认证' : '提交认证' }}
                  </el-button>
                  <el-button @click="loadRealName">刷新状态</el-button>
                </el-form-item>
              </el-form>

              <EmptyState
                v-else
                size="sm"
                icon="🪪"
                :description="
                  realNameInfo.status === 'pending'
                    ? '资料审核中，暂时不能重复提交'
                    : '已通过实名认证，无需再次提交'
                "
              >
                <el-button size="small" @click="loadRealName">刷新状态</el-button>
              </EmptyState>
            </template>
          </el-tab-pane>

          <!-- ---------- 修改密码 ---------- -->
          <el-tab-pane label="修改密码" name="password">
            <el-form
              ref="passwordFormRef"
              :model="passwordForm"
              :rules="passwordRules"
              label-width="92px"
              style="max-width: 520px"
            >
              <el-form-item label="原密码" prop="old_password">
                <el-input
                  v-model="passwordForm.old_password"
                  type="password"
                  placeholder="请输入当前密码"
                  show-password
                />
              </el-form-item>
              <el-form-item label="新密码" prop="new_password">
                <el-input
                  v-model="passwordForm.new_password"
                  type="password"
                  placeholder="至少 6 位"
                  show-password
                />
              </el-form-item>
              <el-form-item label="确认密码" prop="confirm_password">
                <el-input
                  v-model="passwordForm.confirm_password"
                  type="password"
                  placeholder="请再次输入新密码"
                  show-password
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="passwordSaving" @click="handleChangePassword">
                  保存新密码
                </el-button>
              </el-form-item>
            </el-form>
            <p class="form-tip">建议使用字母 + 数字的组合，避免与其他网站使用相同的密码。</p>
          </el-tab-pane>

          <!-- ---------- 手机绑定 ---------- -->
          <el-tab-pane label="手机绑定" name="phone">
            <p class="form-tip" style="margin-bottom: 16px">
              当前绑定：<strong>{{ userStore.profile?.phone_masked || userStore.profile?.phone || '未绑定' }}</strong>
              ，绑定手机号可用于登录、找回密码与接收训练提醒。
            </p>

            <el-alert
              v-if="phoneDevCode"
              type="success"
              :closable="false"
              show-icon
              :title="`演示环境验证码：${phoneDevCode}`"
              style="margin-bottom: 16px"
            />

            <el-form
              ref="phoneFormRef"
              :model="phoneForm"
              :rules="phoneRules"
              label-width="92px"
              style="max-width: 560px"
            >
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="phoneForm.phone" placeholder="请输入要绑定的手机号" maxlength="20" />
              </el-form-item>
              <el-form-item label="验证码" prop="code">
                <div class="code-row">
                  <el-input v-model="phoneForm.code" placeholder="请输入验证码" maxlength="10" />
                  <el-button
                    :loading="phoneCodeLoading"
                    :disabled="phoneCountdown > 0"
                    class="code-row__btn"
                    @click="handleSendPhoneCode"
                  >
                    {{ phoneCountdown > 0 ? `${phoneCountdown}s 后重发` : '获取验证码' }}
                  </el-button>
                </div>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="phoneSaving" @click="handleBindPhone">
                  确认绑定
                </el-button>
                <el-button @click="loadProfile">刷新资料</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </section>
    </div>
  </div>
</template>

<style scoped>
.profile {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.profile__side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------------- 用户卡片 ---------------- */
.user-card {
  text-align: center;
}

.user-card__avatar-wrap {
  position: relative;
  width: 84px;
  height: 84px;
  margin: 4px auto 12px;
  border-radius: 50%;
  cursor: pointer;
  overflow: hidden;
}

.user-card__avatar {
  background: linear-gradient(135deg, var(--ft-primary), #ff9248);
  color: #fff;
  font-size: 30px;
  font-weight: 700;
}

.user-card__avatar-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
  background: rgba(0, 0, 0, 0.55);
  opacity: 0;
  transition: opacity 0.18s ease;
}

.user-card__avatar-wrap:hover .user-card__avatar-mask {
  opacity: 1;
}

.user-card__file {
  display: none;
}

.user-card__name {
  font-size: 17px;
}

.user-card__username {
  font-size: 12px;
  color: var(--ft-text-dim);
  margin-top: 2px;
}

.user-card__chips {
  display: flex;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.user-card__meta {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  text-align: left;
}

.user-card__meta li {
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border);
}

.user-card__meta span {
  display: block;
  font-size: 11px;
  color: var(--ft-text-dim);
}

.user-card__meta strong {
  font-size: 13px;
}

.user-card__signature {
  margin-top: 14px;
  font-size: 12px;
  color: var(--ft-text-dim);
  font-style: italic;
}

/* ---------------- 等级 ---------------- */
.level-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.level-row__title {
  font-size: 15px;
  font-weight: 600;
}

.level-row__points {
  font-size: 12px;
  color: var(--ft-primary-light);
}

.level-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ft-text-dim);
}

.level-rules {
  margin-top: 10px;
  border-top: 1px solid var(--ft-border);
  border-bottom: none;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rule-list li {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--ft-text-sub);
}

.rule-list__level {
  color: var(--ft-text);
}

.rule-list__range {
  color: var(--ft-text-dim);
}

.rule-note {
  margin-top: 10px;
  font-size: 12px;
  color: var(--ft-text-dim);
  line-height: 1.6;
}

/* ---------------- 表单 ---------------- */
.profile__main {
  min-height: 460px;
}

.profile-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-tip {
  font-size: 12px;
  color: var(--ft-text-dim);
  line-height: 1.7;
}

.code-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.code-row__btn {
  flex: 0 0 118px;
}

@media (max-width: 1000px) {
  .profile {
    grid-template-columns: 1fr;
  }

  .profile-form__grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
