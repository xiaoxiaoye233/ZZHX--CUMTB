import request from '@/utils/http'

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

// 教师端「任务」面板：获取全部班级与分班级的各知识点平均得分率
export const getTeacherTasksAPI = () => {
  return request({ url: '/api/teacher/tasks' })
}
