<template>
  <div class="events-page">
    <div class="page-header">
      <h2>事件告警</h2>
      <div class="header-actions">
        <el-button @click="markAllAsRead" :disabled="unreadCount === 0">
          <el-icon><Check /></el-icon>
          全部已读
        </el-button>
        <el-button @click="refreshEvents">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="事件类型">
          <el-select v-model="filters.type" placeholder="请选择" clearable>
            <el-option label="人脸识别" value="face_recognition" />
            <el-option label="陌生人告警" value="stranger_alert" />
            <el-option label="危险区域违规" value="zone_violation" />
            <el-option label="异常行为" value="abnormal_behavior" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重程度">
          <el-select v-model="filters.severity" placeholder="请选择" clearable>
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="filters.status" placeholder="请选择" clearable>
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已处理" value="resolved" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchEvents">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>



    <!-- 事件列表 -->
    <el-card class="events-card">
      <template #header>
        <div class="card-header">
          <span>告警事件列表</span>
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </template>

      <el-table 
        :data="events" 
        v-loading="loading"
        @row-click="handleRowClick"
        row-key="id"
        :row-class-name="getRowClassName"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getEventTypeTag(row.type)">
              {{ getEventTypeName(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag :type="getSeverityTag(row.severity)">
              {{ getSeverityName(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="250" show-overflow-tooltip />
        <el-table-column label="截图" width="120">
          <template #default="{ row }">
            <el-image
              v-if="row.image_url"
              :src="row.image_url"
              :preview-src-list="[row.image_url]"
              fit="cover"
              style="width: 80px; height: 60px; border-radius: 4px;"
            />
            <span v-else class="no-image">无截图</span>
          </template>
        </el-table-column>
        <el-table-column label="视频" width="100">
          <template #default="{ row }">
            <div v-if="row.has_video || row.video_clip_url">
              <el-icon class="video-icon" color="#409EFF">
                <VideoPlay />
              </el-icon>
              <span class="video-duration" v-if="row.video_duration">
                {{ formatDuration(row.video_duration) }}
              </span>
            </div>
            <span v-else class="no-video">无视频</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="发生时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="!row.is_read" 
              size="small" 
              @click.stop="markAsRead(row.id)"
            >
              标记已读
            </el-button>
            <el-button 
              size="small" 
              type="primary" 
              @click.stop="viewDetails(row)"
            >
              查看详情
            </el-button>
            <el-button 
              size="small" 
              type="success" 
              @click.stop="updateStatus(row.id, 'resolved')"
              :disabled="row.status === 'resolved'"
            >
              标记处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 事件详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="selectedEvent?.title || '事件详情'"
      width="800px"
    >
      <div v-if="selectedEvent" class="event-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="事件ID">
            {{ selectedEvent.id }}
          </el-descriptions-item>
          <el-descriptions-item label="事件类型">
            <el-tag :type="getEventTypeTag(selectedEvent.type)">
              {{ getEventTypeName(selectedEvent.type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="严重程度">
            <el-tag :type="getSeverityTag(selectedEvent.severity)">
              {{ getSeverityName(selectedEvent.severity) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTag(selectedEvent.status)">
              {{ getStatusName(selectedEvent.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="发生时间" :span="2">
            {{ formatTime(selectedEvent.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="详细描述" :span="2">
            {{ selectedEvent.description }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="selectedEvent.image_url" class="event-image">
          <h4>相关截图</h4>
          <el-image
            :src="selectedEvent.image_url"
            :preview-src-list="[selectedEvent.image_url]"
            fit="contain"
            style="max-width: 100%; max-height: 400px;"
          />
        </div>

        <div v-if="selectedEvent.video_clip_url" class="event-video">
          <h4>事件视频下载</h4>
          <div class="video-info">
            <span v-if="selectedEvent.video_duration">
              时长: {{ formatDuration(selectedEvent.video_duration) }}
            </span>
            <span v-if="selectedEvent.video_size" class="video-size">
              大小: {{ formatFileSize(selectedEvent.video_size) }}
            </span>
            <el-button 
              size="small" 
              type="primary" 
              @click="downloadVideo(selectedEvent)"
              style="margin-left: 10px;"
            >
              <el-icon><Download /></el-icon>
              下载视频
            </el-button>
          </div>
        </div>

        <div v-if="selectedEvent.event_data" class="event-metadata">
          <h3>元数据</h3>
          <pre>{{ JSON.stringify(selectedEvent.event_data, null, 2) }}</pre>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDetailDialog = false">关闭</el-button>
          <el-button 
            v-if="selectedEvent && !selectedEvent.is_read" 
            type="primary" 
            @click="markAsRead(selectedEvent.id)"
          >
            标记已读
          </el-button>
          <el-button 
            v-if="selectedEvent && selectedEvent.status !== 'resolved'"
            type="success" 
            @click="updateStatus(selectedEvent.id, 'resolved')"
          >
            标记处理
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { useEventStore } from '../stores/events'
import { ElMessage } from 'element-plus'
import { VideoPlay, Download } from '@element-plus/icons-vue'
import axios from 'axios'

const eventStore = useEventStore()

const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDetailDialog = ref(false)
const selectedEvent = ref(null)



const filters = reactive({
  type: '',
  severity: '',
  status: '',
  dateRange: []
})

const events = computed(() => eventStore.filteredEvents)
const unreadCount = computed(() => eventStore.unreadCount)

const eventTypeMap = {
  'face_recognition': '人脸识别',
  'stranger_alert': '陌生人告警',
  'zone_violation': '危险区域违规',
  'abnormal_behavior': '异常行为'
}

const severityMap = {
  'high': '高',
  'medium': '中',
  'low': '低'
}

const statusMap = {
  'pending': '待处理',
  'processing': '处理中',
  'resolved': '已处理'
}

const getEventTypeName = (type) => eventTypeMap[type] || type
const getSeverityName = (severity) => severityMap[severity] || severity
const getStatusName = (status) => statusMap[status] || status

const getEventTypeTag = (type) => {
  const tagMap = {
    'face_recognition': 'info',
    'stranger_alert': 'danger',
    'zone_violation': 'warning',
    'abnormal_behavior': 'danger'
  }
  return tagMap[type] || 'info'
}

const getSeverityTag = (severity) => {
  const tagMap = {
    'high': 'danger',
    'medium': 'warning',
    'low': 'info'
  }
  return tagMap[severity] || 'info'
}

const getStatusTag = (status) => {
  const tagMap = {
    'pending': 'warning',
    'processing': 'primary',
    'resolved': 'success'
  }
  return tagMap[status] || 'info'
}

const getRowClassName = ({ row }) => {
  if (!row.is_read) {
    return 'unread-row'
  }
  return ''
}

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

const formatDuration = (seconds) => {
  if (!seconds) return '0s'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return mins > 0 ? `${mins}m${secs}s` : `${secs}s`
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0B'
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
}

const downloadVideo = (event) => {
  if (!event.video_clip_url) {
    ElMessage.error('视频文件不存在')
    return
  }
  
  try {
    const link = document.createElement('a')
    link.href = event.video_clip_url
    link.download = `event_${event.id}_video.mp4`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    ElMessage.success('视频下载已开始')
  } catch (error) {
    ElMessage.error('视频下载失败')
  }
}

const fetchEvents = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ...filters
    }
    
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_time = filters.dateRange[0]
      params.end_time = filters.dateRange[1]
    }

    // 直接调用API而不依赖Store状态
    const response = await axios.get('http://localhost:8000/api/events', { params })
    
    if (response.data.success) {
      // 更新本地事件数据
      eventStore.events = response.data.data.items || []
      total.value = response.data.data.total || 0
      
      console.log(`成功获取 ${response.data.data.items.length} 条事件记录`)
    } else {
      throw new Error(response.data.message || '获取事件失败')
    }
  } catch (error) {
    console.error('获取事件列表失败:', error)
    ElMessage.error('获取事件列表失败: ' + (error.response?.data?.message || error.message))
  } finally {
    loading.value = false
  }
}



const searchEvents = () => {
  currentPage.value = 1
  fetchEvents()
}

const resetFilters = () => {
  Object.assign(filters, {
    type: '',
    severity: '',
    status: '',
    dateRange: []
  })
  searchEvents()
}

const refreshEvents = () => {
  fetchEvents()
}

const markAsRead = async (eventId) => {
  try {
    await eventStore.markEventAsRead(eventId)
    ElMessage.success('标记已读成功')
    if (selectedEvent.value && selectedEvent.value.id === eventId) {
      selectedEvent.value.is_read = true
    }
  } catch (error) {
    ElMessage.error('标记已读失败')
  }
}

const markAllAsRead = async () => {
  try {
    await eventStore.markAllAsRead()
    ElMessage.success('全部标记已读成功')
  } catch (error) {
    ElMessage.error('批量标记失败')
  }
}

const updateStatus = async (eventId, status) => {
  try {
    await axios.put(`http://localhost:8000/api/events/${eventId}/status`, { status })
    ElMessage.success('状态更新成功')
    await fetchEvents()
    if (selectedEvent.value && selectedEvent.value.id === eventId) {
      selectedEvent.value.status = status
    }
  } catch (error) {
    ElMessage.error('状态更新失败')
  }
}

const handleRowClick = (row) => {
  viewDetails(row)
}

const viewDetails = (event) => {
  selectedEvent.value = event
  showDetailDialog.value = true
}

const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchEvents()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchEvents()
}

onMounted(() => {
  fetchEvents()
})
</script>

<style lang="scss" scoped>
.events-page {
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

  .filter-card {
    margin-bottom: 20px;
  }



  .events-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .no-image {
      color: #999;
      font-size: 12px;
    }

    .video-icon {
      margin-right: 4px;
    }

    .video-duration {
      font-size: 12px;
      color: #606266;
    }

    .no-video {
      color: #999;
      font-size: 12px;
    }
  }

  .event-detail {
    .event-image {
      margin-top: 20px;

      h4 {
        margin-bottom: 10px;
        color: #333;
      }
    }

    .event-video {
      margin-top: 20px;

      h4 {
        margin-bottom: 10px;
        color: #333;
      }

      .video-container {
        margin-bottom: 10px;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .video-info {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 14px;
        color: #606266;

        .video-size {
          color: #909399;
        }
      }
    }

    .event-metadata {
      margin-top: 15px;
      padding: 15px;

      h3 {
        margin-bottom: 10px;
        color: #333;
      }

      pre {
        background: #f5f5f5;
        padding: 10px;
        border-radius: 4px;
        font-size: 12px;
        max-height: 200px;
        overflow-y: auto;
      }
    }
  }
}

:deep(.unread-row) {
  background-color: #fef0f0;
}

:deep(.el-table__row:hover.unread-row) {
  background-color: #fde2e2;
}
</style> 