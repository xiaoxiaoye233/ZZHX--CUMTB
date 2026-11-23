<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import AgentChat from '@/components/AgentChat.vue'
import { useStudentStore } from '@/stores/studentStore'
import { useUserStore } from '@/stores/userStore'
import StudentResults from './components/StudentResults.vue'

defineOptions({ name: 'StudentView' })

const route = useRoute()
const studentStore = useStudentStore()
const userStore = useUserStore()
const { agentAdvice, adviceLoading } = storeToRefs(studentStore)

const currentStudentId = computed(() =>
  String(route.params.id || route.query.student_id || userStore.studentId || 'D01'),
)

const agentMessages = computed(() => {
  if (!agentAdvice.value) return []
  return [
    {
      role: 'agent',
      tag: 'Agent 老师 · 个性化建议',
      text: agentAdvice.value,
    },
  ]
})

watch(
  currentStudentId,
  (studentId) => {
    studentStore.fetchStudentPageData(studentId)
  },
  { immediate: true },
)
</script>

<template>
  <main class="role-content student-page">
    <div class="page-heading">
      <h1>学生端</h1>
      <p>查看学习情况，与 Agent 老师一起解决问题</p>
    </div>

    <div class="student-workspace">
      <div class="results-pane">
        <StudentResults />
      </div>
      <div class="chat-pane">
        <AgentChat
          class="student-chat"
          title="Agent 老师答疑"
          title-id="chat-title"
          subtitle="已自动生成个性化学习建议，可随时继续追问"
          input-id="student-chat-input"
          input-label="输入问题"
          placeholder="针对错题或薄弱知识点继续提问..."
          empty-text="在下方输入你的问题，开始对话"
          :conversation-key="currentStudentId"
          :auto-messages="agentMessages"
          :loading="adviceLoading"
          loading-text="正在根据当前成绩生成个性化建议..."
        />
      </div>
    </div>
  </main>
</template>

<style scoped>
.student-page {
  padding-top: 28px;
  padding-bottom: 56px;
}

.page-heading {
  margin-bottom: 24px;
}

.page-heading p {
  margin: 8px 0 0;
  color: #9299a2;
  font-size: 14px;
  line-height: 1.6;
}

.student-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(340px, 1fr);
  gap: 24px;
  align-items: start;
}

.results-pane,
.chat-pane {
  min-width: 0;
}

.chat-pane {
  position: sticky;
  top: 24px;
}

.chat-pane :deep(.student-chat) {
  height: clamp(580px, calc(100vh - 130px), 780px);
  min-height: 580px;
  margin-top: 0;
}

@media (max-width: 1100px) {
  .student-workspace {
    grid-template-columns: 1fr;
  }

  .chat-pane {
    position: static;
  }

  .chat-pane :deep(.student-chat) {
    height: 560px;
    min-height: 480px;
  }
}
</style>
