import request from '@/utils/http'

export const sendAgentMessageAPI = ({ role, studentId, message, sessionId = 'default' }) => {
  return request({
    url: '/api/agent/chat',
    method: 'POST',
    data: { role, student_id: studentId, message, session_id: sessionId },
  })
}

// 成功登录后生成该次登录的个性化学习建议。
export const requestStudentLoginAdviceAPI = (studentId, loginId) => {
  return request({
    url: `/api/students/${encodeURIComponent(studentId)}/advice`,
    method: 'POST',
    data: { login_id: loginId },
    keepalive: true,
  })
}

// 获取指定学生的长期会话历史（学生端打开路由 + 教师端 Agent 设置按学号查看均使用此接口）
export const getStudentChatHistoryAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/agent/history` })
}

// 获取教师端的长期会话历史
export const getTeacherChatHistoryAPI = (sessionId = 'default') => {
  return request({
    url: '/api/agent/history',
    params: { role: 'teacher', session_id: sessionId },
  })
}

// 获取教师上传的教材 PDF 列表（师生共用）
export const getTextbooksAPI = () => {
  return request({ url: '/api/agent/textbooks' })
}

// 教师上传新教材 PDF（同步到后端教材库并触发向量化）
export const uploadTextbookAPI = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/api/agent/textbooks',
    method: 'POST',
    data: formData,
  })
}

// 删除指定教材文件
export const deleteTextbookAPI = (filename) => {
  return request({
    url: `/api/agent/textbooks/${encodeURIComponent(filename)}`,
    method: 'DELETE',
  })
}

// 获取与保存「知识梳理」知识图谱数据
export const getKnowledgeGraphAPI = () => {
  return request({ url: '/api/agent/knowledge-graph' })
}

export const saveKnowledgeGraphAPI = (graphData) => {
  return request({
    url: '/api/agent/knowledge-graph',
    method: 'PUT',
    data: graphData,
  })
}

export const resetKnowledgeGraphAPI = () => {
  return request({
    url: '/api/agent/knowledge-graph/reset',
    method: 'POST',
  })
}
