import request from '@/utils/http'

const baseURL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

export const getTeacherReportCardAPI = (classId) => {
  return request({ url: '/api/teacher/report-card', params: { class_id: classId } })
}

// 进入学生路由时请求该学生的成绩与知识点得分表（student）
export const getStudentScoreTableAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/score-table` })
}

// 学生端「任务」面板：获取按知识点分组的全部关联题目及已做/未做状态
export const getStudentTasksAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/tasks` })
}

// 「学情报告」面板：获取总得分率、各知识点得分率（动态数量）、错题题号列表（可选是否包含个性化建议）
export const getStudentLearningReportAPI = (studentId, { includeAdvice = true } = {}) => {
  return request({
    url: `/api/students/${encodeURIComponent(studentId)}/learning-report`,
    params: { include_advice: includeAdvice },
  })
}

// 「学情报告」右上角一键下载 PDF（可选是否包含个性化建议）
export const downloadStudentLearningReportPdfAPI = async (
  studentId,
  { includeAdvice = true } = {},
) => {
  const cleanId = String(studentId || 'D01').trim().toUpperCase() || 'D01'
  const query = new URLSearchParams({ include_advice: String(includeAdvice) }).toString()
  const response = await fetch(
    `${baseURL}/api/students/${encodeURIComponent(cleanId)}/learning-report/pdf?${query}`,
    {
      method: 'GET',
      credentials: 'include',
    },
  )
  if (!response.ok) {
    const isJSON = response.headers.get('content-type')?.includes('application/json')
    const errBody = isJSON ? await response.json() : null
    const message =
      errBody?.message ||
      errBody?.error?.message ||
      errBody?.detail?.error?.message ||
      (typeof errBody?.detail === 'string' ? errBody.detail : '') ||
      `下载学情报告失败（${response.status}）`
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  const blob = await response.blob()
  return {
    blob,
    filename: `学情报告_${cleanId}.pdf`,
  }
}

// 教师端「任务」面板：获取全部班级与分班级的各知识点平均得分率
export const getTeacherTasksAPI = () => {
  return request({ url: '/api/teacher/tasks' })
}
