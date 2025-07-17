<template>
  <div class="slide-verify-container">
    <div class="slide-verify-track" :style="{ width: trackWidth + 'px' }">
      <div 
        class="slide-verify-progress" 
        :style="{ width: progressWidth + 'px' }"
      ></div>
      <div class="slide-verify-text">{{ verifyText }}</div>
      <div 
        class="slide-verify-thumb"
        :style="{ left: thumbLeft + 'px' }"
        @mousedown="startSlide"
        @touchstart="startSlide"
      >
        <i class="el-icon-arrow-right"></i>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const emit = defineEmits(['verify-success', 'verify-fail'])

// 滑块相关状态
const trackWidth = ref(300)
const thumbLeft = ref(0)
const thumbWidth = 40
const isDragging = ref(false)
const isVerified = ref(false)
const startX = ref(0)

// 计算属性
const progressWidth = computed(() => thumbLeft.value + thumbWidth)
const verifyText = computed(() => {
  if (isVerified.value) {
    return '验证成功'
  }
  return '请向右滑动滑块'
})

// 开始滑动
const startSlide = (e) => {
  if (isVerified.value) return
  
  isDragging.value = true
  startX.value = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX
  
  document.addEventListener('mousemove', onSlide)
  document.addEventListener('mouseup', endSlide)
  document.addEventListener('touchmove', onSlide)
  document.addEventListener('touchend', endSlide)
  
  e.preventDefault()
}

// 滑动过程
const onSlide = (e) => {
  if (!isDragging.value) return
  
  const currentX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX
  const deltaX = currentX - startX.value
  const newLeft = Math.max(0, Math.min(deltaX, trackWidth.value - thumbWidth))
  
  thumbLeft.value = newLeft
}

// 结束滑动
const endSlide = () => {
  if (!isDragging.value) return
  
  isDragging.value = false
  
  // 检查是否滑动到最右端（允许一些误差）
  const threshold = trackWidth.value - thumbWidth - 5
  
  if (thumbLeft.value >= threshold) {
    // 验证成功
    isVerified.value = true
    thumbLeft.value = trackWidth.value - thumbWidth
    emit('verify-success')
  } else {
    // 验证失败，重置位置
    thumbLeft.value = 0
    emit('verify-fail')
  }
  
  document.removeEventListener('mousemove', onSlide)
  document.removeEventListener('mouseup', endSlide)
  document.removeEventListener('touchmove', onSlide)
  document.removeEventListener('touchend', endSlide)
}

// 重置验证状态
const reset = () => {
  isVerified.value = false
  thumbLeft.value = 0
}

// 暴露方法给父组件
defineExpose({
  reset,
  isVerified: computed(() => isVerified.value)
})

onMounted(() => {
  // 确保组件正确初始化
  reset()
})
</script>

<style scoped>
.slide-verify-container {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}

.slide-verify-track {
  position: relative;
  height: 40px;
  background-color: #f7f7f7;
  border: 1px solid #e4e7ed;
  border-radius: 20px;
  overflow: hidden;
  user-select: none;
}

.slide-verify-progress {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #42d392, #647eff);
  border-radius: 20px;
  transition: all 0.3s ease;
}

.slide-verify-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  color: #909399;
  z-index: 1;
}

.slide-verify-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 36px;
  height: 36px;
  background-color: #fff;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 3px rgba(0, 0, 0, 0.3);
  transition: all 0.3s ease;
  z-index: 2;
}

.slide-verify-thumb:hover {
  box-shadow: 0 0 6px rgba(0, 0, 0, 0.4);
}

.slide-verify-thumb:active {
  cursor: grabbing;
}

.slide-verify-thumb i {
  color: #409eff;
  font-size: 16px;
}

/* 验证成功状态 */
.slide-verify-track:has(.slide-verify-progress:last-child) .slide-verify-text {
  color: #67c23a;
}

.slide-verify-track:has(.slide-verify-progress:last-child) .slide-verify-thumb i {
  color: #67c23a;
}
</style> 