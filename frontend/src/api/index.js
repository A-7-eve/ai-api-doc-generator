import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 请求拦截器：自动携带登录 Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 时清除登录态并跳回登录页
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // 避免重复跳转提示
      if (!window.location.hash.includes('/login')) {
        window.location.hash = '#/login'
        window.location.reload()
      }
    }
    return Promise.reject(err)
  }
)

// 解析项目（上传ZIP）
export async function parseProjectFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await api.post('/parse', formData)
  return res.data
}

// 解析项目（本地路径）
export async function parseProjectPath(path) {
  const formData = new FormData()
  formData.append('path', path)
  const res = await api.post('/parse', formData)
  return res.data
}

// 快捷解析内置示例项目
export async function parseSample() {
  const res = await api.post('/parse-sample')
  return res.data
}

// 获取项目接口列表
export async function getProject(projectId) {
  const res = await api.get(`/project/${projectId}`)
  return res.data
}

// 获取已解析项目列表（普通用户仅自己的，管理员全部）
export async function listProjects() {
  const res = await api.get('/project')
  return res.data
}

// 删除项目（归属人或管理员）
export async function deleteProject(projectId) {
  const res = await api.delete(`/project/${projectId}`)
  return res.data
}

// 获取单个接口详情
export async function getEndpoint(endpointId) {
  const res = await api.get(`/endpoint/${endpointId}`)
  return res.data
}

// 重新 AI 增强单个接口
export async function reEnhanceEndpoint(endpointId) {
  const res = await api.post(`/endpoint/${endpointId}/enhance`)
  return res.data
}

// 编辑接口信息
export async function updateEndpoint(endpointId, data) {
  const res = await api.put(`/endpoint/${endpointId}`, data)
  return res.data
}

// 导出文档：从响应头解析后端下发的文件名（修复下载文件名丢失 bug）
export async function exportProject(projectId, format) {
  const res = await api.get(`/project/${projectId}/export`, {
    params: { format },
    responseType: 'blob',
  })
  return res
}

// ========== 文档在线编辑（v2.4） ==========

// 获取文档内容（优先编辑版，无则生成版）；返回 { content, edited }
export async function getDoc(projectId, format) {
  const res = await api.get(`/project/${projectId}/doc`, { params: { format } })
  return res.data
}

// 保存文档编辑版
export async function saveDoc(projectId, format, content) {
  const res = await api.put(`/project/${projectId}/doc`, { format, content })
  return res.data
}

// 重置文档（清除编辑版，恢复生成版）；返回 { content, edited }
export async function resetDoc(projectId, format) {
  const res = await api.post(`/project/${projectId}/doc/reset`, { format })
  return res.data
}

// 从 Content-Disposition 响应头中提取文件名（支持 filename*=UTF-8'' 编码格式）
export function getFilenameFromDisposition(disposition, fallback) {
  if (!disposition) return fallback
  // 优先匹配 filename*=UTF-8''xxx（RFC 5987）
  const starMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (starMatch) {
    return decodeURIComponent(starMatch[1].replace(/"/g, ''))
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  if (plainMatch) {
    return plainMatch[1]
  }
  return fallback
}

// ========== 认证相关 ==========

// 登录
export async function login(username, password) {
  const res = await api.post('/auth/login', { username, password })
  return res.data
}

// 注册
export async function register(username, password) {
  const res = await api.post('/auth/register', { username, password })
  return res.data
}

// 获取当前用户信息
export async function fetchMe() {
  const res = await api.get('/auth/me')
  return res.data
}

// 用户列表（管理员）
export async function listUsers() {
  const res = await api.get('/auth/users')
  return res.data
}

// 修改用户角色（管理员）
export async function updateUserRole(userId, role) {
  const res = await api.put(`/auth/users/${userId}/role`, { role })
  return res.data
}

// 删除用户（管理员）
export async function deleteUser(userId) {
  const res = await api.delete(`/auth/users/${userId}`)
  return res.data
}

// 退出登录（前端清除本地凭证即可，JWT 无需服务端注销）
export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}
