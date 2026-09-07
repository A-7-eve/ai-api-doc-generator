<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '../api'

const router = useRouter()

const isRegister = ref(false)
const form = ref({ username: '', password: '', confirmPassword: '' })
const submitting = ref(false)

const title = computed(() => (isRegister.value ? '注册新账号' : '用户登录'))

async function handleSubmit() {
  const { username, password, confirmPassword } = form.value
  if (!username || !password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (isRegister.value) {
    if (username.length < 2) {
      ElMessage.warning('用户名至少 2 位')
      return
    }
    if (password.length < 6) {
      ElMessage.warning('密码至少 6 位')
      return
    }
    if (password !== confirmPassword) {
      ElMessage.warning('两次输入的密码不一致')
      return
    }
  }

  submitting.value = true
  try {
    const data = isRegister.value
      ? await register(username, password)
      : await login(username, password)
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    ElMessage.success(`欢迎，${data.user.username}`)
    // 登录成功后进入工作台
    router.push('/workspace')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

function toggleMode() {
  isRegister.value = !isRegister.value
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-title">
        <el-icon size="28" color="#409eff"><Document /></el-icon>
        <span>AI辅助接口文档自动生成系统</span>
      </div>
      <div class="login-subtitle">{{ title }}</div>

      <el-form @submit.prevent="handleSubmit" class="login-form">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item v-if="isRegister">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ isRegister ? '注 册' : '登 录' }}
        </el-button>
      </el-form>

      <div class="login-footer">
        <span>{{ isRegister ? '已有账号？' : '没有账号？' }}</span>
        <el-link type="primary" @click="toggleMode">
          {{ isRegister ? '去登录' : '去注册' }}
        </el-link>
      </div>
      <div class="login-hint">默认管理员：admin / admin123</div>
    </div>
  </div>
</template>

<script>
// 图标需要以变量方式绑定 prefix-icon
import { User, Lock } from '@element-plus/icons-vue'
export default {
  setup() {
    return { User, Lock }
  },
}
</script>

<style scoped>
.login-wrapper {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f1fd 0%, #f5f7fa 100%);
}

.login-card {
  width: 400px;
  padding: 40px 36px 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

.login-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.login-subtitle {
  text-align: center;
  margin: 12px 0 24px;
  color: #909399;
  font-size: 14px;
}

.login-btn {
  width: 100%;
}

.login-footer {
  text-align: center;
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}

.login-hint {
  text-align: center;
  margin-top: 16px;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
