import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/Login/index.vue'
import TeacherView from '@/views/Teacher/index.vue'
import StudentView from '@/views/Student/index.vue'
import AgentConfigView from '@/views/AgentConfig/index.vue'
import DataAnalysisView from '@/views/DataAnalysis/index.vue'
import { useUserStore } from '@/stores/userStore'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'login', component: LoginView },
    { path: '/teacher', name: 'teacher', component: TeacherView, meta: { role: 'teacher' } },
    { path: '/teacher/agent-config', name: 'agent-config', component: AgentConfigView, meta: { role: 'teacher' } },
    { path: '/teacher/data-analysis', name: 'data-analysis', component: DataAnalysisView, meta: { role: 'teacher' } },
    { path: '/student/:id?', name: 'student', component: StudentView, meta: { role: 'student' } },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.role) return
  const userStore = useUserStore()
  if (userStore.restoreRole() !== to.meta.role) return { name: 'login' }
})

export default router
