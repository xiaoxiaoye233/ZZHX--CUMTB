import request from '@/utils/http'

// 教师端两步上传接口：step=1 模拟学生，step=2 作答记录（自动运行 steps 脚本）
export const uploadTeacherDataFileAPI = ({ file, step }) => {
  const data = new FormData()
  data.append('step', String(step))
  data.append('file', file)

  return request({ url: '/api/teacher/upload', method: 'POST', data })
}
