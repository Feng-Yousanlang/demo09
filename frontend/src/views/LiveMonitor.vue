<template>
  <div class="live-monitor">
    <div class="monitor-header">
      <h1>实时监控</h1>
      <div class="monitor-controls">
        <el-button
          v-if="cameraStatus === 'stopped'"
          type="success"
          size="large"
          @click="startCamera"
          :loading="controlLoading"
        >
          <el-icon><VideoPlay /></el-icon>
          开启监控
        </el-button>
        <el-button
          v-else
          type="danger"
          size="large"
          @click="stopCamera"
          :loading="controlLoading"
        >
          <el-icon><VideoPause /></el-icon>
          关闭监控
        </el-button>
        
        <el-tag
          :type="cameraStatus === 'running' ? 'success' : 'danger'"
          size="large"
          class="status-tag"
        >
          {{ cameraStatus === 'running' ? '监控中' : '已停止' }}
        </el-tag>
      </div>
    </div>

    <div class="monitor-content">
      <!-- 主视频区域 -->
      <div class="video-main">
        <el-card>
          <div class="video-container">
            <canvas 
              ref="videoCanvas"
              class="video-canvas"
              @click="handleCanvasClick"
              @mousemove="handleMouseMove"
            ></canvas>
            <img 
              v-if="cameraStatus === 'running'"
              :src="videoStreamUrl"
              ref="videoStream"
              alt="视频流"
              class="video-stream"
              style="display: block; max-width: 100%; max-height: 480px; margin: 0 auto;"
              @error="handleVideoError"
            />
            
            <!-- 覆盖层：显示检测结果 -->
            <div class="overlay-info">
              <div class="detection-status">
                <el-tag v-if="detectedFaces.length > 0" type="success">
                  检测到 {{ detectedFaces.length }} 个人脸
                </el-tag>
                <el-tag v-if="dangerZoneViolations.length > 0" type="danger">
                  {{ dangerZoneViolations.length }} 个危险区域违规
                </el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 侧边栏 -->
      <div class="monitor-sidebar">
        <!-- 检测信息 -->
        <el-card class="info-card">
          <template #header>
            <span>检测信息</span>
          </template>
          <div class="detection-info">
            <div class="info-item">
              <span class="label">人脸检测:</span>
              <span class="value">{{ detectedFaces.length }} 个</span>
            </div>
            <div class="info-item">
              <span class="label">已识别:</span>
              <span class="value">{{ recognizedFaces.length }} 个</span>
            </div>
            <div class="info-item">
              <span class="label">陌生人:</span>
              <span class="value">{{ strangers.length }} 个</span>
            </div>
            <div class="info-item">
              <span class="label">危险区域:</span>
              <span class="value">{{ dangerZones.length }} 个</span>
            </div>
          </div>
        </el-card>

        <!-- 最近告警 -->
        <el-card class="alerts-card">
          <template #header>
            <span>实时告警</span>
          </template>
          <div v-if="realtimeAlerts.length === 0" class="no-alerts">
            <el-icon><SuccessFilled /></el-icon>
            <p>暂无告警</p>
          </div>
          <div v-else class="alerts-list">
            <div 
              v-for="alert in realtimeAlerts" 
              :key="alert.id"
              class="alert-item"
              :class="alert.severity"
            >
              <div class="alert-time">{{ formatTime(alert.created_at) }}</div>
              <div class="alert-content">
                <div class="alert-title">{{ alert.title }}</div>
                <div class="alert-desc">{{ alert.description }}</div>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 控制面板 -->
        <el-card class="control-card">
          <template #header>
            <span>控制面板</span>
          </template>
          <div class="controls-list">
            <div class="control-item">
              <span class="label">显示人脸框:</span>
              <el-switch v-model="showFaceBoxes" />
            </div>
            <div class="control-item">
              <span class="label">显示危险区域:</span>
              <el-switch v-model="showDangerZones" />
            </div>
            <div class="control-item">
              <span class="label">显示轨迹:</span>
              <el-switch v-model="showTrajectory" />
            </div>
            <div class="control-item">
              <span class="label">AI分析:</span>
              <el-switch v-model="enableAIAnalysis" />
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
import axios from 'axios'

