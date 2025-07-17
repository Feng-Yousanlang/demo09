import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'

export const useSystemStore = defineStore('system', {
  state: () => ({
    systemStatus: {
      overall_status: 'healthy',
      video_service: 'running',
      ai_service: 'running',
      database: 'connected',
      last_update: new Date().toISOString()
    },
    loading: false,
    error: null
  }),

  actions: {
    async fetchSystemStatus() {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.get(`${API_BASE}/system/status`)
        this.systemStatus = response.data
      } catch (error) {
        console.error('获取系统状态失败:', error)
        this.error = error.message
        // 设置默认状态
        this.systemStatus.overall_status = 'error'
      } finally {
        this.loading = false
      }
    },

    updateSystemStatus(newStatus) {
      this.systemStatus = { ...this.systemStatus, ...newStatus }
    },

    clearError() {
      this.error = null
    }
  },

  getters: {
    isSystemHealthy: (state) => state.systemStatus.overall_status === 'healthy',
    hasError: (state) => state.error !== null
  }
}) 