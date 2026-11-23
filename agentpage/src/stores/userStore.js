import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginAPI, loginDemoAPI } from '@/apis/user'
import {
  getDemoAccount,
  getDemoRole,
  getDemoStudentId,
  setDemoAccount,
  setDemoRole,
  setDemoStudentId,
} from '@/utils/demoSession'

export const useUserStore = defineStore('user', () => {
  const role = ref(null)
  const account = ref('')
  const studentId = ref('')

  function saveSession({ role: nextRole, account: nextAccount, studentId: nextStudentId }) {
    setDemoRole(nextRole)
    setDemoAccount(nextAccount)
    setDemoStudentId(nextStudentId || '')
    role.value = nextRole
    account.value = nextAccount
    studentId.value = nextStudentId || ''
  }

  function restoreRole() {
    role.value = getDemoRole()
    account.value = getDemoAccount() || ''
    studentId.value = getDemoStudentId() || ''
    return role.value
  }

  async function login({ account: accountName, password, remember = false }) {
    const cleanAccount = String(accountName || '').trim()
    const cleanPassword = String(password || '').trim()

    if (!cleanAccount || !cleanPassword) {
      throw new Error('请输入账号和密码')
    }

    try {
      const res = await loginAPI({
        account: cleanAccount,
        password: cleanPassword,
        remember,
      })
      const user = res?.data?.user || res?.data || res?.user || res?.msg || {}
      const nextRole = user.role || 'student'
      const nextAccount = user.account || cleanAccount
      const nextStudentId =
        user.student_id ?? user.studentId ?? (nextRole === 'student' ? nextAccount : '')

      saveSession({
        role: nextRole,
        account: nextAccount,
        studentId: nextStudentId,
      })

      return { role: nextRole, account: nextAccount, studentId: nextStudentId }
    } catch (err) {
      // 后端明确返回账号/密码错误或参数错误时直接提示
      if (err?.status === 400 || err?.status === 401 || err?.status === 403) {
        throw new Error(err.message || '账号或密码错误，请重新输入', { cause: err })
      }

      // 后端未启动时，兼容原演示账号离线体验（教师 123/123、学生 456/456）
      const fallbackRole = loginDemoAPI({ account: cleanAccount, password: cleanPassword })
      if (fallbackRole) {
        const fallbackStudentId = fallbackRole === 'student' ? 'D01' : ''
        saveSession({
          role: fallbackRole,
          account: cleanAccount,
          studentId: fallbackStudentId,
        })
        return { role: fallbackRole, account: cleanAccount, studentId: fallbackStudentId }
      }

      throw new Error('无法连接后端登录服务，请确认 FastAPI 后端已启动', { cause: err })
    }
  }

  return { role, account, studentId, restoreRole, login }
})
