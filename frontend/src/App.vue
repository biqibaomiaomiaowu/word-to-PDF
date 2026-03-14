<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex flex-col items-center py-10 px-4">
    <header class="mb-10 text-center">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">Word 转 PDF 转换器</h1>
      <p class="text-gray-600">本地化、安全的文档转换工具</p>
    </header>

    <main class="w-full max-w-4xl flex-1 flex flex-col items-center">
      <RouterView />
    </main>

    <footer class="mt-12 text-sm text-gray-500 text-center">
      &copy; {{ new Date().getFullYear() }} Word to PDF Converter. Powered by LibreOffice.
    </footer>
  </div>
</template>

<style scoped>
</style>