const videoCanvas = ref(null)
const videoStream = ref(null)
const videoStreamUrl = ref('')

const isRecording = ref(false)
const showFaceBoxes = ref(true)
const showDangerZones = ref(true)
const showTrajectory = ref(false)
const enableAIAnalysis = ref(true)

const cameraStatus = ref('stopped')
const controlLoading = ref(false)

const detectedFaces = ref([])
const recognizedFaces = ref([])
const strangers = ref([])
const dangerZones = ref([])
const dangerZoneViolations = ref([])
const realtimeAlerts = ref([])

let ws = null
let animationId = null

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

const drawVideoFrame = () => {
  // 只有在监控运行且有视频流时才绘制
  if (cameraStatus.value !== 'running' || !videoStreamUrl.value) return
  if (!videoCanvas.value || !videoStream.value) return
  
  const canvas = videoCanvas.value
  const video = videoStream.value
  const ctx = canvas.getContext('2d')
  
  try {
    // 检查视频元素状态
    if (!video.complete || video.naturalWidth === 0) {
      // 视频还没有加载任何数据
      return
    }
    
    if (video.error) {
      // 视频加载出错
      console.warn('视频元素出错:', video.error)
      return
    }
    
    // 设置画布尺寸
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    
    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // 绘制视频帧
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    
    // 绘制检测结果覆盖层
    drawOverlays(ctx)
    
  } catch (error) {
    // 处理绘制错误，通常是因为视频元素处于broken状态
    if (error.name === 'InvalidStateError') {
      console.warn('视频流暂不可用，跳过此帧绘制')
    } else {
      console.error('绘制视频帧时发生错误:', error)
    }
  }
}

const drawOverlays = (ctx) => {
  // 绘制人脸框
  if (showFaceBoxes.value && detectedFaces.value.length > 0) {
    detectedFaces.value.forEach(face => {
      const { left, top, right, bottom } = face.location
      
      ctx.strokeStyle = face.is_stranger ? '#ff4444' : '#44ff44'
      ctx.lineWidth = 2
      ctx.strokeRect(left, top, right - left, bottom - top)
      
      if (face.match) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
        ctx.fillRect(left, top - 20, right - left, 20)
        
        ctx.fillStyle = '#ffffff'
        ctx.font = '12px Arial'
        ctx.fillText(face.match.name, left + 5, top - 8)
      }
    })
  }
  
  // 绘制危险区域
  if (showDangerZones.value && dangerZones.value.length > 0) {
    dangerZones.value.forEach(zone => {
      ctx.strokeStyle = '#ffaa00'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      
      ctx.beginPath()
      zone.coordinates.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y)
        } else {
          ctx.lineTo(point.x, point.y)
        }
      })
      ctx.closePath()
      ctx.stroke()
      
      ctx.setLineDash([])
    })
  }
}

const handleCanvasClick = (event) => {
  const rect = videoCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  console.log('点击坐标:', { x, y })
}

const handleMouseMove = (event) => {
  // 可以在这里实现鼠标跟踪功能
}

let videoErrorRetry = 0
const handleVideoError = () => {
  if (videoErrorRetry < 3) {
    // 尝试重新加载视频流，带时间戳避免缓存
    videoErrorRetry += 1
    setTimeout(() => {
      refreshStream()
    }, 1000 * videoErrorRetry) // 逐次延长等待时间
  } else {
    ElMessage.error('视频流连接失败，请稍后重试')
  }
}

const toggleRecording = async () => {
  try {
    if (isRecording.value) {
      await axios.post('http://localhost:8000/api/video/stop-recording')
      ElMessage.success('录制已停止')
    } else {
      await axios.post('http://localhost:8000/api/video/start-recording')
      ElMessage.success('录制已开始')
    }
    isRecording.value = !isRecording.value
  } catch (error) {
    ElMessage.error('录制操作失败')
  }
}

const takeScreenshot = async () => {
  try {
    await axios.post('http://localhost:8000/api/video/screenshot')
    ElMessage.success('截图已保存')
  } catch (error) {
    ElMessage.error('截图失败')
  }
}

const MJPEG_API = 'http://localhost:8000/api/stream/mjpeg?rtmp_url=rtmp://121.41.28.35:9090/live/obs_stream'

