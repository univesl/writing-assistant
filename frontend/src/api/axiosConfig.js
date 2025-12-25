import axios from 'axios'

// 创建axios实例
const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  config => {
    // 可以在这里添加token等认证信息
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  response => {
    // 对于流式响应(Content-Type为text/event-stream)，直接返回response对象
    const contentType = response.headers['content-type']
    if (contentType && contentType.includes('text/event-stream')) {
      return response
    }
    // 根据接口规范处理普通响应数据
    const res = response.data
    if (res.code === 200) {
      return res.data
    } else {
      console.error('API Error:', res.msg)
      return Promise.reject(new Error(res.msg || 'Error'))
    }
  },
  error => {
    console.error('Network Error:', error)
    return Promise.reject(error)
  }
)

export default apiClient