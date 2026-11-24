<script setup>
import { computed, ref } from 'vue'
import { getStudentChatHistoryAPI } from '@/apis/agent'
import AgentChat from '@/components/AgentChat.vue'
import TeacherBackLink from '@/components/TeacherBackLink.vue'
import AgentSettings from './components/AgentSettings.vue'

defineOptions({ name: 'AgentConfigView' })

const studentInput = ref('')
const selectedStudent = ref('')
const studentHistory = ref([])
const historyLoading = ref(false)
const lookupError = ref('')
const reloadSeq = ref(0)

const chatConversationKey = computed(() =>
  selectedStudent.value ? `${selectedStudent.value}-${reloadSeq.value}` : '',
)

const chatSubtitle = computed(() => {
  if (!selectedStudent.value) {
    return '请输入学生学号并点击确定（如 D01），即可查看并继续使用该同学的长期聊天记录'
  }
  return `当前查看学号：${selectedStudent.value} · 已加载 ${studentHistory.value.length} 条长期记录，可直接继续对话`
})

async function selectStudent() {
  const studentId = studentInput.value.trim().toUpperCase()
  if (!studentId) return
  studentInput.value = studentId

  historyLoading.value = true
  lookupError.value = ''
  studentHistory.value = []

  try {
    const res = await getStudentChatHistoryAPI(studentId)
    selectedStudent.value = studentId
    studentHistory.value = Array.isArray(res?.data) ? res.data : []
    reloadSeq.value += 1
  } catch (err) {
    selectedStudent.value = ''
    studentHistory.value = []
    lookupError.value = err?.message || `未找到学号 ${studentId}，请检查后重试`
  } finally {
    historyLoading.value = false
  }
}
</script>

<template>
  <main class="role-content config-page">
    <TeacherBackLink />
    <div class="split-layout">
      <div class="left-pane">
        <AgentSettings />
      </div>
      <section class="right-pane" aria-label="学生对话">
        <form class="student-form" @submit.prevent="selectStudent">
          <label for="student-id">学号</label>
          <input
            id="student-id"
            v-model="studentInput"
            type="text"
            placeholder="请输入学号，例如 D01"
          />
          <button type="submit" :disabled="historyLoading">
            {{ historyLoading ? '查询中' : '确定' }}
          </button>
        </form>
        <p v-if="lookupError" class="student-error" role="alert">{{ lookupError }}</p>
        <AgentChat
          class="config-chat"
          title="学生与 Agent 长期对话记录"
          title-id="chat-title"
          input-id="chat-input"
          :subtitle="chatSubtitle"
          :empty-text="
            selectedStudent
              ? '该同学暂无历史聊天记录，可在下方直接提问并记入该同学的长期会话'
              : '确认学号后查看并使用该同学的长期聊天记录'
          "
          placeholder="基于该同学的长期会话继续提问..."
          :disabled="!selectedStudent || historyLoading"
          :conversation-key="chatConversationKey"
          chat-role="student"
          :student-id="selectedStudent"
          :auto-messages="studentHistory"
          :loading="historyLoading"
          loading-text="正在加载该同学的长期聊天记录..."
        />
      </section>
    </div>
  </main>
</template>

<style scoped>
.config-page {
  padding-top: 28px;
}

.split-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 560px;
}

.left-pane {
  padding-right: 32px;
}

.right-pane {
  min-width: 0;
  padding-left: 32px;
  border-left: 1px dashed #c9c3b8;
}

.student-form {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 12px;
}

.student-form label {
  flex: none;
  margin: 0;
}

.student-form input {
  flex: 0 1 240px;
  min-width: 0;
  width: 240px;
  height: 40px;
  margin: 0;
  padding: 0 12px;
}

.student-form button {
  width: auto;
  flex: none;
  height: 40px;
  padding: 0 18px;
  letter-spacing: .04em;
}

.student-error {
  margin: 0 0 14px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fdf2f2;
  color: #b54745;
  font-size: 13px;
}

@media (max-width: 700px) {
  .split-layout {
    grid-template-columns: 1fr;
  }

  .left-pane {
    padding: 0 0 28px;
  }

  .right-pane {
    padding: 28px 0 0;
    border-left: 0;
    border-top: 1px dashed #c9c3b8;
  }
}

@media (max-width: 520px) {
  .student-form input {
    flex: 1;
    width: 0;
  }
}
</style>
