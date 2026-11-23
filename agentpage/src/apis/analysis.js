import request from '@/utils/http'

export const getStudentsAPI = () => {
  return request({ url: '/api/students' })
}

export const getClassesAPI = (classId) => {
  return request({ url: '/api/classes', params: { class_id: classId } })
}

// 教师首页与数据详情页统一概览接口（班级平均分、最低得分率主题、各学生各主题得分与总得分）
export const getTeacherOverviewAPI = () => {
  return request({ url: '/api/teacher/overview' })
}

export const getClassAnalysisAPI = (classId) => {
  return request({ url: `/api/analysis/classes/${encodeURIComponent(classId)}` })
}

export const getClassIndicatorsAPI = (classId) => {
  return request({ url: `/api/classes/${encodeURIComponent(classId)}/indicators` })
}

export const getClassThemesAPI = (classId) => {
  return request({ url: `/api/classes/${encodeURIComponent(classId)}/themes` })
}

export const getStudentAnalysisAPI = ({ studentId, exam }) => {
  return request({
    url: `/api/analysis/students/${encodeURIComponent(studentId)}`,
    params: { exam },
  })
}

export const getStudentDetailsAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}` })
}

// 进入学生路由时请求该学生的成绩与知识点得分表（student）
export const getStudentScoreTableAPI = (studentId) => {
  return request({ url: `/api/students/${encodeURIComponent(studentId)}/score-table` })
}

export const getQuestionAPI = (questionId) => {
  return request({ url: `/api/questions/${encodeURIComponent(questionId)}` })
}

export const getMyAnalysisAPI = ({ studentId, exam }) => {
  return request({ url: '/api/me/analysis', params: { student_id: studentId, exam } })
}

export const getMyPlansAPI = (studentId) => {
  return request({ url: '/api/me/plans', params: { student_id: studentId } })
}

// 联调草案，由后端根据登录会话识别学生本人。
export const getMyWrongQuestionsAPI = (exam) => {
  return request({ url: '/api/me/wrong-questions', params: { exam } })
}
