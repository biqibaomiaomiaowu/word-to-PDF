<script setup>
import { ref } from 'vue'

const emit = defineEmits(['file-selected'])
const isDragging = ref(false)
const fileInput = ref(null)

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
    validateAndEmit(e.dataTransfer.files[0])
  }
}

const handleFileSelect = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    validateAndEmit(e.target.files[0])
  }
}

const triggerFileInput = () => {
  fileInput.value.click()
}

const validateAndEmit = (file) => {
  const allowedExtensions = ['.doc', '.docx']
  const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

  if (!allowedExtensions.includes(fileExtension)) {
    alert(`不支持的文件格式：${fileExtension}。仅支持 .doc 和 .docx 文件。`)
    return
  }

  // 50MB limit
  if (file.size > 50 * 1024 * 1024) {
    alert('文件太大！最大支持 50MB。')
    return
  }

  emit('file-selected', file)
}
</script>

<template>
  <div
    class="w-full p-8 border-2 border-dashed rounded-xl transition-colors duration-200 cursor-pointer flex flex-col items-center justify-center text-center bg-white shadow-sm"
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
      accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      @change="handleFileSelect"
    >
    <svg class="w-16 h-16 text-blue-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
    </svg>
    <h3 class="text-xl font-medium text-gray-700 mb-2">点击或拖拽文件到这里上传</h3>
    <p class="text-sm text-gray-500">仅支持 .doc 和 .docx 格式，最大支持 50MB</p>
  </div>
</template>
