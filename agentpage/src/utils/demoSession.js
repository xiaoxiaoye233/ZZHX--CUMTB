const roleKey = 'demo-role'
const accountKey = 'demo-account'
const studentIdKey = 'demo-student-id'

export function getDemoRole() {
  return sessionStorage.getItem(roleKey)
}

export function setDemoRole(role) {
  sessionStorage.setItem(roleKey, role)
}

export function getDemoAccount() {
  return sessionStorage.getItem(accountKey)
}

export function setDemoAccount(account) {
  sessionStorage.setItem(accountKey, account)
}

export function getDemoStudentId() {
  return sessionStorage.getItem(studentIdKey)
}

export function setDemoStudentId(studentId) {
  if (studentId) {
    sessionStorage.setItem(studentIdKey, studentId)
  } else {
    sessionStorage.removeItem(studentIdKey)
  }
}
