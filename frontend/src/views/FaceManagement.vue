<template>
  <div class="face-management">
    <div class="page-header">
      <h1>人脸管理</h1>
      <p>管理已注册的人脸信息，支持添加、查看和删除人脸数据</p>
    </div>

    <!-- 人脸上传区域 -->
    <el-card class="upload-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <h3>添加新人脸</h3>
        </div>
      </template>
      
      <el-form :model="uploadForm" ref="uploadFormRef" :rules="uploadRules" label-width="80px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="uploadForm.name" placeholder="请输入姓名" />
        </el-form-item>
        
        <el-form-item label="人脸照片" prop="file">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleFileChange"
            :before-remove="handleFileRemove"
            :limit="1"
            accept="image/*"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只能上传jpg/png文件，且不超过5MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="submitUpload" :loading="uploading">
            注册人脸
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 人脸列表区域 -->
    <el-card class="list-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <h3>已注册人脸 ({{ faceList.length }})</h3>
          <el-button type="primary" @click="loadFaceList" :loading="loading">
            刷新列表
          </el-button>
        </div>
      </template>
      
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="3" animated />
      </div>
      
      <div v-else-if="faceList.length === 0" class="empty-container">
        <el-empty description="暂无人脸数据" />
      </div>
      
      <div v-else class="face-grid">
        <el-card
          v-for="face in faceList"
          :key="face.id"
          class="face-item"
          shadow="hover"
        >
          <div class="face-avatar">
            <el-avatar :size="80" :src="getFaceImageUrl(face.face_image_path)" />
          </div>
          <div class="face-info">
            <h4>{{ face.name }}</h4>
            <p class="face-id">ID: {{ face.id }}</p>
            <p class="face-date">注册时间: {{ formatDate(face.created_at) }}</p>
          </div>
          <div class="face-actions">
            <el-popconfirm
              title="确定要删除这个人脸吗？"
              @confirm="deleteFace(face.id)"
            >
              <template #reference>
                <el-button type="danger" size="small" :loading="deleting === face.id">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'

// 响应式数据
const loading = ref(false)
const uploading = ref(false)
const deleting = ref(null)
const faceList = ref([])

const uploadForm = reactive({
  name: '',
  file: null
})

const uploadFormRef = ref()
const uploadRef = ref()

// 表单验证规则
const uploadRules = {
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 2, max: 20, message: '姓名长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  file: [
    { required: true, message: '请选择人脸照片', trigger: 'change' }
  ]
}

// 方法
const handleFileChange = (file) => {
  uploadForm.file = file.raw
}

const handleFileRemove = () => {
  uploadForm.file = null
}

const resetForm = () => {
  uploadFormRef.value?.resetFields()
  uploadRef.value?.clearFiles()
  uploadForm.file = null
}

const submitUpload = async () => {
  if (!uploadFormRef.value) return
  
  try {
    await uploadFormRef.value.validate()
    
    if (!uploadForm.file) {
      ElMessage.error('请选择人脸照片')
      return
    }
    
    uploading.value = true
    
    const formData = new FormData()
    formData.append('file', uploadForm.file)
    formData.append('name', uploadForm.name)
    
    const response = await axios.post('/api/face/upload', formData)
    
    if (response.data.success) {
      ElMessage.success('人脸注册成功！')
      resetForm()
      await loadFaceList()
    } else {
      ElMessage.error(response.data.message || '注册失败')
    }
    
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

const loadFaceList = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/face/list')
    if (response.data.success) {
      faceList.value = response.data.faces
    } else {
      ElMessage.error('获取人脸列表失败')
    }
  } catch (error) {
    console.error('获取人脸列表失败:', error)
    ElMessage.error('获取人脸列表失败')
  } finally {
    loading.value = false
  }
}

const deleteFace = async (faceId) => {
  deleting.value = faceId
  try {
    const response = await axios.delete(`/api/face/${faceId}`)
    if (response.data.success) {
      ElMessage.success('删除成功')
      await loadFaceList()
    } else {
      ElMessage.error(response.data.message || '删除失败')
    }
  } catch (error) {
    console.error('删除失败:', error)
    ElMessage.error('删除失败')
  } finally {
    deleting.value = null
  }
}

const getFaceImageUrl = (imagePath) => {
  if (!imagePath) return ''
  return `http://localhost:8000/static/${imagePath.replace('media/', '')}`
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  loadFaceList()
})
</script>

<style scoped>
.face-management {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 30px;
  text-align: center;
}

.page-header h1 {
  margin: 0;
  color: #2c3e50;
  font-size: 28px;
}

.page-header p {
  margin: 10px 0 0 0;
  color: #7f8c8d;
  font-size: 16px;
}

.upload-card, .list-card {
  margin-bottom: 30px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  color: #2c3e50;
}

.loading-container {
  padding: 20px;
}

.empty-container {
  padding: 40px;
  text-align: center;
}

.face-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.face-item {
  text-align: center;
  transition: transform 0.2s;
}

.face-item:hover {
  transform: translateY(-2px);
}

.face-avatar {
  margin-bottom: 15px;
}

.face-info h4 {
  margin: 0 0 8px 0;
  color: #2c3e50;
  font-size: 18px;
}

.face-id, .face-date {
  margin: 4px 0;
  color: #7f8c8d;
  font-size: 12px;
}

.face-actions {
  margin-top: 15px;
}

:deep(.el-upload-dragger) {
  width: 100%;
  height: 140px;
}

:deep(.el-upload__tip) {
  color: #909399;
  font-size: 12px;
  margin-top: 10px;
}
</style> 