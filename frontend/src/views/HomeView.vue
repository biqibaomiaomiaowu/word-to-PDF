<script setup>
import { ref, onUnmounted } from 'vue'
import { useHistoryStore } from '@/stores/history'
import api from '@/services/api'
import UploadZone from '@/components/UploadZone.vue'
import TaskStatus from '@/components/TaskStatus.vue'
import HistoryList from '@/components/HistoryList.vue'

const historyStore = useHistoryStore()
const currentTask = ref(null)
const isUploading = ref(false)
const uploadProgress = ref(0)
const errorMessage = ref(null)

let pollInterval = null

const startPolling = (taskId) => {
  stopPolling() // Ensure only one interval runs

  pollInterval = setInterval(async () => {
    try {
      const response = await api.getTaskStatus(taskId)
      const task = response.data

      // Update local state
      currentTask.value = task

      // Update history store
      historyStore.updateTaskStatus(taskId, task.status, task)

      // Stop polling if completed or failed
      if (['completed', 'failed'].includes(task.status)) {
        stopPolling()
      }
    } catch (err) {
      console.error('Polling error', err)
      stopPolling()
      errorMessage.value = '无法获取任务状态，可能任务已过期或服务出错。'
    }
  }, 2000) // Poll every 2 seconds
}

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onUnmounted(() => {
  stopPolling()
})

const handleFileSelected = async (file) => {
  // Reset state
  errorMessage.value = null
  isUploading.value = true
  uploadProgress.value = 0
  currentTask.value = null

  try {
    const response = await api.convertFile(file, (progressEvent) => {
      if (progressEvent.total) {
        uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      }
    })

    // File uploaded, task created
    const task = response.data
    currentTask.value = task
    historyStore.addTask(task)

    // Start polling for conversion progress
    startPolling(task.task_id)

  } catch (err) {
    console.error('Upload error', err)
    if (err.response && err.response.data && err.response.data.detail) {
      errorMessage.value = `上传失败: ${err.response.data.detail}`
    } else {
      errorMessage.value = '上传失败，请检查网络或稍后重试。'
    }
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <div class="w-full max-w-2xl mx-auto flex flex-col gap-6">
    <!-- Main Conversion Area -->
    <div class="bg-white p-8 rounded-2xl shadow-lg border border-gray-100 relative">
      <!-- Back button when task is present to do another conversion -->
      <button
        v-if="currentTask && ['completed', 'failed'].includes(currentTask.status)"
        @click="currentTask = null"
        class="absolute top-4 right-4 text-sm text-gray-500 hover:text-blue-600 font-medium"
      >
        转换新文件 →
      </button>

      <!-- Upload Error -->
      <div v-if="errorMessage" class="mb-6 p-4 bg-red-50 text-red-600 rounded-lg text-sm flex items-start gap-3 border border-red-100">
        <svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        <span>{{ errorMessage }}</span>
        <button @click="errorMessage = null" class="ml-auto text-red-400 hover:text-red-700 font-bold p-1">×</button>
      </div>

      <!-- Current Task Status -->
      <TaskStatus
        v-if="currentTask"
        :task="currentTask"
        class="mb-6"
      />

      <!-- Uploading State -->
      <div v-else-if="isUploading" class="w-full flex flex-col items-center justify-center p-8 bg-gray-50 rounded-xl border border-gray-100 h-48">
        <p class="text-gray-600 font-medium mb-4">正在上传文件...</p>
        <div class="w-full max-w-sm bg-gray-200 rounded-full h-2.5 mb-2 overflow-hidden relative">
          <div class="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out absolute left-0 top-0" :style="`width: ${uploadProgress}%`"></div>
        </div>
        <p class="text-xs text-gray-500">{{ uploadProgress }}%</p>
      </div>

      <!-- Upload Zone -->
      <UploadZone
        v-else
        @file-selected="handleFileSelected"
      />

      <!-- Helper Text below active components -->
      <div class="mt-6 flex justify-center gap-4 text-xs text-gray-400">
        <span class="flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
          完全本地处理
        </span>
        <span class="flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          转换后自动清理
        </span>
      </div>
    </div>

    <!-- History Area -->
    <HistoryList />
  </div>
</template>
