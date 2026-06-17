import axios from './axiosConfig'

export const generateApi = {
  // 基于知识库生成文档
  generateDocument: async (topic, requirements = '', modelName = 'Qwen2.5-72B-Instruct', useKnowledgeBase = true, topK = 3) => {
    const response = await axios.post('/generate/document', {
      topic,
      requirements,
      model_name: modelName,
      use_knowledge_base: useKnowledgeBase,
      top_k: topK
    }, {
      timeout: 180000  // 3分钟超时，因为文档生成可能需要较长时间
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
      timeout: 180000,
      responseType: 'stream'
    })
    return response
  },

  // 以参考文档为基础生成
  generateWithReference: async (data) => {
    const response = await axios.post('/generate/with-reference', data, {
      timeout: 180000,
      responseType: 'stream'
    })
    return response
  },

  // 参考写作（流式）：回函/仿写/基于内容生成
  referenceWrite: async (data) => {
    const response = await axios.post('/generate/reference-write', data, {
      timeout: 180000,
      responseType: 'stream'
    })
    return response
  }
}
