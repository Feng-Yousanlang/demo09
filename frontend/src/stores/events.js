import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'

export const useEventStore = defineStore('events', {
  state: () => ({
    events: [],
    recentEvents: [],
    unreadCount: 0,
    loading: false,
    error: null,
    filters: {
      type: '',
      severity: '',
      status: '',
      dateRange: []
    }
  }),

  actions: {
    async fetchEvents(params = {}) {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.get(`${API_BASE}/events`, { params })
        this.events = response.data.events || []
        return response.data
      } catch (error) {
        console.error('获取事件列表失败:', error)
        this.error = error.message
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchRecentEvents() {
      try {
        const response = await axios.get(`${API_BASE}/events/recent`)
        this.recentEvents = response.data.events || []
        this.unreadCount = response.data.unread_count || 0
      } catch (error) {
        console.error('获取最近事件失败:', error)
      }
    },

    async markEventAsRead(eventId) {
      try {
        await axios.put(`${API_BASE}/events/${eventId}/read`)
        
        // 更新本地状态
        const event = this.events.find(e => e.id === eventId)
        if (event) {
          event.is_read = true
        }
        
        const recentEvent = this.recentEvents.find(e => e.id === eventId)
        if (recentEvent) {
          recentEvent.is_read = true
        }
        
        if (this.unreadCount > 0) {
          this.unreadCount--
        }
      } catch (error) {
        console.error('标记事件已读失败:', error)
        throw error
      }
    },

    async markAllAsRead() {
      try {
        await axios.put(`${API_BASE}/events/mark-all-read`)
        
        // 更新本地状态
        this.events.forEach(event => {
          event.is_read = true
        })
        this.recentEvents.forEach(event => {
          event.is_read = true
        })
        this.unreadCount = 0
      } catch (error) {
        console.error('标记所有事件已读失败:', error)
        throw error
      }
    },

    addRealtimeEvent(event) {
      // 添加实时事件到列表开头
      this.recentEvents.unshift(event)
      this.events.unshift(event)
      
      // 限制最近事件数量
      if (this.recentEvents.length > 50) {
        this.recentEvents = this.recentEvents.slice(0, 50)
      }
      
      // 增加未读计数
      if (!event.is_read) {
        this.unreadCount++
      }
    },

    updateFilters(newFilters) {
      this.filters = { ...this.filters, ...newFilters }
    },

    clearError() {
      this.error = null
    }
  },

  getters: {
    filteredEvents: (state) => {
      let filtered = state.events
      
      if (state.filters.type) {
        filtered = filtered.filter(event => event.type === state.filters.type)
      }
      
      if (state.filters.severity) {
        filtered = filtered.filter(event => event.severity === state.filters.severity)
      }
      
      if (state.filters.status) {
        filtered = filtered.filter(event => event.status === state.filters.status)
      }
      
      return filtered
    },

    eventsByType: (state) => {
      const types = {}
      state.events.forEach(event => {
        if (!types[event.type]) {
          types[event.type] = 0
        }
        types[event.type]++
      })
      return types
    },

    unreadEvents: (state) => {
      return state.recentEvents.filter(event => !event.is_read)
    }
  }
}) 