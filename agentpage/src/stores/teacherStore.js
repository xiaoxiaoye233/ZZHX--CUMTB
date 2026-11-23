import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getTeacherOverviewAPI } from '@/apis/analysis'

// 后端未启动时的静态兜底快照（与真实 02_按班级 & 03_按主题 数据同构）
const FALLBACK_TEACHER_OVERVIEW = {
  themes: [
    { theme_id: 'T01', theme_name: '代数式与整式运算' },
    { theme_id: 'T02', theme_name: '方程与方程组' },
    { theme_id: 'T03', theme_name: '不等式与不等式组' },
  ],
  classes: [
    {
      class_name: 'DC01',
      student_count: 21,
      avg_score: 19.9,
      avg_rate: 0.587,
      lowest_theme: {
        theme_id: 'T01',
        theme_name: '代数式与整式运算',
        score: 186,
        full_score: 330,
        rate: 0.5636,
      },
      themes: [
        { theme_id: 'T01', theme_name: '代数式与整式运算', score: 186, full_score: 330, rate: 0.5636 },
        { theme_id: 'T02', theme_name: '方程与方程组', score: 138, full_score: 225, rate: 0.6133 },
        { theme_id: 'T03', theme_name: '不等式与不等式组', score: 94, full_score: 157, rate: 0.5987 },
      ],
    },
    {
      class_name: 'DC02',
      student_count: 19,
      avg_score: 17.21,
      avg_rate: 0.5505,
      lowest_theme: {
        theme_id: 'T02',
        theme_name: '方程与方程组',
        score: 101,
        full_score: 210,
        rate: 0.481,
      },
      themes: [
        { theme_id: 'T01', theme_name: '代数式与整式运算', score: 162, full_score: 273, rate: 0.5934 },
        { theme_id: 'T02', theme_name: '方程与方程组', score: 101, full_score: 210, rate: 0.481 },
        { theme_id: 'T03', theme_name: '不等式与不等式组', score: 64, full_score: 111, rate: 0.5766 },
      ],
    },
  ],
  students: [
    {
      id: 'D01',
      class_name: 'DC01',
      total_score: 18,
      total_full_score: 37,
      total_rate: 0.4865,
      theme_scores: {
        T01: { score: 9, full_score: 18, rate: 0.5 },
        T02: { score: 6, full_score: 11, rate: 0.5455 },
        T03: { score: 3, full_score: 8, rate: 0.375 },
      },
    },
    {
      id: 'D02',
      class_name: 'DC01',
      total_score: 16,
      total_full_score: 44,
      total_rate: 0.3636,
      theme_scores: {
        T01: { score: 8, full_score: 22, rate: 0.3636 },
        T02: { score: 5, full_score: 15, rate: 0.3333 },
        T03: { score: 3, full_score: 7, rate: 0.4286 },
      },
    },
    {
      id: 'D04',
      class_name: 'DC01',
      total_score: 26,
      total_full_score: 44,
      total_rate: 0.5909,
      theme_scores: {
        T01: { score: 12, full_score: 24, rate: 0.5 },
        T02: { score: 4, full_score: 8, rate: 0.5 },
        T03: { score: 10, full_score: 12, rate: 0.8333 },
      },
    },
    {
      id: 'D22',
      class_name: 'DC02',
      total_score: 16,
      total_full_score: 35,
      total_rate: 0.4571,
      theme_scores: {
        T01: { score: 8, full_score: 19, rate: 0.4211 },
        T02: { score: 3, full_score: 11, rate: 0.2727 },
        T03: { score: 5, full_score: 5, rate: 1 },
      },
    },
    {
      id: 'D29',
      class_name: 'DC02',
      total_score: 30,
      total_full_score: 35,
      total_rate: 0.8571,
      theme_scores: {
        T01: { score: 11, full_score: 13, rate: 0.8462 },
        T02: { score: 11, full_score: 14, rate: 0.7857 },
        T03: { score: 8, full_score: 8, rate: 1 },
      },
    },
  ],
}

export const useTeacherStore = defineStore('teacher', () => {
  const themes = ref([])
  const classes = ref([])
  const students = ref([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')

  function applyOverview(payload) {
    themes.value = Array.isArray(payload?.themes) ? payload.themes : []
    classes.value = Array.isArray(payload?.classes) ? payload.classes : []
    students.value = Array.isArray(payload?.students) ? payload.students : []
  }

  async function fetchTeacherOverview({ force = false } = {}) {
    if (loading.value) return
    if (loaded.value && !force) return

    loading.value = true
    error.value = ''

    try {
      const res = await getTeacherOverviewAPI()
      const payload = res?.msg || res?.data || res
      if (payload && Array.isArray(payload.students)) {
        applyOverview(payload)
        loaded.value = true
        return
      }
      applyOverview(FALLBACK_TEACHER_OVERVIEW)
      loaded.value = true
    } catch {
      applyOverview(FALLBACK_TEACHER_OVERVIEW)
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  return {
    themes,
    classes,
    students,
    loading,
    loaded,
    error,
    fetchTeacherOverview,
  }
})
