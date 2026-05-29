import apiClient from './axiosConfig'

export const writeApi = {
  quickWrite: async (sessionId, prompt, modelType = 'general') => {
    return apiClient.post('/write/quick', {
      session_id: sessionId,
      prompt: prompt,
      model_type: modelType
    })
  },
  
  saveContent: async (sessionId, content, contentType, contentCategory = 'chat', role = 'user') => {
    return apiClient.post('/write/save', {
      session_id: sessionId,
      content: content,
      content_type: contentType,
      content_category: contentCategory,
      role: role
    })
  },
  
  getSessionContent: async (sessionId) => {
    const response = await apiClient.get(`/content/get/${sessionId}`)
    return response || []
  },
  
  getArticle: async (sessionId) => {
    const response = await apiClient.get(`/content/article/${sessionId}`)
    return response || { article_content: '' }
  },
  
  saveArticle: async (sessionId, articleContent) => {
    return apiClient.post('/content/article/save', {
      session_id: sessionId,
      article_content: articleContent
    })
  },
  
  uploadReference: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/content/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  exportDocument: async (sessionId, exportType = 'md', referenceDoc = null) => {
    let url = `/content/export/${sessionId}?export_type=${exportType}`
    if (referenceDoc) {
      url += `&reference_doc=${encodeURIComponent(referenceDoc)}`
    }
    const response = await apiClient.get(url, {
      responseType: 'blob'
    })
    return response
  },
  
  clearSessionContent: async (sessionId) => {
    return apiClient.delete(`/content/clear/${sessionId}`)
  }
}

export const writeMock = {
  quickWrite: async (sessionId, prompt, modelType = 'general') => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          content: `这是${modelType === 'general' ? '通用' : '创意'}模型根据您的需求生成的内容："${prompt}"。这是一段完整的生成结果，展示了AI写作助手的功能。`,
          finish: true
        })
      }, 1500)
    })
  },
  
  saveContent: async (sessionId, content, contentType) => {
    return {
      content_id: Date.now()
    }
  },
  
  getSessionContent: async (sessionId) => {
    return [
      {
        content_id: 1,
        content: '这是历史生成的内容',
        content_type: 'quick',
        created_at: new Date().toLocaleString()
      }
    ]
  }
}
