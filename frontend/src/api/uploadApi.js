import axios from './axiosConfig'

export const uploadApi = {
  // 上传文件到指定会话
  uploadFile: async (sessionId, file, autoParse = true, autoExtract = false, modelName = 'qwen3-235b') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('auto_parse', autoParse)
    formData.append('auto_extract', autoExtract)
    formData.append('model_name', modelName)

    // axios拦截器已经提取了res.data，所以直接返回response即可
    const response = await axios.post(`/upload/session/${sessionId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 300000  // 5分钟超时，因为PDF解析可能需要较长时间
    })
    return response
  },

  // 获取会话文件列表
  getSessionFiles: async (sessionId) => {
    const response = await axios.get(`/upload/session/${sessionId}/files`)
    return response
  },

  // 获取文件详情
  getFileDetail: async (fileId) => {
    const response = await axios.get(`/upload/file/${fileId}`)
    return response
  },

  // 提取文件字段
  extractFields: async (fileId, modelName = 'qwen3-235b') => {
    const formData = new FormData()
    formData.append('model_name', modelName)

    const response = await axios.post(`/upload/file/${fileId}/extract`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000  // 2分钟超时，因为LLM字段提取可能需要较长时间
    })
    return response
  },

  // 删除文件
  deleteFile: async (fileId) => {
    const response = await axios.delete(`/upload/file/${fileId}`)
    return response
  },

  // 获取可用模型列表
  getAvailableModels: async () => {
    const response = await axios.get('/upload/models')
    return response
  },

  // 更新文件字段（用户手动编辑后保存）
  updateFields: async (fileId, fields) => {
    const response = await axios.put(`/upload/file/${fileId}/fields`, {
      fields: fields
    }, {
      timeout: 30000  // 30秒超时
    })
    return response
  }
}
