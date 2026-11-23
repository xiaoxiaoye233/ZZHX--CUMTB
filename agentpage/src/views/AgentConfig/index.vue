<script setup>
import { ref } from 'vue'
import AgentChat from '@/components/AgentChat.vue'
import TeacherBackLink from '@/components/TeacherBackLink.vue'
import AgentSettings from './components/AgentSettings.vue'

defineOptions({ name: 'AgentConfigView' })

const studentInput = ref('')
const selectedStudent = ref('')

function selectStudent() {
  const student = studentInput.value.trim()
  if (!student) return
  selectedStudent.value = student
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
          <input id="student-id" v-model="studentInput" type="text" placeholder="请输入学号" />
          <button type="submit">确定</button>
        </form>
        <AgentChat
          class="config-chat"
          title="学生与 Agent 对话"
          title-id="chat-title"
          input-id="chat-input"
          :subtitle="selectedStudent ? `学号：${selectedStudent}` : '请先输入并确认学号'"
          :empty-text="selectedStudent ? '暂无对话内容' : '确认学号后开始对话'"
          :disabled="!selectedStudent"
          :conversation-key="selectedStudent"
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
  margin: 0 0 16px;
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
