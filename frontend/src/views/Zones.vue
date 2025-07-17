<template>
  <div class="zones-page">
    <div class="page-header">
      <h2>危险区域</h2>
      <div class="header-actions">
        <el-button type="primary" @click="startDrawing">
          <el-icon><EditPen /></el-icon>
          添加区域
        </el-button>
        <el-button @click="refreshZones">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="zones-content">
      <!-- 视频预览和区域绘制 -->
      <div class="video-section">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>区域配置</span>
              <div class="video-controls">
                <el-button-group size="small">
                  <el-button 
                    :type="drawMode ? 'danger' : 'default'"
                    @click="toggleDrawMode"
                  >
                    {{ drawMode ? '退出绘制' : '绘制模式' }}
                  </el-button>
                  <el-button @click="clearDrawing">清除绘制</el-button>
                  <el-button @click="resetView">重置视图</el-button>
                </el-button-group>
              </div>
            </div>
          </template>
          
          <div class="video-container">
            <!-- 摄像头状态提示 -->
            <div v-if="cameraStatus !== 'running'" class="camera-status">
              <el-icon><VideoCamera /></el-icon>
              <p v-if="cameraStatus === 'stopped'">摄像头未启动</p>
              <p v-else-if="cameraStatus === 'error'">摄像头连接失败</p>
              <p v-else>摄像头状态: {{ cameraStatus }}</p>
              <el-button 
                v-if="cameraStatus === 'stopped'"
                type="primary" 
                @click="startCamera"
              >
                启动摄像头
              </el-button>
              <el-button 
                v-else
                @click="checkCameraStatus"
              >
                刷新状态
              </el-button>
            </div>
            
            <canvas
              ref="videoCanvas"
              class="video-canvas"
              @click="handleCanvasClick"
              @mousemove="handleMouseMove"
              @contextmenu="handleRightClick"
            ></canvas>
            <img
              v-if="videoStreamUrl"
              :src="videoStreamUrl"
              ref="videoStream"
              alt="视频流"
              class="video-stream"
              style="display: block; max-width: 100%; max-height: 480px; margin: 0 auto;"
              @load="drawFrame"
              @error="handleVideoError"
            />
            
            <!-- 绘制提示 -->
            <div v-if="drawMode" class="draw-tips">
              <p>绘制模式已启用</p>
              <p>左键点击添加点，右键完成绘制</p>
              <p>当前点数: {{ currentPoints.length }}</p>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 区域列表 -->
      <div class="zones-list">
        <el-card>
          <template #header>
            <span>危险区域列表</span>
          </template>
          
          <div v-if="zones.length === 0" class="no-zones">
            <el-icon><Location /></el-icon>
            <p>暂无危险区域</p>
            <p>点击"添加区域"开始配置</p>
          </div>
          
          <div v-else class="zones-items">
            <div
              v-for="zone in zones"
              :key="zone.id"
              class="zone-item"
              :class="{ active: selectedZone?.id === zone.id }"
              @click="selectZone(zone)"
            >
              <div class="zone-header">
                <div class="zone-info">
                  <h4>{{ zone.name }}</h4>
                  <el-tag 
                    :type="zone.is_active ? 'success' : 'info'"
                    size="small"
                  >
                    {{ zone.is_active ? '启用' : '禁用' }}
                  </el-tag>
                </div>
                <div class="zone-actions">
                  <el-button size="small" @click.stop="editZone(zone)">
                    编辑
                  </el-button>
                  <el-button 
                    size="small" 
                    type="danger" 
                    @click.stop="deleteZone(zone)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
              
              <div class="zone-details">
                <div class="zone-stats">
                  <span>停留阈值: {{ zone.stay_threshold }}秒</span>
                  <span>顶点数: {{ zone.coordinates.length }}</span>
                  <span>类型: {{ zone.zone_type }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 添加/编辑区域对话框 -->
    <el-dialog
      v-model="showZoneDialog"
      :title="editingZone ? '编辑危险区域' : '添加危险区域'"
      width="500px"
    >
      <el-form :model="zoneForm" :rules="zoneRules" ref="zoneFormRef" label-width="120px">
        <el-form-item label="区域名称" prop="name">
          <el-input v-model="zoneForm.name" placeholder="请输入区域名称" />
        </el-form-item>

        <el-form-item label="停留阈值" prop="stay_threshold">
          <el-input-number
            v-model="zoneForm.stay_threshold"
            :min="1"
            :max="300"
            :step="1"
            controls-position="right"
          />
          <span class="input-suffix">秒</span>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="zoneForm.is_active" />
        </el-form-item>
        <el-form-item label="顶点坐标">
          <div class="coordinates-info">
            <p v-if="zoneForm.coordinates.length === 0">请在视频画面中绘制区域</p>
            <div v-else>
              <p>已绘制 {{ zoneForm.coordinates.length }} 个顶点</p>
              <el-button size="small" @click="clearCoordinates">清除坐标</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showZoneDialog = false">取消</el-button>
          <el-button type="primary" @click="submitZoneForm" :loading="submitting">
            {{ editingZone ? '更新' : '创建' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoCamera } from '@element-plus/icons-vue'
import axios from 'axios'

const zones = ref([])
const selectedZone = ref(null)
const loading = ref(false)
const submitting = ref(false)

const videoCanvas = ref(null)
const videoStream = ref(null)
const videoStreamUrl = ref('')
const cameraStatus = ref('stopped')
const videoError = ref(false)

const drawMode = ref(false)
const currentPoints = ref([])
const showZoneDialog = ref(false)
const editingZone = ref(null)

const zoneFormRef = ref(null)
const zoneForm = reactive({
  name: '',
  stay_threshold: 10,
  is_active: true,
  coordinates: []
})

const zoneRules = {
  name: [
    { required: true, message: '请输入区域名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  stay_threshold: [
    { required: true, message: '请设置停留阈值', trigger: 'blur' },
    { type: 'number', min: 1, max: 300, message: '阈值范围为 1-300 秒', trigger: 'blur' }
  ]
}

let animationId = null

const MJPEG_API = 'http://localhost:8000/api/stream/mjpeg?rtmp_url=rtmp://121.41.28.35:9090/live/obs_stream'

const drawFrame = () => {
  if (!videoCanvas.value) return
  
  const canvas = videoCanvas.value
  const ctx = canvas.getContext('2d')
  
  // 设置画布尺寸
  canvas.width = 640
  canvas.height = 480
  
  // 清空画布
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  
  // 检查视频流状态
  if (cameraStatus.value !== 'running') {
    drawStatusMessage(ctx, '摄像头未启动', '#999')
    return
  }
  
  if (videoError.value) {
    drawStatusMessage(ctx, '视频流连接失败', '#ff4444')
    return
  }
  
  // 检查视频元素状态
  const video = videoStream.value
  if (!video || !video.complete || video.naturalWidth === 0) {
    drawStatusMessage(ctx, '视频加载中...', '#409EFF')
    return
  }
  
  try {
    // 绘制视频帧
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    
    // 绘制已有的危险区域
    drawExistingZones(ctx)
    
    // 绘制当前正在绘制的区域
    drawCurrentDrawing(ctx)
  } catch (error) {
    console.error('Canvas绘制错误:', error)
    drawStatusMessage(ctx, '视频绘制失败', '#ff4444')
  }
}

const drawStatusMessage = (ctx, message, color) => {
  ctx.fillStyle = color
  ctx.font = '16px Arial'
  ctx.textAlign = 'center'
  ctx.fillText(message, ctx.canvas.width / 2, ctx.canvas.height / 2)
}

const drawExistingZones = (ctx) => {
  zones.value.forEach(zone => {
    if (zone.coordinates && zone.coordinates.length > 2) {
      ctx.strokeStyle = zone.is_active ? '#ff6b6b' : '#95a5a6'
      ctx.fillStyle = zone.is_active ? 'rgba(255, 107, 107, 0.2)' : 'rgba(149, 165, 166, 0.2)'
      ctx.lineWidth = selectedZone.value?.id === zone.id ? 3 : 2
      ctx.setLineDash(zone.is_active ? [] : [5, 5])
      
      // 绘制填充区域
      ctx.beginPath()
      zone.coordinates.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y)
        } else {
          ctx.lineTo(point.x, point.y)
        }
      })
      ctx.closePath()
      ctx.fill()
      ctx.stroke()
      
      // 绘制区域名称
      if (zone.coordinates.length > 0) {
        const centerX = zone.coordinates.reduce((sum, p) => sum + p.x, 0) / zone.coordinates.length
        const centerY = zone.coordinates.reduce((sum, p) => sum + p.y, 0) / zone.coordinates.length
        
        ctx.fillStyle = '#333'
        ctx.font = '14px Arial'
        ctx.textAlign = 'center'
        ctx.fillText(zone.name, centerX, centerY)
      }
      
      ctx.setLineDash([])
    }
  })
}

