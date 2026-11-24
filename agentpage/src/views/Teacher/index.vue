<script setup>
import { onMounted, ref } from 'vue'
import { getTeacherChatHistoryAPI } from '@/apis/agent'
import TeachingWorkspace from '@/components/TeachingWorkspace.vue'

defineOptions({ name: 'TeacherView' })

const teacherHistory = ref([])
const historyLoading = ref(false)

async function loadTeacherHistory() {
  historyLoading.value = true
  try {
    const res = await getTeacherChatHistoryAPI('default')
    teacherHistory.value = Array.isArray(res?.data) ? res.data : []
  } catch {
    teacherHistory.value = []
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  loadTeacherHistory()
})
</script>

<template>
  <TeachingWorkspace
    role="teacher"
    :initial-messages="teacherHistory"
    :initial-loading="historyLoading"
  />
</template>
