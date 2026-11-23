import axios from 'axios'
import request from '@/utils/http'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const createUploadAPI = ({ files, onUploadProgress }) => {
  const data = new FormData()
  for (const file of files) data.append('files', file)

  return axios
    .post(`${baseURL}/api/uploads`, data, { withCredentials: true, onUploadProgress })
    .then((res) => res.data)
}

// 教师端两步上传接口：step=1 模拟学生，step=2 作答记录（自动运行 steps 脚本）
export const uploadTeacherDataFileAPI = ({ file, step, onUploadProgress }) => {
  const data = new FormData()
  data.append('step', String(step))
  data.append('file', file)

  return axios
    .post(`${baseURL}/api/teacher/upload`, data, {
      withCredentials: true,
      onUploadProgress,
    })
    .then((res) => res.data)
}

export const getUploadStatusAPI = (batchId) => {
  return request({ url: `/api/uploads/${encodeURIComponent(batchId)}/status` })
}

export const getUploadChecklistAPI = (batchId) => {
  return request({ url: `/api/uploads/${encodeURIComponent(batchId)}` })
}

export const trialUploadAPI = (batchId) => {
  return request({ url: `/api/uploads/${encodeURIComponent(batchId)}/trial`, method: 'POST' })
}

export const publishUploadAPI = (batchId) => {
  return request({ url: `/api/uploads/${encodeURIComponent(batchId)}/publish`, method: 'POST' })
}

export const discardUploadAPI = (batchId) => {
  return request({ url: `/api/uploads/${encodeURIComponent(batchId)}`, method: 'DELETE' })
}