const drawCurrentDrawing = (ctx) => {
  if (currentPoints.value.length > 0) {
    ctx.strokeStyle = '#409EFF'
    ctx.fillStyle = 'rgba(64, 158, 255, 0.2)'
    ctx.lineWidth = 2
    
    // 绘制已连接的线段
    if (currentPoints.value.length > 1) {
      ctx.beginPath()
      currentPoints.value.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y)
        } else {
          ctx.lineTo(point.x, point.y)
        }
      })
      ctx.stroke()
      
      // 如果有3个或以上点，显示填充预览
      if (currentPoints.value.length >= 3) {
        ctx.beginPath()
        currentPoints.value.forEach((point, index) => {
          if (index === 0) {
            ctx.moveTo(point.x, point.y)
          } else {
            ctx.lineTo(point.x, point.y)
          }
        })
        ctx.closePath()
        ctx.fill()
      }
    }
    
    // 绘制顶点
    currentPoints.value.forEach(point => {
      ctx.fillStyle = '#409EFF'
      ctx.beginPath()
      ctx.arc(point.x, point.y, 4, 0, 2 * Math.PI)
      ctx.fill()
    })
  }
}

const handleCanvasClick = (event) => {
  if (!drawMode.value) return
  
  const rect = videoCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // 调整坐标到画布实际尺寸
  const scaleX = videoCanvas.value.width / rect.width
  const scaleY = videoCanvas.value.height / rect.height
  
  const adjustedX = x * scaleX
  const adjustedY = y * scaleY
  
  currentPoints.value.push({ x: adjustedX, y: adjustedY })
  
  // 重绘画布
  nextTick(drawFrame)
}

