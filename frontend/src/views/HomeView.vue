<script setup>
import { ref, onUnmounted } from 'vue'
import { useHistoryStore } from '@/stores/history'
import api from '@/services/api'
import UploadZone from '@/components/UploadZone.vue'
import TaskStatus from '@/components/TaskStatus.vue'
import HistoryList from '@/components/HistoryList.vue'

const historyStore = useHistoryStore()
const currentTasks = ref([])
const errorMessage = ref(null)

const activePollings = new Map()

const startPolling = (taskId) => {
  if (activePollings.has(taskId)) return

  const intervalId = setInterval(async () => {
    try {
      const response = await api.getTaskStatus(taskId)
      const task = response.data

      // Update local state
      const taskIndex = currentTasks.value.findIndex(t => t.task_id === taskId)
      if (taskIndex !== -1) {
        currentTasks.value[taskIndex] = task
      }

      // Update history store
      historyStore.updateTaskStatus(taskId, task.status, task)

      // Stop polling if completed or failed
      if (['completed', 'failed'].includes(task.status)) {
        stopPolling(taskId)
      }
    } catch (err) {
      console.error('Polling error', err)
      stopPolling(taskId)
      // We don't want to overwrite the global error message for a single poll failure,
      // but we can update the task status to failed visually.
      const taskIndex = currentTasks.value.findIndex(t => t.task_id === taskId)
      if (taskIndex !== -1) {
        currentTasks.value[taskIndex].status = 'failed'
        currentTasks.value[taskIndex].error_message = '无法获取任务状态，可能任务已过期或服务出错。'
      }
    }
  }, 2000) // Poll every 2 seconds

  activePollings.set(taskId, intervalId)
}

const stopPolling = (taskId) => {
  if (activePollings.has(taskId)) {
    clearInterval(activePollings.get(taskId))
    activePollings.delete(taskId)
  }
}

const stopAllPolling = () => {
  for (const taskId of activePollings.keys()) {
    stopPolling(taskId)
  }
}

onUnmounted(() => {
  stopAllPolling()
})

const handleFilesSelected = async (files, removeAd) => {
  errorMessage.value = null

  // Create placeholders for uploading files
  const newTasks = files.map((file, index) => ({
    _localId: Date.now() + index, // temporary ID before we get real task_id
    original_filename: file.name,
    status: 'uploading',
    uploadProgress: 0,
    file: file // keep reference to file to upload it
  }))

  currentTasks.value = [...newTasks, ...currentTasks.value]

  // Upload concurrently
  const uploadPromises = newTasks.map(async (localTask) => {
    try {
      const response = await api.convertFile(localTask.file, removeAd, (progressEvent) => {
        if (progressEvent.total) {
          const taskIndex = currentTasks.value.findIndex(t => t._localId === localTask._localId)
          if (taskIndex !== -1) {
            currentTasks.value[taskIndex].uploadProgress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          }
        }
      })

      // File uploaded, task created
      const task = response.data

      // Replace placeholder with real task
      const taskIndex = currentTasks.value.findIndex(t => t._localId === localTask._localId)
      if (taskIndex !== -1) {
        currentTasks.value[taskIndex] = task
      }

      historyStore.addTask(task)

      // Start polling for conversion progress
      startPolling(task.task_id)

    } catch (err) {
      console.error('Upload error for file', localTask.file.name, err)
      const taskIndex = currentTasks.value.findIndex(t => t._localId === localTask._localId)
      if (taskIndex !== -1) {
        currentTasks.value[taskIndex].status = 'failed'
        if (err.response && err.response.data && err.response.data.detail) {
          currentTasks.value[taskIndex].error_message = `上传失败: ${err.response.data.detail}`
        } else {
          currentTasks.value[taskIndex].error_message = '上传失败，请检查网络或稍后重试。'
        }
      }
    }
  })

  await Promise.allSettled(uploadPromises)
}

const clearCurrentTasks = () => {
  stopAllPolling()
  currentTasks.value = []
}
</script>

<template>
  <div class="w-full max-w-2xl mx-auto flex flex-col gap-6">
    <!-- Main Conversion Area -->
    <div class="bg-white p-8 rounded-2xl shadow-lg border border-gray-100 relative">
      <!-- Back button when task is present to do another conversion -->
      <button
        v-if="currentTasks.length > 0 && currentTasks.every(t => ['completed', 'failed'].includes(t.status))"
        @click="clearCurrentTasks"
        class="absolute top-4 right-4 text-sm text-gray-500 hover:text-blue-600 font-medium z-10"
      >
        清空并转换新文件 →
      </button>

      <!-- Upload Error -->
      <div v-if="errorMessage" class="mb-6 p-4 bg-red-50 text-red-600 rounded-lg text-sm flex items-start gap-3 border border-red-100">
        <svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        <span>{{ errorMessage }}</span>
        <button @click="errorMessage = null" class="ml-auto text-red-400 hover:text-red-700 font-bold p-1">×</button>
      </div>

      <template v-if="currentTasks.length > 0">
        <div class="flex flex-col gap-4 mb-6 mt-4">
          <div v-for="task in currentTasks" :key="task.task_id || task._localId" class="relative">
             <!-- Uploading State for specific task -->
            <div v-if="task.status === 'uploading'" class="w-full flex flex-col p-6 bg-gray-50 rounded-xl border border-gray-100">
              <p class="text-gray-700 font-medium mb-2 truncate" :title="task.original_filename">{{ task.original_filename }} - 正在上传...</p>
              <div class="w-full bg-gray-200 rounded-full h-2.5 mb-2 overflow-hidden relative">
                <div class="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out absolute left-0 top-0" :style="`width: ${task.uploadProgress}%`"></div>
              </div>
              <p class="text-xs text-gray-500">{{ task.uploadProgress }}%</p>
            </div>

            <!-- Current Task Status -->
            <TaskStatus
              v-else
              :task="task"
            />
          </div>
        </div>

        <!-- Append new files to existing list -->
        <UploadZone
          @files-selected="handleFilesSelected"
        />
      </template>

      <!-- Upload Zone when empty -->
      <UploadZone
        v-else
        @files-selected="handleFilesSelected"
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
