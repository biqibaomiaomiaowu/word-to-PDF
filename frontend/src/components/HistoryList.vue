<script setup>
import { useHistoryStore } from '@/stores/history'
import api from '@/services/api'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

const historyStore = useHistoryStore()
const { history } = storeToRefs(historyStore)

const formatTime = (isoString) => {
  if (!isoString) return ''
  const d = new Date(isoString)
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`
}

const statusColorText = (status) => {
  switch(status) {
    case 'pending': case 'processing': return 'text-blue-600'
    case 'completed': return 'text-green-600'
    case 'failed': return 'text-red-600'
    default: return 'text-gray-600'
  }
}

const statusLabel = (status) => {
  switch(status) {
    case 'pending': return '排队中'
    case 'processing': return '转换中'
    case 'completed': return '成功'
    case 'failed': return '失败'
    default: return '未知'
  }
}

const handleDownload = (taskId) => {
  const url = api.getDownloadUrl(taskId)
  window.location.href = url
}

const handleRemove = (taskId) => {
  historyStore.removeTask(taskId)
}
</script>

<template>
  <div class="w-full mt-10">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-xl font-semibold text-gray-700">转换历史记录</h3>
      <button v-if="history.length > 0" @click="historyStore.clearHistory" class="text-sm text-gray-500 hover:text-red-500 transition-colors">
        清空记录
      </button>
    </div>

    <div v-if="history.length === 0" class="text-center p-8 bg-gray-50 border border-gray-100 rounded-xl">
      <p class="text-gray-500">暂无转换记录</p>
    </div>

    <div v-else class="bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
      <ul class="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
        <li v-for="item in history" :key="item.task_id" class="p-4 hover:bg-gray-50 transition-colors flex items-center justify-between group">
          <div class="flex-1 min-w-0 pr-4">
            <p class="text-sm font-medium text-gray-900 truncate" :title="item.original_filename">
              {{ item.original_filename }}
            </p>
            <div class="flex items-center gap-3 mt-1">
              <span class="text-xs font-semibold" :class="statusColorText(item.status)">
                {{ statusLabel(item.status) }}
              </span>

              <template v-if="item.status === 'completed' && item.ad_removal_enabled">
                <span v-if="item.ad_removed && item.ad_remove_stage === 'docx'" class="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 border border-green-100">
                  去除广告(DOCX)
                </span>
                <span v-else-if="item.ad_removed && item.ad_remove_stage === 'pdf'" class="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 border border-green-100">
                  去除广告(PDF)
                </span>
                <span v-else class="text-[10px] px-1.5 py-0.5 rounded bg-gray-50 text-gray-500 border border-gray-100">
                  未检测到广告
                </span>
              </template>

              <span class="text-xs text-gray-400 ml-auto">
                {{ formatTime(item.created_at) }}
              </span>
            </div>
          </div>

          <div class="flex items-center space-x-2 pl-4">
            <!-- Retry download for completed files (note backend clears files after 1hr default) -->
            <button
              v-if="item.status === 'completed'"
              @click="handleDownload(item.task_id)"
              class="text-blue-600 hover:text-blue-800 text-sm px-3 py-1 bg-blue-50 rounded hover:bg-blue-100 transition-colors"
              title="下载文件 (可能已在服务器端过期)"
            >
              下载
            </button>
            <button
              @click="handleRemove(item.task_id)"
              class="text-gray-400 hover:text-red-600 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
              title="移除记录"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        </li>
      </ul>
      <div class="bg-yellow-50 p-3 text-xs text-yellow-700 border-t border-yellow-100 flex items-start gap-2">
        <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
        <span>服务器会定期自动清理转换后的文件。过期的历史记录点击下载将会失败。</span>
      </div>
    </div>
  </div>
</template>
