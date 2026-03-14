import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

export default {
  // Convert a Word file
  convertFile(file, onUploadProgress) {
    const formData = new FormData()
    formData.append('file', file)

    return apiClient.post('/convert', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress
    })
  },

  // Check status of a conversion task
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}`)
  },

  // Download converted PDF
  getDownloadUrl(taskId) {
    const baseUrl = apiClient.defaults.baseURL === '/api'
        ? window.location.origin + '/api'
        : apiClient.defaults.baseURL;
    return `${baseUrl}/download/${taskId}`
  },

  // Health check
  healthCheck() {
    return apiClient.get('/health')
  }
}
