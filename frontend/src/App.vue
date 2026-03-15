<template>
  <div class="flex flex-col min-h-screen bg-gray-50 text-gray-900 font-sans selection:bg-blue-100 selection:text-blue-900">
    <header class="w-full pt-12 pb-6 flex flex-col items-center justify-center">
      <h1 class="text-3xl font-bold tracking-tight text-gray-800 mb-2">文档格式转换器</h1>
      <p class="text-gray-500 text-sm">本地化、安全的文档转换工具</p>
    </header>

    <main class="flex-grow flex flex-col items-center px-4 pb-12 w-full">
      <router-view />
    </main>

    <footer class="w-full py-6 text-center text-xs text-gray-400 mt-auto">
      &copy; {{ new Date().getFullYear() }} Document Converter. Built with Vue 3 & FastAPI.
    </footer>
  </div>
</template>