const handleRightClick = (event) => {
  event.preventDefault()
  
  if (!drawMode.value || currentPoints.value.length < 3) {
    ElMessage.warning('至少需要3个点才能完成区域绘制')
    return
  }
  
  // 完成绘制
  zoneForm.coordinates = [...currentPoints.value]
  showZoneDialog.value = true
  drawMode.value = false
}

const handleMouseMove = (event) => {
  // 可以在这里实现鼠标跟踪预览
}

const handleVideoError = () => {
  console.error('视频流连接失败')
  videoError.value = true
  ElMessage.error('视频流连接失败，请检查摄像头状态')
}

const startDrawing = () => {
  drawMode.value = true
  currentPoints.value = []
  selectedZone.value = null
}

const toggleDrawMode = () => {
  drawMode.value = !drawMode.value
  if (!drawMode.value) {
    currentPoints.value = []
  }
}

const clearDrawing = () => {
  currentPoints.value = []
  drawFrame()
}

const clearCoordinates = () => {
  zoneForm.coordinates = []
  currentPoints.value = []
  drawFrame()
}

const resetView = () => {
  selectedZone.value = null
  drawMode.value = false
  currentPoints.value = []
  drawFrame()
}

const selectZone = (zone) => {
  selectedZone.value = zone
  drawFrame()
}

const fetchZones = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/zone')
    zones.value = response.data.data || []
  } catch (error) {
    console.error('获取危险区域列表失败:', error)
    ElMessage.error('获取危险区域列表失败')
  } finally {
    loading.value = false
  }
}

const refreshZones = () => {
  fetchZones()
  resetView()
}

const editZone = (zone) => {
  editingZone.value = zone
  Object.assign(zoneForm, {
    name: zone.name,
    stay_threshold: zone.stay_threshold,
    is_active: zone.is_active,
    coordinates: [...zone.coordinates]
  })
  currentPoints.value = [...zone.coordinates]
  showZoneDialog.value = true
}

