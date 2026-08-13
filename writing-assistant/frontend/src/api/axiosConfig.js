import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
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
    console.log('Raw response:', response)
    console.log('Response data:', response.data)
    console.log('Response status:', response.status)
    console.log('Response headers:', response.headers)
    
    // 对于流式响应(Content-Type为text/event-stream)，直接返回response对象
    const contentType = response.headers['content-type']
    if (contentType && contentType.includes('text/event-stream')) {
      return response
    }
    // 对于文件下载响应(responseType为blob)，直接返回response对象
    if (response.config.responseType === 'blob') {
      return response.data
    }
    // 根据接口规范处理普通响应数据
    const res = response.data
    console.log('API Response:', res, 'code type:', typeof res?.code, 'code value:', res?.code)
    if (res && (res.code == 200 || res.code === 200)) {
      return res.data
    } else {
      const errorMsg = res?.msg || '请求失败'
      console.error('API Error:', errorMsg, 'code:', res?.code, 'full response:', res)
      return Promise.reject(new Error(errorMsg))
    }
  },
  error => {
    console.error('Network Error:', error)
    return Promise.reject(error)
  }
)

export default apiClient