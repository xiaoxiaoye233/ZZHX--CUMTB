<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import TeachingWorkspace from '@/components/TeachingWorkspace.vue'
import { useStudentStore } from '@/stores/studentStore'
import { useUserStore } from '@/stores/userStore'

defineOptions({ name: 'StudentView' })

const route = useRoute()
const studentStore = useStudentStore()
const userStore = useUserStore()
const { chatHistory, historyLoading, loginResult } = storeToRefs(studentStore)

const currentStudentId = computed(() =>
  String(route.params.id || route.query.student_id || userStore.studentId || 'D01')
    .trim()
    .toUpperCase(),
)

const currentLogin = computed(() =>
  loginResult.value?.studentId === currentStudentId.value ? loginResult.value : null,
)

const initialMessages = computed(() => {
  const advice = currentLogin.value?.advice
  if (historyLoading.value || !advice || chatHistory.value.some((message) => message.id === advice.id)) {
    return chatHistory.value
  }
  return [...chatHistory.value, advice]
})

const printMessages = {
  submitted: '学情报告已提交打印',
  print_failed: '学情报告已保存',
  already_generated: '学情报告已就绪',
  in_progress: '学情报告生成中',
  advice_failed: '报告建议生成失败',
}

const statusHint = computed(() => {
  const login = currentLogin.value
  if (!login) return ''
  const adviceStatus = login.adviceLoading
    ? '个性化建议生成中'
    : login.adviceFailed ? '暂时无法生成个性化建议' : ''
  return [adviceStatus, printMessages[login.printStatus]].filter(Boolean).join(' · ')
})

watch(currentStudentId, (studentId) => studentStore.fetchStudentPageData(studentId), { immediate: true })
</script>

<template>
  <TeachingWorkspace
    role="student"
    :student-id="currentStudentId"
    :initial-messages="initialMessages"
    :initial-loading="historyLoading || currentLogin?.adviceLoading"
    :status-hint="statusHint"
  />
</template>
