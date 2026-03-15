<script setup>
import { computed } from 'vue'
import api from '@/services/api'

const props = defineProps({
  task: {
    type: Object,
    required: true
  }
})

const statusText = computed(() => {
  switch (props.task.status) {
    case 'pending': return '排队中...'
    case 'processing': return '转换中...'
    case 'completed': return '转换成功'
    case 'failed': return '转换失败'
    default: return '未知状态'
  }
})

const statusColorClass = computed(() => {
  switch (props.task.status) {
    case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    case 'processing': return 'bg-blue-100 text-blue-800 border-blue-200'
    case 'completed': return 'bg-green-100 text-green-800 border-green-200'
    case 'failed': return 'bg-red-100 text-red-800 border-red-200'
    default: return 'bg-gray-100 text-gray-800 border-gray-200'
  }
})

const isProcessing = computed(() => ['pending', 'processing'].includes(props.task.status))

const handleDownload = () => {
  if (props.task.status === 'completed') {
    const url = api.getDownloadUrl(props.task.task_id)
    window.location.href = url
  }
}
</script>

<template>
  <div class="flex flex-col bg-white p-6 rounded-xl border shadow-sm w-full mb-6" :class="statusColorClass">
    <div class="flex items-center justify-between">
      <div class="flex flex-col min-w-0 pr-4">
        <h3 class="text-lg font-semibold truncate" :title="task.original_filename">
          {{ task.original_filename }}
        </h3>
        <span class="text-xs opacity-70 mt-1 font-mono">ID: {{ task.task_id.substring(0, 8) }}...</span>
      </div>

      <span class="px-3 py-1 rounded-full text-xs font-bold tracking-wide flex items-center gap-2 whitespace-nowrap">
        <svg v-if="isProcessing" class="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <svg v-else-if="task.status === 'completed'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        <svg v-else-if="task.status === 'failed'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>

        {{ statusText }}
      </span>
    </div>

    <!-- Ad Removal Tags -->
    <div v-if="task.status === 'completed' && task.ad_removal_enabled" class="mt-2 flex gap-2">
      <span v-if="task.ad_removed && task.ad_remove_stage === 'docx'" class="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
        去除广告(DOCX)
      </span>
      <span v-else-if="task.ad_removed && task.ad_remove_stage === 'pdf'" class="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
        去除广告(PDF)
      </span>
      <span v-else class="inline-flex items-center rounded-md bg-gray-50 px-2 py-1 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-500/10">
        未检测到广告
      </span>
    </div>

    <!-- Quality Labels (PDF to Word) -->
    <div v-if="task.status === 'completed' && task.conversion_type === 'pdf_to_word' && task.final_quality_level" class="mt-2 flex gap-2">
      <span v-if="task.final_quality_level === 'good'" class="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
        转换质量：良好
      </span>
      <span v-else-if="task.final_quality_level === 'acceptable'" class="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-700 ring-1 ring-inset ring-yellow-600/20">
        转换质量：可接受
      </span>
      <span v-else-if="task.final_quality_level === 'poor'" class="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/20">
        转换质量：较差
      </span>
    </div>

    <!-- Error message if any -->
    <div v-if="task.status === 'failed' && task.error_message" class="mt-4 p-3 bg-white/50 rounded-md text-sm">
      <p class="font-medium mb-1">错误信息：</p>
      {{ task.error_message }}
    </div>

    <!-- Quality Warnings if any (Completed with Warnings) -->
    <div v-if="task.status === 'completed' && task.quality_warnings && task.quality_warnings.length > 0" class="mt-4 p-3 bg-yellow-50 text-yellow-800 border border-yellow-200 rounded-md text-sm flex flex-col gap-1">
      <p class="font-bold mb-1 flex items-center gap-1">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
        质量提示：
      </p>
      <ul class="list-disc pl-5">
        <li v-for="(warning, index) in task.quality_warnings" :key="index">{{ warning }}</li>
      </ul>
    </div>
    <div v-else-if="task.status === 'completed' && task.warnings && task.warnings.length > 0" class="mt-4 p-3 bg-yellow-50 text-yellow-800 border border-yellow-200 rounded-md text-sm flex flex-col gap-1">
      <p class="font-bold mb-1 flex items-center gap-1">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
        质量提示：
      </p>
      <ul class="list-disc pl-5">
        <li v-for="(warning, index) in task.warnings" :key="index">{{ warning }}</li>
      </ul>
    </div>

    <!-- Action Area -->
    <div v-if="task.status === 'completed'" class="mt-4 flex justify-end">
      <button
        @click="handleDownload"
        class="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-5 rounded-lg shadow-sm transition-colors duration-150 flex items-center gap-2 text-sm"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
        </svg>
        {{ task.conversion_type === 'pdf_to_word' ? '下载 Word' : '下载 PDF' }}
      </button>
    </div>
  </div>
</template>
