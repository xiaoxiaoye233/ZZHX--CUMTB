import request from '@/utils/http'

export const sendAgentMessageAPI = ({ role, studentId, message, sessionId = 'default' }) => {
  return request({
    url: '/api/agent/chat',
    method: 'POST',
    data: { role, student_id: studentId, message, session_id: sessionId },
  })
}

// 首次进入学生路由时自动请求 Agent 生成该学生的个性化学习建议
export const getStudentAdviceAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/advice` })
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

// 读取和保存后端的自动打印开关
export const getAgentConfigAPI = () => {
  return request({ url: '/api/agent/config' })
}

export const updateAgentConfigAPI = ({ autoPrint }) => {
  return request({
    url: '/api/agent/config',
    method: 'PATCH',
    data: { auto_print: autoPrint },
  })
}

// 学生每次进入自己的页面时申请生成并打印本次学情报告
export const requestStudentReportPrintAPI = (studentId, visitId) => {
  return request({
    url: `/api/students/${encodeURIComponent(studentId)}/print-report`,
    method: 'POST',
    data: { visit_id: visitId },
  })
}
