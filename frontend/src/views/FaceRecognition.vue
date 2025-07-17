<template>
  <div class="face-recognition">
    <!-- 头部控制区 -->
    <div class="recognition-header">
      <h1>人脸识别</h1>
      <div class="control-section">
        <el-button
          v-if="cameraStatus === 'stopped'"
          type="success"
          size="large"
          @click="startCamera"
          :loading="controlLoading"
        >
          <el-icon><VideoPlay /></el-icon>
          开启摄像头
        </el-button>
        <el-button
          v-else
          type="danger"
          size="large"
          @click="stopCamera"
          :loading="controlLoading"
        >
          <el-icon><VideoPause /></el-icon>
          关闭摄像头
        </el-button>
        
        <el-tag
          :type="cameraStatus === 'running' ? 'success' : 'info'"
          size="large"
          class="status-tag"
        >
          {{ getStatusText() }}
        </el-tag>
      </div>
    </div>

    <!-- 主识别区域 -->
    <div class="recognition-main">
      <el-card class="video-card" :body-style="{ padding: 0 }">
        <div class="video-container">
          <!-- Canvas用于绘制识别框 -->
          <canvas 
            ref="videoCanvas"
            class="video-canvas"
          ></canvas>
          
          <!-- 隐藏的视频流图片 -->
          <img 
            v-if="cameraStatus === 'running'"
            :src="videoStreamUrl" 
            ref="videoStream"
            alt="视频流"
            class="video-stream"
            style="display: block; max-width: 100%; max-height: 480px; margin: 0 auto;"
            @load="drawVideoFrame"
            @error="handleVideoError"
          />
          
          <!-- 状态覆盖层 -->
          <div class="status-overlay">
            <div v-if="cameraStatus === 'stopped'" class="camera-stopped">
              <el-icon class="camera-icon"><VideoCamera /></el-icon>
              <p>摄像头未开启</p>
              <p>点击"开启摄像头"开始人脸识别</p>
            </div>
            
            <div v-else-if="!videoLoaded" class="loading-status">
              <el-icon class="loading-icon"><Loading /></el-icon>
              <p>正在连接摄像头...</p>
            </div>
          </div>
          
          <!-- 识别结果显示 -->
          <div class="recognition-results" v-if="cameraStatus === 'running'">
            <div class="face-count">
              <el-tag v-if="totalFaces > 0" type="primary" size="large">
                检测到 {{ totalFaces }} 个人脸
              </el-tag>
            </div>
            
            <!-- 识别成功的用户信息 -->
            <div class="recognized-users" v-if="recognizedUsers.length > 0">
              <div 
                v-for="user in recognizedUsers" 
                :key="user.user_id"
                class="user-info success-feedback"
              >
                <div class="user-card">
                  <el-icon class="success-icon"><CircleCheck /></el-icon>
                  <div class="user-details">
                    <h3>{{ user.name }}</h3>
                    <p>置信度: {{ (user.confidence * 100).toFixed(1) }}%</p>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 陌生人提示 -->
            <div class="strangers-alert" v-if="strangersCount > 0">
              <el-alert
                title="检测到陌生人"
                :description="`发现 ${strangersCount} 个未注册的人脸`"
                type="warning"
                :closable="false"
                show-icon
              />
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 底部信息栏 -->
    <div class="info-bar">
      <div class="stats">
        <span>已注册用户: {{ registeredFacesCount }}</span>
        <span class="separator">|</span>
        <span>识别到用户: {{ recognizedUsers.length }}</span>
        <span class="separator">|</span>
        <span>陌生人: {{ strangersCount }}</span>
      </div>
      <div class="connection-status">
        <el-icon :class="wsConnected ? 'connected' : 'disconnected'">
          <Connection />
        </el-icon>
        <span>{{ wsConnected ? '已连接' : '连接断开' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, VideoPause, VideoCamera, Loading, CircleCheck, Connection } from '@element-plus/icons-vue'
import axios from 'axios'

// 响应式数据
const videoCanvas = ref(null)
const videoStream = ref(null)
const videoStreamUrl = ref('http://localhost:8000/api/video/stream')

const cameraStatus = ref('stopped')
const controlLoading = ref(false)
const videoLoaded = ref(false)
const wsConnected = ref(false)

const detectedFaces = ref([])
const registeredFacesCount = ref(0)

// WebSocket连接
let ws = null
let animationId = null

// 计算属性
const recognizedUsers = computed(() => {
  return detectedFaces.value
    .filter(face => !face.is_stranger && face.match)
    .map(face => ({
      user_id: face.match.user_id,
      name: face.match.name,
      confidence: face.match.confidence
    }))
})

const strangersCount = computed(() => {
  return detectedFaces.value.filter(face => face.is_stranger).length
})

const totalFaces = computed(() => {
  return detectedFaces.value.length
})

// 方法
const getStatusText = () => {
  if (cameraStatus.value === 'running') {
    return videoLoaded.value ? '识别中' : '连接中'
  }
  return '已停止'
}

const drawVideoFrame = () => {
  if (!videoCanvas.value || !videoStream.value) return
  
  const canvas = videoCanvas.value
  const video = videoStream.value
  const ctx = canvas.getContext('2d')
  
  try {
    // 检查图片是否加载完成
    if (!video.complete || video.naturalWidth === 0) {
      return
    }
    
    // 设置画布尺寸匹配图片尺寸
    if (canvas.width !== video.naturalWidth || canvas.height !== video.naturalHeight) {
      canvas.width = video.naturalWidth || 640
      canvas.height = video.naturalHeight || 480
    }
    
    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // 绘制视频帧
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    
    // 绘制人脸框
    drawFaceBoxes(ctx)
    
    // 更新加载状态
    videoLoaded.value = true
    
  } catch (error) {
    console.error('绘制视频帧时发生错误:', error)
  }
}

const drawFaceBoxes = (ctx) => {
  if (detectedFaces.value.length === 0) return
  
  detectedFaces.value.forEach(face => {
    const { left, top, right, bottom } = face.location
    
    // 绘制红色人脸框
    ctx.strokeStyle = '#ff4444'
    ctx.lineWidth = 3
    ctx.strokeRect(left, top, right - left, bottom - top)
    
    // 绘制标签背景
    const labelText = face.is_stranger ? '陌生人' : (face.match?.name || '未知')
    ctx.font = 'bold 14px Arial'
    const textWidth = ctx.measureText(labelText).width
    const textHeight = 25
    
    // 确保标签在画布范围内
    const labelTop = Math.max(top - textHeight, 0)
    const labelLeft = Math.max(left, 0)
    const labelRight = Math.min(labelLeft + textWidth + 20, ctx.canvas.width)
    
    ctx.fillStyle = 'rgba(255, 68, 68, 0.9)'
    ctx.fillRect(labelLeft, labelTop, labelRight - labelLeft, textHeight)
    
    // 绘制标签文字
    ctx.fillStyle = '#ffffff'
    ctx.fillText(labelText, labelLeft + 10, labelTop + 16)
    
    // 如果是识别用户，显示置信度
    if (!face.is_stranger && face.match) {
      const confidence = `${(face.match.confidence * 100).toFixed(1)}%`
      ctx.font = '12px Arial'
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.fillText(confidence, labelLeft + 10, labelTop + textHeight + 15)
    }
  })
}

const handleVideoError = () => {
  videoLoaded.value = false
  ElMessage.error('视频流连接失败')
}

const startCamera = async () => {
  controlLoading.value = true
  try {
    const response = await axios.post('/api/video/camera/start')
    if (response.data.success) {
      ElMessage.success('摄像头已启动')
      cameraStatus.value = 'running'
      videoStreamUrl.value = 'http://localhost:8000/api/stream/mjpeg?rtmp_url=rtmp://121.41.28.35:9090/live/obs_stream'
    } else {
      ElMessage.error(response.data.message || '启动失败')
    }
  } catch (error) {
    console.error('启动摄像头失败:', error)
    ElMessage.error('启动失败，请检查摄像头连接')
  } finally {
    controlLoading.value = false
  }
}

const stopCamera = async () => {
  controlLoading.value = true
  try {
    const response = await axios.post('/api/video/camera/stop')
    if (response.data.success) {
      ElMessage.success('摄像头已停止')
      cameraStatus.value = 'stopped'
      videoStreamUrl.value = ''
    } else {
      ElMessage.error(response.data.message || '停止失败')
    }
  } catch (error) {
    console.error('停止摄像头失败:', error)
    ElMessage.error('停止失败')
  } finally {
    controlLoading.value = false
  }
}

const checkCameraStatus = async () => {
  try {
    const response = await axios.get('/api/video/camera/status')
    cameraStatus.value = response.data.status
    if (cameraStatus.value === 'running') {
      videoStreamUrl.value = 'http://localhost:8000/api/stream/mjpeg?rtmp_url=rtmp://121.41.28.35:9090/live/obs_stream'
    } else {
      videoStreamUrl.value = ''
    }
  } catch (error) {
    console.error('获取摄像头状态失败:', error)
    ElMessage.error('获取摄像头状态失败')
  }
}

const loadFaceStatistics = async () => {
  try {
    const response = await axios.get('/api/face/statistics')
    if (response.data.success) {
      registeredFacesCount.value = response.data.data.known_faces_count || 0
    }
  } catch (error) {
    console.error('获取人脸统计失败:', error)
  }
}

const initWebSocket = () => {
  const wsUrl = `ws://localhost:8000/ws`
  ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    wsConnected.value = true
    console.log('WebSocket连接已建立')
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'face_detection') {
      // 处理实时人脸检测数据
      const faceData = data.data
      detectedFaces.value = faceData.faces || []
      
      // 不再需要手动触发重绘，requestAnimationFrame循环会自动处理
    } else if (data.type === 'event_alert') {
      // 处理事件告警
      console.log('收到事件告警:', data.data)
    }
  }
  
  ws.onclose = () => {
    wsConnected.value = false
    console.log('WebSocket连接已断开，尝试重连...')
    setTimeout(initWebSocket, 3000)
  }
  
  ws.onerror = (error) => {
    wsConnected.value = false
    console.error('WebSocket错误:', error)
  }
}

