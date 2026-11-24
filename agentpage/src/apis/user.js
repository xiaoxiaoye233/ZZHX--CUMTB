import request from '@/utils/http'

// 当前页面使用的演示账户。
export const loginDemoAPI = ({ account, password }) => {
  if (account === '123' && password === '123') return 'teacher'
  if (account === '456' && password === '456') return 'student'
  return ''
}

export const loginAPI = ({ account, password, remember = false }) => {
  return request({
    url: '/api/auth/login',
    method: 'POST',
    data: { account, password, remember },
  })
}

export const getSessionAPI = () => {
  return request({ url: '/api/auth/me' })
}

export const logoutAPI = () => {
  return request({ url: '/api/auth/logout', method: 'POST' })
}
