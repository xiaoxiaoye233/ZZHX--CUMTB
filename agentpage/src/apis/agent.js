import request from '@/utils/http'

export const sendAgentMessageAPI = ({ role, studentId, message }) => {
  return request({
    url: '/api/agent/chat',
    method: 'POST',
    data: { role, student_id: studentId, message },
  })
}

// 进入学生路由时自动请求 Agent 生成该学生的个性化学习建议
export const getStudentAdviceAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/advice` })
}

// 以下是后端待实现的配置和对话历史接口。
export const getAgentConfigAPI = () => {
  return request({ url: '/api/agent/config' })
}

export const updateAgentConfigAPI = ({ tone, autoPrint }) => {
  return request({
    url: '/api/agent/config',
    method: 'PATCH',
    data: { tone, auto_print: autoPrint },
  })
}

export const getStudentChatHistoryAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/agent/history` })
}
