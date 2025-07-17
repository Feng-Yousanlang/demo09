<template>
  <div id="app" class="app-container">
    <!-- 登录页面特殊布局 -->
    <router-view v-if="$route.meta.hideLayout" />
    
    <!-- 正常应用布局 -->
    <el-container v-else class="app-layout">
      <!-- 侧边栏 -->
      <el-aside width="250px" class="sidebar">
        <div class="logo">
          <h2>视频监控系统</h2>
        </div>
        <el-menu
          :default-active="$route.path"
          router
          class="sidebar-menu"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
          @select="handleMenuSelect"
        >
          <el-menu-item index="/live">
            <el-icon><VideoCamera /></el-icon>
            <span>实时监控</span>
          </el-menu-item>
          <el-menu-item index="/face-recognition">
            <el-icon><UserFilled /></el-icon>
            <span>人脸识别</span>
          </el-menu-item>
          <el-menu-item index="/events">
            <el-icon><Warning /></el-icon>
            <span>事件告警</span>
          </el-menu-item>
          <el-menu-item index="/faces">
            <el-icon><User /></el-icon>
            <span>人脸管理</span>
          </el-menu-item>
          <el-menu-item index="/zones">
            <el-icon><Location /></el-icon>
            <span>危险区域</span>
          </el-menu-item>
          <el-menu-item index="/logout">
            <el-icon><SwitchButton /></el-icon>
            <span>退出登录</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区域 -->
      <el-container>
        <!-- 顶部导航 -->
        <el-header class="header">
          <div class="header-content">
            <div class="header-left">
              <h3>{{ pageTitle }}</h3>
            </div>
            <div class="header-right">
              <el-badge :value="unreadEvents" class="event-badge">
                <el-button type="primary" :icon="Bell" @click="showEventDialog = true">
                  告警通知
                </el-button>
              </el-badge>
              <div class="system-status" :class="systemStatus.overall_status">
                <el-icon v-if="systemStatus.overall_status === 'healthy'"><CircleCheck /></el-icon>
                <el-icon v-else><Warning /></el-icon>
                <span>{{ systemStatus.overall_status === 'healthy' ? '系统正常' : '系统异常' }}</span>
              </div>
            </div>
          </div>
        </el-header>

        <!-- 页面内容 -->
        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>

    <!-- 事件通知对话框（仅在非登录页面显示） -->
    <el-dialog
      v-if="!$route.meta.hideLayout"
      v-model="showEventDialog"
      title="实时告警"
      width="600px"
    >
      <div class="event-list">
        <div v-for="event in recentEvents" :key="event.id" class="event-item">
          <div class="event-header">
            <el-tag :type="getEventTypeTag(event.severity)">{{ event.title }}</el-tag>
            <span class="event-time">{{ formatTime(event.created_at) }}</span>
          </div>
          <div class="event-content">{{ event.description }}</div>
        </div>
        <div v-if="recentEvents.length === 0" class="no-events">
          暂无新告警
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSystemStore } from './stores/system'
import { useEventStore } from './stores/events'
import { SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const systemStore = useSystemStore()
const eventStore = useEventStore()

const showEventDialog = ref(false)
let ws = null

// 页面标题映射
const pageTitleMap = {
  '/live': '实时监控',
  '/face-recognition': '人脸识别',
  '/events': '事件告警',
  '/faces': '人脸管理',
  '/zones': '危险区域'
}

const pageTitle = computed(() => {
  return pageTitleMap[route.path] || '家庭视频监控系统'
})

const systemStatus = computed(() => systemStore.systemStatus)
const unreadEvents = computed(() => eventStore.unreadCount)
const recentEvents = computed(() => eventStore.recentEvents)

const getEventTypeTag = (severity) => {
  const typeMap = {
    'high': 'danger',
    'medium': 'warning',
    'low': 'info'
  }
  return typeMap[severity] || 'info'
}

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

const initWebSocket = () => {
  const wsUrl = `ws://localhost:8000/ws`
  ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket连接已建立')
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'event_alert') {
      eventStore.addRealtimeEvent(data.data)
      // 可以在这里添加声音提醒或桌面通知
    } else if (data.type === 'system_status') {
      systemStore.updateSystemStatus(data.data)
    }
  }
  
  ws.onclose = () => {
    console.log('WebSocket连接已断开，尝试重连...')
    // 3秒后重连
    setTimeout(initWebSocket, 3000)
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket错误:', error)
  }
}

function handleMenuSelect(index) {
  if (index === '/logout') {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_info')
    router.push('/login')
  }
}

onMounted(async () => {
  // 初始化系统状态
  await systemStore.fetchSystemStatus()
  await eventStore.fetchRecentEvents()
  
  // 初始化WebSocket连接
  initWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<style lang="scss" scoped>
.app-container {
  height: 100vh;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', SimSun, sans-serif;
}

.app-layout {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #409EFF;
    h2 {
      color: white;
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }
  }
  
  .sidebar-menu {
    border: none;
    height: calc(100vh - 60px);
    width: 100%;
  }
}

.header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 100%;
    
    .header-left h3 {
      margin: 0;
      color: #303133;
    }
    
    .header-right {
      display: flex;
      align-items: center;
      gap: 20px;
      
      .event-badge {
        margin-right: 10px;
      }
      
      .system-status {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 14px;
        
        &.healthy {
          background-color: #f0f9ff;
          color: #67c23a;
        }
        
        &.degraded {
          background-color: #fef0f0;
          color: #f56c6c;
        }
      }
    }
  }
}

.main-content {
  background-color: #f5f5f5;
  padding: 20px;
}

.event-list {
  max-height: 400px;
  overflow-y: auto;
  
  .event-item {
    padding: 12px;
    border: 1px solid #e6e6e6;
    border-radius: 6px;
    margin-bottom: 8px;
    background-color: #fff;
    
    .event-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      
      .event-time {
        font-size: 12px;
        color: #909399;
      }
    }
    
    .event-content {
      font-size: 14px;
      color: #606266;
    }
  }
  
  .no-events {
    text-align: center;
    padding: 40px;
    color: #909399;
  }
}
</style> 