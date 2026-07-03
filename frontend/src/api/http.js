import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000
})

http.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  r => r.data,
  err => {
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : (err.message || '请求失败，请检查后端服务')
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      location.href = '/login'
    }
    return Promise.reject(new Error(msg))
  }
)

export default http