onMounted(async () => {
  await checkCameraStatus()
  await loadFaceStatistics()
  initWebSocket()
  
  // 使用requestAnimationFrame连续渲染，参考实时监控页面的成功模式
  const frameUpdate = () => {
    if (cameraStatus.value === 'running') {
      drawVideoFrame()
    }
    animationId = requestAnimationFrame(frameUpdate)
  }
  frameUpdate()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<style lang="scss" scoped>
.face-recognition {
  padding: 20px;
  height: calc(100vh - 80px);
  background: #f5f5f5;
  
  .recognition-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    h1 {
      margin: 0;
      color: #333;
      font-size: 2rem;
      font-weight: 600;
    }
    
    .control-section {
      display: flex;
      align-items: center;
      gap: 15px;
      
      .status-tag {
        font-size: 14px;
        padding: 8px 16px;
      }
    }
  }
  
  .recognition-main {
    .video-card {
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      border: 1px solid #e0e0e0;
      
      .video-container {
        position: relative;
        width: 100%;
        height: 600px;
        background: #000;
        
        .video-canvas {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
        }
        
        .status-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(0,0,0,0.7);
          color: white;
          
          .camera-stopped, .loading-status {
            text-align: center;
            
            .camera-icon, .loading-icon {
              font-size: 64px;
              margin-bottom: 16px;
              opacity: 0.7;
            }
            
            .loading-icon {
              animation: spin 2s linear infinite;
            }
            
            p {
              margin: 8px 0;
              font-size: 18px;
              
              &:first-of-type {
                font-size: 24px;
                font-weight: bold;
              }
            }
          }
        }
        
        .recognition-results {
          position: absolute;
          top: 20px;
          right: 20px;
          display: flex;
          flex-direction: column;
          gap: 15px;
          max-width: 300px;
          
          .face-count {
            .el-tag {
              font-size: 16px;
              padding: 8px 16px;
              background: rgba(255,255,255,0.9);
              color: #333;
              border: 1px solid #ddd;
            }
          }
          
          .recognized-users {
            .user-info {
              margin-bottom: 12px;
              
              .user-card {
                background: rgba(255,255,255,0.95);
                color: #333;
                padding: 15px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                gap: 12px;
                animation: slideInRight 0.5s ease-out;
                border: 1px solid #e0e0e0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                
                .success-icon {
                  font-size: 24px;
                  color: #52c41a;
                }
                
                .user-details {
                  h3 {
                    margin: 0 0 4px 0;
                    font-size: 16px;
                    font-weight: 600;
                    color: #333;
                  }
                  
                  p {
                    margin: 0;
                    font-size: 14px;
                    color: #666;
                  }
                }
              }
            }
          }
          
          .strangers-alert {
            .el-alert {
              border-radius: 6px;
              background: rgba(255,255,255,0.95);
            }
          }
        }
      }
    }
  }
  
  .info-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 20px;
    padding: 15px 20px;
    background: white;
    border-radius: 6px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    border: 1px solid #e0e0e0;
    color: #333;
    
    .stats {
      display: flex;
      align-items: center;
      gap: 20px;
      font-size: 14px;
      
      .separator {
        opacity: 0.5;
      }
    }
    
    .connection-status {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      
      .el-icon {
        &.connected {
          color: #52c41a;
        }
        
        &.disconnected {
          color: #ff4d4f;
        }
      }
    }
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.success-feedback {
  .user-card {
    animation: pulse 1s ease-in-out;
  }
}

@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.02); }
  100% { transform: scale(1); }
}
</style> 