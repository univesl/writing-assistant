import apiClient from './axiosConfig'

// 写作功能API
export const writeApi = {
  // 快速写作（流式）
  quickWrite: async (sessionId, prompt, modelType = 'general') => {
    return apiClient.post('/write/quick', {
      session_id: sessionId,
      prompt: prompt,
      model_type: modelType
    })
  },
  
  // 保存内容
  saveContent: async (sessionId, content, contentType) => {
    return apiClient.post('/write/save', {
      session_id: sessionId,
      content: content,
      content_type: contentType
    })
  },
  
  // 获取会话历史内容
  getSessionContent: async (sessionId) => {
    const response = await apiClient.get(`/content/get/${sessionId}`)
    return response || []
  },
  
  // 上传参考文档
  uploadReference: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/content/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  // 导出文档
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
  
  // 清空会话内容
  clearSessionContent: async (sessionId) => {
    return apiClient.delete(`/content/clear/${sessionId}`)
  }
}

// Mock数据服务（当后端未实现时使用）
export const writeMock = {
  // 快速写作（模拟流式响应）
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
  
  // 保存内容
  saveContent: async (sessionId, content, contentType) => {
    return {
      content_id: Date.now()
    }
  },
  
  // 获取会话历史内容
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
