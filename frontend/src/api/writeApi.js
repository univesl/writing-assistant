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
  
  // 步骤式写作（流式）
  stepWrite: async (sessionId, productName, sellingPoints, style = 'simple', length = 'medium') => {
    return apiClient.post('/write/step', {
      session_id: sessionId,
      product_name: productName,
      selling_points: sellingPoints,
      style: style,
      length: length
    })
  },
  
  // 文本润色（流式）
  polishText: async (sessionId, content, polishType = 'check') => {
    return apiClient.post('/write/polish', {
      session_id: sessionId,
      content: content,
      polish_type: polishType
    })
  },
  
  // 获取会话历史内容
  getSessionContent: async (sessionId) => {
    const response = await apiClient.get(`/content/get/${sessionId}`)
    return response || []
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
  
  // 步骤式写作
  stepWrite: async (sessionId, productName, sellingPoints, style = 'simple', length = 'medium') => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          content: `产品：${productName}\n卖点：${sellingPoints}\n风格：${style}\n长度：${length}\n\n这是根据您提供的信息生成的文案内容，采用了${style}风格，长度为${length}。`,
          finish: true
        })
      }, 2000)
    })
  },
  
  // 文本润色
  polishText: async (sessionId, content, polishType = 'check') => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const polishResults = {
          check: `校对结果：${content}\n\n发现0个语法错误，0个拼写错误。`,
          optimize: `优化结果：${content}\n\n优化了句子结构，使表达更加流畅自然。`,
          expand: `扩写结果：${content}\n\n根据原文内容进行了扩展，增加了更多细节和例子。`
        }
        
        resolve({
          original_content: content,
          polished_content: polishResults[polishType] || content
        })
      }, 1000)
    })
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