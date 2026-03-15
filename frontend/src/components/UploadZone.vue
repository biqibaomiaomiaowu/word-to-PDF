<script setup>
import { ref } from 'vue'

const emit = defineEmits(['files-selected'])
const props = defineProps({
  conversionType: {
    type: String,
    default: 'word_to_pdf'
  },
  capabilities: {
    type: Object,
    default: () => ({})
  }
})
const isDragging = ref(false)
const fileInput = ref(null)
// 从 Vite 环境变量中读取是否默认开启，如果没有配置，则默认 true
const defaultRemoveAd = import.meta.env.VITE_DEFAULT_REMOVE_AD !== 'false'
const removeAd = ref(defaultRemoveAd)
const converterMode = ref('auto')

const handleDragOver = (e) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = (e) => {
  e.preventDefault()
  isDragging.value = false
}

const handleDrop = (e) => {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    validateAndEmit(Array.from(e.dataTransfer.files))
  }
}

const handleFileSelect = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    validateAndEmit(Array.from(e.target.files))
  }
  // 清空 value 允许重复选择相同文件
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const triggerFileInput = () => {
  fileInput.value.click()
}

const validateAndEmit = (files) => {
  const isWordToPdf = props.conversionType === 'word_to_pdf'
  const allowedExtensions = isWordToPdf ? ['.doc', '.docx'] : ['.pdf']
  const validFiles = []
  const errorMessages = []

  // 单次最多 20 个文件
  if (files.length > 20) {
    errorMessages.push('单次最多只能上传 20 个文件，超出的文件将被忽略。')
    files = files.slice(0, 20)
  }

  for (const file of files) {
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

    if (!allowedExtensions.includes(fileExtension)) {
      if (!isWordToPdf && ['.doc', '.docx'].includes(fileExtension)) {
        errorMessages.push(`"${file.name}": 当前为 PDF 转 Word 模式，仅支持 .pdf；如需上传 ${fileExtension}，请切换到 Word 转 PDF 模式。`)
      } else if (isWordToPdf && ['.pdf'].includes(fileExtension)) {
        errorMessages.push(`"${file.name}": 当前为 Word 转 PDF 模式，仅支持 .doc/.docx；如需上传 .pdf，请切换到 PDF 转 Word 模式。`)
      } else {
        errorMessages.push(`"${file.name}": 不支持的格式(${fileExtension})`)
      }
      continue
    }

    // 100MB limit
    if (file.size > 100 * 1024 * 1024) {
      errorMessages.push(`"${file.name}": 文件太大(>100MB)`)
      continue
    }

    validFiles.push(file)
  }

  if (errorMessages.length > 0) {
    alert(`部分文件被跳过:\n\n${errorMessages.join('\n')}`)
  }

  if (validFiles.length > 0) {
    emit('files-selected', validFiles, removeAd.value, converterMode.value)
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div
      class="w-full p-8 border-2 border-dashed rounded-xl transition-colors duration-200 cursor-pointer flex flex-col items-center justify-center text-center bg-white shadow-sm relative"
      :class="isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="triggerFileInput"
    >
    <input
      type="file"
      ref="fileInput"
      class="hidden"
      multiple
      :accept="props.conversionType === 'word_to_pdf' ? '.doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document' : '.pdf,application/pdf'"
      @change="handleFileSelect"
    >
    <svg class="w-16 h-16 text-blue-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
    </svg>
      <h3 class="text-xl font-medium text-gray-700 mb-2">
        {{ props.conversionType === 'word_to_pdf' ? '上传 Word 文件' : '上传 PDF 文件' }}
      </h3>
      <p class="text-sm text-gray-500">
        {{ props.conversionType === 'word_to_pdf' ? '支持批量上传 .doc / .docx (最多 20 个)，单文件最大 100MB' : '支持批量上传 .pdf (最多 20 个)，单文件最大 100MB' }}
      </p>
    </div>

    <!-- Options Area -->
    <div class="flex flex-col gap-4 mt-2 px-2">
      <!-- PDF to Word Options -->
      <div v-if="props.conversionType === 'pdf_to_word'" class="flex flex-col gap-2">
        <label class="text-sm font-medium text-gray-700">转换方案选择</label>
        <div class="flex gap-4">
          <label class="inline-flex items-center">
            <input type="radio" v-model="converterMode" value="auto" class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 focus:ring-blue-500">
            <span class="ml-2 text-sm text-gray-700">自动选择（推荐）</span>
          </label>
          <label class="inline-flex items-center">
            <input type="radio" v-model="converterMode" value="pdf2docx" class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 focus:ring-blue-500">
            <span class="ml-2 text-sm text-gray-700">标准文本引擎 (pdf2docx)</span>
          </label>
          <label class="inline-flex items-center" :class="{ 'opacity-50 cursor-not-allowed': capabilities && capabilities.paddle_available === false }">
            <input type="radio" v-model="converterMode" value="paddle" :disabled="capabilities && capabilities.paddle_available === false" class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 focus:ring-blue-500">
            <span class="ml-2 text-sm text-gray-700">复杂版面引擎 (Paddle)</span>
            <span v-if="capabilities && capabilities.paddle_available === false" class="ml-1 text-xs text-red-500">(未配置)</span>
          </label>
        </div>
        <p v-if="converterMode === 'auto' && capabilities && capabilities.paddle_available === false" class="text-xs text-yellow-600 mt-1">当前未配置复杂版面引擎，自动选择将仅使用标准文本引擎。</p>
      </div>

      <!-- Ad Removal Option -->
      <div class="flex items-center gap-2">
        <input
          type="checkbox"
          id="removeAdCheckbox"
          v-model="removeAd"
          class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
        >
        <label for="removeAdCheckbox" class="text-sm font-medium text-gray-700 select-none">
          {{ props.conversionType === 'word_to_pdf' ? '智能去除末尾广告' : '智能去除尾页广告' }}（默认开启）
        </label>
        <span class="text-xs text-gray-500 ml-1">
          {{ props.conversionType === 'word_to_pdf' ? '仅检测最后一页底部区域，未识别到广告时不会修改文件' : '如支持则在转换前剔除 PDF 尾页广告' }}
        </span>
      </div>
    </div>
  </div>
</template>
