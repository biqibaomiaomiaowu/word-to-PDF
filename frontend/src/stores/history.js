import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useHistoryStore = defineStore('history', () => {
  // Try to load from local storage
  const savedHistory = localStorage.getItem('conversionHistory')
  const history = ref(savedHistory ? JSON.parse(savedHistory) : [])

  // Keep localStorage synced
  watch(history, (newHistory) => {
    localStorage.setItem('conversionHistory', JSON.stringify(newHistory))
  }, { deep: true })

  function addTask(task) {
    // Only keep the most recent 20 tasks
    if (history.value.length >= 20) {
      history.value.pop()
    }
    // Check if task exists, if so update it
    const existingIndex = history.value.findIndex(t => t.task_id === task.task_id)
    if (existingIndex >= 0) {
      history.value[existingIndex] = { ...history.value[existingIndex], ...task }
    } else {
      history.value.unshift(task)
    }
  }

  function updateTaskStatus(taskId, status, extraData = {}) {
    const task = history.value.find(t => t.task_id === taskId)
    if (task) {
      task.status = status
      Object.assign(task, extraData)
    }
  }

  function removeTask(taskId) {
    history.value = history.value.filter(t => t.task_id !== taskId)
  }

  function clearHistory() {
    history.value = []
  }

  return {
    history,
    addTask,
    updateTaskStatus,
    removeTask,
    clearHistory
  }
})
