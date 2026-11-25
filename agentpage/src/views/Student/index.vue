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

const statusHint = computed(() => {
  const login = currentLogin.value
  if (!login) return ''
  if (login.adviceLoading) return '个性化建议生成中'
  if (login.adviceFailed) return '暂时无法生成个性化建议'
  return ''
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
