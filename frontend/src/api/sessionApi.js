import apiClient from './axiosConfig'

// 会话管理API
export const sessionApi = {
  // 创建新会话
  createSession: async (sessionName) => {
    return apiClient.post('/session/create', { session_name: sessionName })
  },
  
  // 获取会话列表
  getSessions: async () => {
    return apiClient.get('/session/list')
  },
  
  // 删除会话
  deleteSession: async (sessionId) => {
    return apiClient.delete(`/session/delete/${sessionId}`)
  },
  
  // 重命名会话
  renameSession: async (sessionId, sessionName) => {
    return apiClient.put(`/session/rename/${sessionId}`, { session_name: sessionName })
  }
}

// Mock数据服务（当后端未实现时使用）
export const sessionMock = {
  // 创建新会话
  createSession: async (sessionName) => {
    return {
      session_id: Date.now(),
      session_name: sessionName || '新会话',
      created_at: new Date().toLocaleString()
    }
  },
  
  // 获取会话列表
  getSessions: async () => {
    return []
  },
  
  // 删除会话
  deleteSession: async (sessionId) => {
    return null
  },
  
  // 重命名会话
  renameSession: async (sessionId, sessionName) => {
    return null
  }
}