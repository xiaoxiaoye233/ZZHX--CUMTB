<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { requestStudentReportPrintAPI } from '@/apis/agent'
import AgentChat from '@/components/AgentChat.vue'
import { useStudentStore } from '@/stores/studentStore'
import { useUserStore } from '@/stores/userStore'
import StudentResults from './components/StudentResults.vue'

defineOptions({ name: 'StudentView' })

const route = useRoute()
const studentStore = useStudentStore()
const userStore = useUserStore()
const { chatHistory, adviceLoading } = storeToRefs(studentStore)

const currentStudentId = computed(() =>
  String(route.params.id || route.query.student_id || userStore.studentId || 'D01')
    .trim()
    .toUpperCase(),
)

const printMessage = ref('')
const printMessages = {
  submitted: '学情报告已生成并提交打印',
  print_failed: '学情报告已保存，打印提交失败',
  advice_failed: 'Agent 建议生成失败，本次学情报告暂未生成',
  already_generated: '本次学情报告已生成',
  in_progress: '本次学情报告正在处理',
}

watch(
  currentStudentId,
  (studentId, _, onCleanup) => {
    studentStore.fetchStudentPageData(studentId)
    printMessage.value = ''
    let current = true
    const loadingTimer = window.setTimeout(() => {
      printMessage.value = 'Agent 正在生成个性化建议和学情报告…'
    }, 200)
    onCleanup(() => {
      current = false
      window.clearTimeout(loadingTimer)
    })

    const visitId = Array.from(crypto.getRandomValues(new Uint8Array(16)), (value) =>
      value.toString(16).padStart(2, '0'),
    ).join('')
    requestStudentReportPrintAPI(studentId, visitId)
      .then((result) => {
        if (current) printMessage.value = printMessages[result.data.status] || ''
      })
      .catch((error) => {
        if (current) printMessage.value = error.message || '学情报告自动打印失败'
      })
      .finally(() => window.clearTimeout(loadingTimer))
  },
  { immediate: true },
)
</script>

<template>
  <main class="role-content student-page">
    <div class="page-heading">
      <h1>学生端</h1>
      <p>查看学习情况，与 Agent 老师一起解决问题</p>
      <p v-if="printMessage" role="status">{{ printMessage }}</p>
    </div>

    <div class="student-workspace">
      <section class="results-pane" tabindex="0" aria-label="学习结果">
        <StudentResults />
      </section>
      <div class="chat-pane">
        <AgentChat
          class="student-chat"
          title="Agent 老师答疑"
          title-id="chat-title"
          subtitle="已开启长期会话记忆，历史聊天会自动保存，可随时继续追问"
          input-id="student-chat-input"
          input-label="输入问题"
          placeholder="针对错题或薄弱知识点继续提问..."
          empty-text="在下方输入你的问题，开始对话"
          :conversation-key="currentStudentId"
          chat-role="student"
          :student-id="currentStudentId"
          :auto-messages="chatHistory"
          :loading="adviceLoading"
          loading-text="正在加载长期会话记录或生成个性化建议..."
        />
      </div>
    </div>
  </main>
</template>

<style scoped>
.student-page {
  display: flex;
  flex-direction: column;
  padding-block: 28px;
}

.page-heading {
  flex: none;
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
  flex: 1;
  min-height: 0;
  grid-template-columns: minmax(0, 1.55fr) minmax(340px, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 24px;
}

.results-pane,
.chat-pane {
  min-width: 0;
  min-height: 0;
}

.results-pane {
  overflow: auto;
}

.chat-pane {
  display: flex;
}

@media (max-width: 1100px) {
  .student-workspace {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: max-content clamp(320px, 70vh, 560px);
    grid-template-rows: max-content clamp(320px, 70dvh, 560px);
    align-content: start;
    overflow: auto;
  }

  .results-pane {
    overflow: visible;
  }
}
</style>
