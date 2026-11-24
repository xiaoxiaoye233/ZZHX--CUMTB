import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/Login/index.vue'
import TeacherView from '@/views/Teacher/index.vue'
import StudentView from '@/views/Student/index.vue'
import { useUserStore } from '@/stores/userStore'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'login', component: LoginView },
    { path: '/teacher', name: 'teacher', component: TeacherView, meta: { role: 'teacher', fixedWorkspace: true } },
    { path: '/teacher/agent-config', redirect: { name: 'teacher' } },
    { path: '/teacher/data-analysis', redirect: { name: 'teacher' } },
    { path: '/student/:id?', name: 'student', component: StudentView, meta: { role: 'student', fixedWorkspace: true } },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.role) return
  const userStore = useUserStore()
  if ((await userStore.restoreRole()) !== to.meta.role) return { name: 'login' }
})

export default router