const refreshStream = () => {
  if (cameraStatus.value === 'running') {
    videoStreamUrl.value = MJPEG_API
  }
}

const startCamera = async () => {
  controlLoading.value = true
  try {
    const response = await axios.post('/api/video/camera/start')
    if (response.data.success) {
      ElMessage.success('监控已启动')
      cameraStatus.value = 'running'
      videoStreamUrl.value = MJPEG_API
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
      ElMessage.success('监控已停止')
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
      videoStreamUrl.value = MJPEG_API
    } else {
      videoStreamUrl.value = ''
    }
  } catch (error) {
    console.error('获取摄像头状态失败:', error)
  }
}

const initWebSocket = () => {
  const wsUrl = `ws://localhost:8000/ws`
  ws = new WebSocket(wsUrl)
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'face_detection') {
      detectedFaces.value = data.data.faces || []
      recognizedFaces.value = data.data.faces.filter(f => !f.is_stranger) || []
      strangers.value = data.data.faces.filter(f => f.is_stranger) || []
    } else if (data.type === 'zone_violation') {
      dangerZoneViolations.value = data.data.violations || []
    } else if (data.type === 'realtime_alert' || data.type === 'event_alert') {
      realtimeAlerts.value.unshift(data.data)
      if (realtimeAlerts.value.length > 10) {
        realtimeAlerts.value = realtimeAlerts.value.slice(0, 10)
      }
    }
    
    // 触发重绘
    nextTick(drawVideoFrame)
  }
  
  ws.onclose = () => {
    setTimeout(initWebSocket, 3000)
  }
}

const loadDangerZones = async () => {
  try {
    const response = await axios.get('http://localhost:8000/api/zone')
    dangerZones.value = response.data.zones || []
  } catch (error) {
    console.error('加载危险区域失败:', error)
  }
}

onMounted(async () => {
  await loadDangerZones()
  initWebSocket()
  checkCameraStatus()
  
  // 只有在监控运行时才启动绘制循环
  const frameUpdate = () => {
    if (cameraStatus.value === 'running' && videoStreamUrl.value) {
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
.live-monitor {
  padding: 20px;
  height: calc(100vh - 80px);
  
  .monitor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    h1 {
      margin: 0;
      color: #333;
    }
  }
  
  .monitor-content {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 20px;
    height: calc(100% - 80px);
    
    .video-main {
      .video-container {
        position: relative;
        width: 100%;
        height: 100%;
        background: #000;
        border-radius: 4px;
        overflow: hidden;
        
        .video-canvas {
          width: 100%;
          height: 100%;
          object-fit: cover;
          cursor: crosshair;
        }
        
        .overlay-info {
          position: absolute;
          top: 10px;
          left: 10px;
          
          .detection-status {
            display: flex;
            flex-direction: column;
            gap: 5px;
          }
        }
      }
    }
    
    .monitor-sidebar {
      display: flex;
      flex-direction: column;
      gap: 20px;
      
      .info-card, .alerts-card, .control-card {
        .info-item, .control-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid #eee;
          
          &:last-child {
            border-bottom: none;
          }
          
          .label {
            font-size: 14px;
            color: #666;
          }
          
          .value {
            font-weight: bold;
            color: #333;
          }
        }
      }
      
      .alerts-card {
        flex: 1;
        
        .no-alerts {
          text-align: center;
          padding: 40px 0;
          color: #999;
          
          .el-icon {
            font-size: 48px;
            color: #67C23A;
            margin-bottom: 10px;
          }
        }
        
        .alerts-list {
          max-height: 300px;
          overflow-y: auto;
          
          .alert-item {
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
            border-left: 4px solid #409EFF;
            
            &.high {
              border-left-color: #F56C6C;
              background: #fef0f0;
            }
            
            &.medium {
              border-left-color: #E6A23C;
              background: #fdf6ec;
            }
            
            .alert-time {
              font-size: 12px;
              color: #999;
              margin-bottom: 5px;
            }
            
            .alert-title {
              font-weight: bold;
              color: #333;
              margin-bottom: 2px;
            }
            
            .alert-desc {
              font-size: 12px;
              color: #666;
            }
          }
        }
      }
    }
  }
}
</style> 