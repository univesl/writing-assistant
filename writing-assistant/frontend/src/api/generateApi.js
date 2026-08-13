import axios from './axiosConfig'

export const generateApi = {
  // 基于知识库生成文档
  generateDocument: async (topic, requirements = '', modelName = null, useKnowledgeBase = true, topK = 3) => {
    const payload = {
      topic,
      requirements,
      use_knowledge_base: useKnowledgeBase,
      top_k: topK
    }
    if (modelName) payload.model_name = modelName

    const response = await axios.post('/generate/document', payload, {
      timeout: 120000
    })
    return response
  },

  // 获取可用的生成模型列表
  getModels: async () => {
    const response = await axios.get('/generate/models')
    return response
  },

  // 搜索知识库文档
  searchDocuments: async (query, topK = 3) => {
    const response = await axios.get(`/generate/search?query=${encodeURIComponent(query)}&top_k=${topK}`)
    return response
  },

  // 生成回函
  generateReply: async (data) => {
    const response = await axios.post('/generate/reply', data, {
      timeout: 120000,
      responseType: 'stream'
    })
    return response
  },

  // 以参考文档为基础生成
  generateWithReference: async (data) => {
    const response = await axios.post('/generate/with-reference', data, {
      timeout: 120000,
      responseType: 'stream'
    })
    return response
  },

  // 参考写作（流式）：回函/仿写/基于内容生成
  referenceWrite: async (data) => {
    const response = await axios.post('/generate/reference-write', data, {
      timeout: 120000,
      responseType: 'stream'
    })
    return response
  }
}
