<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>家庭视频监控系统</h1>
        <p>管理员登录</p>
      </div>

      <div class="login-tabs">
        <div 
          class="tab-item" 
          :class="{ active: activeTab === 'login' }"
          @click="activeTab = 'login'"
        >
          登录
        </div>
        <div 
          class="tab-item" 
          :class="{ active: activeTab === 'register' }"
          @click="activeTab = 'register'"
        >
          注册
        </div>
      </div>

      <!-- 登录表单 -->
      <div v-if="activeTab === 'login'" class="form-container">
        <el-form 
          ref="loginFormRef"
          :model="loginForm" 
          :rules="loginRules"
          label-width="0"
          size="large"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              prefix-icon="User"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>
        </el-form>

        <!-- 滑块验证 -->
        <SlideVerify 
          ref="loginSlideRef"
          @verify-success="handleLoginSlideSuccess"
          @verify-fail="handleSlideFail"
        />

        <el-button 
          type="primary" 
          size="large" 
          class="login-btn"
          :loading="loginLoading"
          :disabled="!isLoginSlideVerified"
          @click="handleLogin"
        >
          登录
        </el-button>
      </div>

      <!-- 注册表单 -->
      <div v-if="activeTab === 'register'" class="form-container">
        <el-form 
          ref="registerFormRef"
          :model="registerForm" 
          :rules="registerRules"
          label-width="0"
          size="large"
        >
          <el-form-item prop="username">
            <el-input
              v-model="registerForm.username"
              placeholder="请输入用户名"
              prefix-icon="User"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="registerForm.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="registerForm.confirmPassword"
              type="password"
              placeholder="请确认密码"
              prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>
        </el-form>

        <!-- 滑块验证 -->
        <SlideVerify 
          ref="registerSlideRef"
          @verify-success="handleRegisterSlideSuccess"
          @verify-fail="handleSlideFail"
        />

        <el-button 
          type="primary" 
          size="large" 
          class="login-btn"
          :loading="registerLoading"
          :disabled="!isRegisterSlideVerified"
          @click="handleRegister"
        >
          注册
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SlideVerify from '../components/SlideVerify.vue'

const router = useRouter()

// 表单引用
const loginFormRef = ref()
const registerFormRef = ref()
const loginSlideRef = ref()
const registerSlideRef = ref()

// 状态管理
const activeTab = ref('login')
const loginLoading = ref(false)
const registerLoading = ref(false)
const isLoginSlideVerified = ref(false)
const isRegisterSlideVerified = ref(false)

// 登录表单
const loginForm = reactive({
  username: '',
  password: ''
})

// 注册表单
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

// 登录表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度在 3 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 100, message: '密码长度在 6 到 100 个字符', trigger: 'blur' }
  ]
}

// 注册表单验证规则
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入密码不一致'))
  } else {
    callback()
  }
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度在 3 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 100, message: '密码长度在 6 到 100 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 滑块验证成功处理
const handleLoginSlideSuccess = () => {
  isLoginSlideVerified.value = true
}

const handleRegisterSlideSuccess = () => {
  isRegisterSlideVerified.value = true
}

const handleSlideFail = () => {
  ElMessage.warning('请完成滑块验证')
}

// 登录处理
const handleLogin = async () => {
  if (!isLoginSlideVerified.value) {
    ElMessage.warning('请先完成滑块验证')
    return
  }

  try {
    await loginFormRef.value.validate()
  } catch {
    return
  }

  loginLoading.value = true

  try {
    const response = await fetch('/api/auth/admin/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(loginForm)
    })

    const result = await response.json()

    if (result.success) {
      // 保存token到localStorage
      localStorage.setItem('admin_token', result.data.token.access_token)
      localStorage.setItem('admin_info', JSON.stringify(result.data.admin))
      
      ElMessage.success('登录成功')
      router.push('/live')
    } else {
      ElMessage.error(result.message || '登录失败')
      // 重置滑块验证
      loginSlideRef.value.reset()
      isLoginSlideVerified.value = false
    }
  } catch (error) {
    console.error('登录请求失败:', error)
    ElMessage.error('网络错误，请稍后重试')
    // 重置滑块验证
    loginSlideRef.value.reset()
    isLoginSlideVerified.value = false
  } finally {
    loginLoading.value = false
  }
}

// 注册处理
const handleRegister = async () => {
  if (!isRegisterSlideVerified.value) {
    ElMessage.warning('请先完成滑块验证')
    return
  }

  try {
    await registerFormRef.value.validate()
  } catch {
    return
  }

  registerLoading.value = true

  try {
    const response = await fetch('/api/auth/admin/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: registerForm.username,
        password: registerForm.password
      })
    })

    const result = await response.json()

    if (result.success) {
      ElMessage.success('注册成功，请登录')
      // 切换到登录标签
      activeTab.value = 'login'
      // 重置注册表单
      registerFormRef.value.resetFields()
      // 重置滑块
      registerSlideRef.value.reset()
      isRegisterSlideVerified.value = false
    } else {
      ElMessage.error(result.message || '注册失败')
      // 重置滑块验证
      registerSlideRef.value.reset()
      isRegisterSlideVerified.value = false
    }
  } catch (error) {
    console.error('注册请求失败:', error)
    ElMessage.error('网络错误，请稍后重试')
    // 重置滑块验证
    registerSlideRef.value.reset()
    isRegisterSlideVerified.value = false
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  font-size: 24px;
  color: #303133;
  margin-bottom: 8px;
  font-weight: 600;
}

.login-header p {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.login-tabs {
  display: flex;
  margin-bottom: 30px;
  border-bottom: 1px solid #e4e7ed;
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 12px 0;
  cursor: pointer;
  color: #909399;
  font-size: 16px;
  border-bottom: 2px solid transparent;
  transition: all 0.3s ease;
}

.tab-item.active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.tab-item:hover {
  color: #409eff;
}

.form-container {
  margin-bottom: 20px;
}

.login-btn {
  width: 100%;
  height: 45px;
  font-size: 16px;
  border-radius: 6px;
  margin-top: 20px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-input__wrapper) {
  border-radius: 6px;
}
</style> 