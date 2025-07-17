<template>
  <div class="faces-page">
    <div class="page-header">
      <h2>人脸管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          注册人脸
        </el-button>
        <el-button @click="refreshFaces">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="stats-row">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card class="stat-card">
            <div class="stat-item">
              <div class="stat-icon primary">
                <el-icon><User /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ faces.length }}</div>
                <div class="stat-label">已注册人脸</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="stat-card">
            <div class="stat-item">
              <div class="stat-icon success">
                <el-icon><CircleCheck /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ activeFaces.length }}</div>
                <div class="stat-label">活跃用户</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="stat-card">
            <div class="stat-item">
              <div class="stat-icon info">
                <el-icon><Clock /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ todayRecognitions }}</div>
                <div class="stat-label">今日识别次数</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="用户名">
          <el-input v-model="filters.name" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="请选择" clearable>
            <el-option label="活跃" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchFaces">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 人脸列表 -->
    <el-card class="faces-card">
      <template #header>
        <span>注册用户列表</span>
      </template>

      <el-table :data="filteredFaces" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="头像" width="100">
          <template #default="{ row }">
            <el-avatar 
              :src="row.face_image_url" 
              :size="60"
              shape="square"
              fit="cover"
            >
              <el-icon><User /></el-icon>
            </el-avatar>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="用户名" min-width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              @change="toggleUserStatus(row)"
              active-text="活跃"
              inactive-text="禁用"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="last_recognized_at" label="最后识别" width="180">
          <template #default="{ row }">
            {{ row.last_recognized_at ? formatTime(row.last_recognized_at) : '从未识别' }}
          </template>
        </el-table-column>
        <el-table-column prop="recognition_count" label="识别次数" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewRecognitionHistory(row)">
              识别记录
            </el-button>
            <el-button size="small" type="warning" @click="editUser(row)">
              编辑
            </el-button>
            <el-button size="small" type="danger" @click="deleteUser(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加人脸对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="注册人脸"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="addForm" :rules="addRules" ref="addFormRef" label-width="100px">
        <el-form-item label="用户名" prop="name">
          <el-input v-model="addForm.name" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="人脸照片" prop="image">
          <div class="image-upload">
            <el-upload
              class="avatar-uploader"
              :action="uploadUrl"
              :show-file-list="false"
              :on-success="handleUploadSuccess"
              :on-error="handleUploadError"
              :before-upload="beforeUpload"
              accept="image/*"
            >
              <img v-if="addForm.imageUrl" :src="addForm.imageUrl" class="avatar" />
              <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
            </el-upload>
            <div class="upload-tips">
              <p>建议上传清晰的正面照片，文件大小不超过2MB</p>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="addForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选择性填写备注信息"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAddDialog = false">取消</el-button>
          <el-button type="primary" @click="submitAddForm" :loading="submitting">
            确认注册
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 编辑用户对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑用户"
      width="600px"
    >
      <el-form :model="editForm" :rules="editRules" ref="editFormRef" label-width="100px">
        <el-form-item label="用户名" prop="name">
          <el-input v-model="editForm.name" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="当前头像">
          <el-avatar 
            :src="editForm.face_image_url" 
            :size="80"
            shape="square"
          >
            <el-icon><User /></el-icon>
          </el-avatar>
        </el-form-item>
        <el-form-item label="更换头像">
          <el-upload
            class="avatar-uploader"
            :action="uploadUrl"
            :show-file-list="false"
            :on-success="handleEditUploadSuccess"
            :before-upload="beforeUpload"
            accept="image/*"
          >
            <el-button size="small">选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选择性填写备注信息"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showEditDialog = false">取消</el-button>
          <el-button type="primary" @click="submitEditForm" :loading="submitting">
            确认修改
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 识别记录对话框 -->
    <el-dialog
      v-model="showHistoryDialog"
      :title="`${selectedUser?.name || ''} 的识别记录`"
      width="800px"
    >
      <el-table :data="recognitionHistory" v-loading="historyLoading">
        <el-table-column prop="recognition_time" label="识别时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.recognition_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="{ row }">
            {{ (row.confidence * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="distance" label="相似度距离" width="120">
          <template #default="{ row }">
            {{ row.distance ? row.distance.toFixed(3) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="识别截图" width="120">
          <template #default="{ row }">
            <el-image
              v-if="row.screenshot_url"
              :src="row.screenshot_url"
              :preview-src-list="[row.screenshot_url]"
              fit="cover"
              style="width: 80px; height: 60px; border-radius: 4px;"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="检测位置" min-width="150">
          <template #default="{ row }">
            {{ formatLocation(row.location) }}
          </template>
        </el-table-column>
        <el-table-column prop="faces_detected_total" label="总人脸数" width="100">
          <template #default="{ row }">
            {{ row.faces_detected_total || '-' }}
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showHistoryDialog = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const faces = ref([])
const loading = ref(false)
const submitting = ref(false)
const historyLoading = ref(false)
const todayRecognitions = ref(0)

const showAddDialog = ref(false)
const showEditDialog = ref(false)
const showHistoryDialog = ref(false)

const selectedUser = ref(null)
const recognitionHistory = ref([])

const uploadUrl = 'http://localhost:8000/api/face/upload'

const filters = reactive({
  name: '',
  status: ''
})

const addForm = reactive({
  name: '',
  image: null,
  imageUrl: '',
  description: ''
})

const editForm = reactive({
  id: null,
  name: '',
  face_image_url: '',
  description: ''
})

const addFormRef = ref(null)
const editFormRef = ref(null)

const addRules = {
  name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度在 2 到 20 个字符', trigger: 'blur' }
  ]
}

const editRules = {
  name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度在 2 到 20 个字符', trigger: 'blur' }
  ]
}

const activeFaces = computed(() => faces.value.filter(face => face.is_active))

const filteredFaces = computed(() => {
  let filtered = faces.value
  
  if (filters.name) {
    filtered = filtered.filter(face => 
      face.name.toLowerCase().includes(filters.name.toLowerCase())
    )
  }
  
  if (filters.status) {
    const isActive = filters.status === 'active'
    filtered = filtered.filter(face => face.is_active === isActive)
  }
  
  return filtered
})

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

const formatLocation = (location) => {
  if (!location) return '-'
  return `(${location.left}, ${location.top}) - (${location.right}, ${location.bottom})`
}

const fetchFaces = async () => {
  loading.value = true
  try {
    const response = await axios.get('http://localhost:8000/api/face/users')
    faces.value = response.data.data || []
  } catch (error) {
    ElMessage.error('获取人脸列表失败')
  } finally {
    loading.value = false
  }
}

const fetchStatistics = async () => {
  try {
    const response = await axios.get('http://localhost:8000/api/face/statistics')
    todayRecognitions.value = response.data.today_recognitions || 0
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

const searchFaces = () => {
  // 本地过滤，已在computed中实现
}

const resetFilters = () => {
  filters.name = ''
  filters.status = ''
}

const refreshFaces = () => {
  fetchFaces()
  fetchStatistics()
}

const beforeUpload = (file) => {
  const isJPGOrPNG = file.type === 'image/jpeg' || file.type === 'image/png'
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isJPGOrPNG) {
    ElMessage.error('上传头像图片只能是 JPG/PNG 格式!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('上传头像图片大小不能超过 2MB!')
    return false
  }
  return true
}

const handleUploadSuccess = (response) => {
  // 兼容 ResponseModel 格式 { success, message, data: { url, file_path } }
  if (response && response.success) {
    // 确保图片URL指向后端服务器
    const imageUrl = response.data?.url || ''
    addForm.imageUrl = imageUrl.startsWith('http') ? imageUrl : `http://localhost:8000${imageUrl}`
    addForm.image = response.data?.file_path || ''
    ElMessage.success(response.message || '图片上传成功')
  } else {
    ElMessage.error(response?.message || '图片上传失败')
  }
}

const handleEditUploadSuccess = (response) => {
  if (response && response.success) {
    editForm.face_image_url = response.data?.url || ''
    editForm.image = response.data?.file_path || ''
    ElMessage.success(response.message || '图片上传成功')
  } else {
    ElMessage.error(response?.message || '图片上传失败')
  }
}

const handleUploadError = () => {
  ElMessage.error('图片上传失败')
}

const submitAddForm = async () => {
  try {
    await addFormRef.value.validate()
    
    if (!addForm.image) {
      ElMessage.error('请上传人脸照片')
      return
    }

    submitting.value = true
    
    const response = await axios.post('http://localhost:8000/api/face/register-by-path', {
      name: addForm.name,
      image_path: addForm.image,
      description: addForm.description
    })

    if (response.data.success) {
      ElMessage.success('人脸注册成功')
      showAddDialog.value = false
      resetAddForm()
      await fetchFaces()
    } else {
      ElMessage.error(response.data.message || '注册失败')
    }
  } catch (error) {
    ElMessage.error('注册失败')
  } finally {
    submitting.value = false
  }
}

const resetAddForm = () => {
  Object.assign(addForm, {
    name: '',
    image: null,
    imageUrl: '',
    description: ''
  })
  addFormRef.value?.resetFields()
}

const editUser = (user) => {
  Object.assign(editForm, {
    id: user.id,
    name: user.name,
    face_image_url: user.face_image_url,
    description: user.description || ''
  })
  showEditDialog.value = true
}

const submitEditForm = async () => {
  try {
    await editFormRef.value.validate()
    
    submitting.value = true
    
    const updateData = {
      name: editForm.name,
      description: editForm.description
    }
    
    if (editForm.image) {
      updateData.image_path = editForm.image
    }

    await axios.put(`http://localhost:8000/api/face/${editForm.id}`, updateData)
    
    ElMessage.success('用户信息更新成功')
    showEditDialog.value = false
    await fetchFaces()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

const toggleUserStatus = async (user) => {
  try {
    await axios.put(`http://localhost:8000/api/face/${user.id}/status`, {
      is_active: user.is_active
    })
    ElMessage.success(`用户已${user.is_active ? '启用' : '禁用'}`)
  } catch (error) {
    ElMessage.error('状态更新失败')
    user.is_active = !user.is_active // 回滚状态
  }
}

const deleteUser = async (user) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        type: 'warning'
      }
    )
    
    await axios.delete(`http://localhost:8000/api/face/${user.id}`)
    ElMessage.success('用户删除成功')
    await fetchFaces()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const viewRecognitionHistory = async (user) => {
  selectedUser.value = user
  showHistoryDialog.value = true
  historyLoading.value = true
  
  try {
    const response = await axios.get(`http://localhost:8000/api/face/${user.id}/recognition-history`)
    console.log('识别记录API返回:', response.data)
    
    if (response.data.success) {
      recognitionHistory.value = response.data.data.records || []
    } else {
      ElMessage.error(response.data.message || '获取识别记录失败')
      recognitionHistory.value = []
    }
  } catch (error) {
    console.error('获取识别记录失败:', error)
    ElMessage.error('获取识别记录失败')
    recognitionHistory.value = []
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  fetchFaces()
  fetchStatistics()
})
</script>

<style lang="scss" scoped>
.faces-page {
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    h2 {
      margin: 0;
      color: #333;
    }
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      .stat-item {
        display: flex;
        align-items: center;
        gap: 15px;

        .stat-icon {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-size: 18px;

          &.primary {
            background: #409EFF;
          }

          &.success {
            background: #67C23A;
          }

          &.info {
            background: #909399;
          }
        }

        .stat-content {
          .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #333;
          }

          .stat-label {
            font-size: 12px;
            color: #999;
          }
        }
      }
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .image-upload {
    .avatar-uploader {
      .avatar {
        width: 120px;
        height: 120px;
        display: block;
        border-radius: 4px;
      }
    }

    .upload-tips {
      margin-top: 10px;
      
      p {
        margin: 0;
        font-size: 12px;
        color: #999;
      }
    }
  }
}

:deep(.avatar-uploader .el-upload) {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: 0.2s;
  
  &:hover {
    border-color: #409EFF;
  }
}

:deep(.avatar-uploader-icon) {
  font-size: 28px;
  color: #8c939d;
  width: 120px;
  height: 120px;
  line-height: 120px;
  text-align: center;
}
</style> 