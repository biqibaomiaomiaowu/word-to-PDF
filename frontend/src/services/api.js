import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

export default {
  // Convert a file
  convertFile(file, removeAd = true, conversionType = 'word_to_pdf', converterMode = 'auto', onUploadProgress) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('remove_ad', removeAd)
    formData.append('conversion_type', conversionType)
    formData.append('converter_mode', converterMode)

    return apiClient.post('/convert', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress
    })
  },

  // Get Capabilities
  getCapabilities() {
    return apiClient.get('/capabilities')
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
