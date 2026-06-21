import axios from 'axios'
import { useAdminStore } from '../store'

export const api = axios.create({
  baseURL: '/api/v1/admin',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = useAdminStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const isAuthEndpoint = err.config?.url?.includes('/auth/')
    if (!isAuthEndpoint && (err.response?.status === 401 || err.response?.status === 403)) {
      useAdminStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// Auth
export const login = (email: string, password: string) =>
  api.post('/auth/login', { email, password }).then((r) => r.data)

// Generation
export const previewDesign = (data: object) =>
  api.post('/generation/preview', data).then((r) => r.data)
export const refineDesign = (jobId: string, feedback: string) =>
  api.post(`/generation/${jobId}/refine`, { feedback }).then((r) => r.data)
export const approveGeneration = (jobId: string) =>
  api.post(`/generation/${jobId}/approve`).then((r) => r.data)
export const cancelJob = (jobId: string) =>
  api.post(`/generation/${jobId}/cancel`).then((r) => r.data)
export const retryJob = (jobId: string) =>
  api.post(`/generation/${jobId}/retry`).then((r) => r.data)
export const getJobStatus = (jobId: string) =>
  api.get(`/generation/${jobId}/status`).then((r) => r.data)
export const getGenerationHistory = () =>
  api.get('/generation/history').then((r) => r.data)

// Problems
export const listProblems = (page = 0, size = 20) =>
  api.get('/problems', { params: { page, size } }).then((r) => r.data)
export const createProblem = (data: object) =>
  api.post('/problems', data).then((r) => r.data)
export const updateProblem = (id: string, data: object) =>
  api.put(`/problems/${id}`, data).then((r) => r.data)
export const deleteProblem = (id: string) =>
  api.delete(`/problems/${id}`)
export const setPublished = (id: string, published: boolean) =>
  api.patch(`/problems/${id}/publish`, { published }).then((r) => r.data)

// Users
export const listUsers = (page = 0, size = 20) =>
  api.get('/users', { params: { page, size } }).then((r) => r.data)
export const deleteUser = (id: string) =>
  api.delete(`/users/${id}`)

// Monitoring
export const listSubmissions = (page = 0, size = 20) =>
  api.get('/submissions', { params: { page, size } }).then((r) => r.data)
export const getQueueDepth = () =>
  api.get('/submissions/queue-depth').then((r) => r.data)