const submitZoneForm = async () => {
  try {
    await zoneFormRef.value.validate()
    
    if (zoneForm.coordinates.length < 3) {
      ElMessage.error('请至少绘制3个顶点')
      return
    }
    
    submitting.value = true
    
    const zoneData = {
      name: zoneForm.name,
      zone_type: "polygon",
      coordinates: zoneForm.coordinates,
      stay_threshold: zoneForm.stay_threshold,
      is_active: zoneForm.is_active
    }
    
    if (editingZone.value) {
      await axios.put(`/api/zone/${editingZone.value.id}`, zoneData)
      ElMessage.success('危险区域更新成功')
    } else {
      await axios.post('/api/zone', zoneData)
      ElMessage.success('危险区域创建成功')
    }
    
    showZoneDialog.value = false
    resetZoneForm()
    await fetchZones()
    
  } catch (error) {
    ElMessage.error(editingZone.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const resetZoneForm = () => {
  Object.assign(zoneForm, {
    name: '',
    stay_threshold: 10,
    is_active: true,
    coordinates: []
  })
  currentPoints.value = []
  editingZone.value = null
  zoneFormRef.value?.resetFields()
}

const deleteZone = async (zone) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除危险区域 "${zone.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    
    await axios.delete(`/api/zone/${zone.id}`)
    ElMessage.success('危险区域删除成功')
    await fetchZones()
    
    if (selectedZone.value?.id === zone.id) {
      selectedZone.value = null
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
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
    ElMessage.error('获取摄像头状态失败')
  }
}

const startCamera = async () => {
  controlLoading.value = true
  try {
    const response = await axios.post('/api/video/camera/start')
    if (response.data.success) {
      ElMessage.success('摄像头已启动')
      cameraStatus.value = 'running'
      videoStreamUrl.value = MJPEG_API
    } else {
      ElMessage.error(response.data.message || '启动失败')
    }
  } catch (error) {
    ElMessage.error('启动失败')
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
    ElMessage.error('停止失败')
  } finally {
    controlLoading.value = false
  }
}

onMounted(async () => {
  await fetchZones()
  
  // 先检查摄像头状态，等待状态检查完成
  await checkCameraStatus()
  
  // 如果摄像头正在运行，等待一小段时间让视频流稳定
  if (cameraStatus.value === 'running') {
    // 添加延迟，确保视频流URL设置完成
    setTimeout(() => {
      videoError.value = false
    }, 1000)
  }
  
  // 启动绘制循环
  const frameUpdate = () => {
    drawFrame()
    animationId = requestAnimationFrame(frameUpdate)
  }
  frameUpdate()
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<style lang="scss" scoped>
.zones-page {
  padding: 20px;
  height: calc(100vh - 80px);

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

  .zones-content {
    display: grid;
    grid-template-columns: 1fr 350px;
    gap: 20px;
    height: calc(100% - 80px);

    .video-section {
      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

              .video-container {
          position: relative;
          width: 100%;
          height: 500px;
          background: #000;
          border-radius: 4px;
          overflow: hidden;

          .camera-status {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            color: #fff;
            z-index: 10;

            .el-icon {
              font-size: 48px;
              color: #409EFF;
              margin-bottom: 10px;
            }

            p {
              margin: 10px 0;
              font-size: 16px;
            }

            .el-button {
              margin-top: 10px;
            }
          }

          .video-canvas {
            width: 100%;
            height: 100%;
            object-fit: cover;
            cursor: crosshair;
          }

          .draw-tips {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: #fff;
            padding: 10px;
            border-radius: 4px;
            font-size: 12px;

            p {
              margin: 0 0 5px 0;

              &:last-child {
                margin-bottom: 0;
              }
            }
          }
        }
    }

    .zones-list {
      display: flex;
      flex-direction: column;

      .no-zones {
        text-align: center;
        padding: 40px 20px;
        color: #999;

        .el-icon {
          font-size: 48px;
          color: #409EFF;
          margin-bottom: 10px;
        }

        p {
          margin: 5px 0;
        }
      }

      .zones-items {
        .zone-item {
          border: 1px solid #eee;
          border-radius: 4px;
          margin-bottom: 10px;
          padding: 15px;
          cursor: pointer;
          transition: all 0.3s;

          &:hover {
            border-color: #409EFF;
            box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
          }

          &.active {
            border-color: #409EFF;
            background: #f0f9ff;
          }

          .zone-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;

            .zone-info {
              h4 {
                margin: 0 0 5px 0;
                color: #333;
                font-size: 16px;
              }
            }

            .zone-actions {
              .el-button {
                margin-left: 5px;
              }
            }
          }

          .zone-details {
            .zone-desc {
              margin: 0 0 10px 0;
              color: #666;
              font-size: 14px;
              line-height: 1.4;
            }

            .zone-stats {
              display: flex;
              gap: 15px;
              font-size: 12px;
              color: #999;
            }
          }
        }
      }
    }
  }

  .coordinates-info {
    .input-suffix {
      margin-left: 8px;
      color: #999;
      font-size: 12px;
    }
  }
}
</style> 