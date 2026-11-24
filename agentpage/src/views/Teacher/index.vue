<script setup>
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { getTeacherChatHistoryAPI } from '@/apis/agent'
import AgentChat from '@/components/AgentChat.vue'
import { useTeacherStore } from '@/stores/teacherStore'
import TeacherActions from './components/TeacherActions.vue'
import TeacherScoreTable from './components/TeacherScoreTable.vue'

defineOptions({ name: 'TeacherView' })

const teacherStore = useTeacherStore()
const { themes, students, loading } = storeToRefs(teacherStore)

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
  teacherStore.fetchTeacherOverview()
  loadTeacherHistory()
})
</script>

<template>
  <main class="role-content split-layout">
    <section class="left-pane" tabindex="0" aria-label="教师操作和成绩表">
      <TeacherActions />
      <section class="analysis-area" aria-labelledby="analysis-title">
        <div class="analysis-header">
          <h2 id="analysis-title">数据分析</h2>
          <span class="analysis-meta">
            共 {{ students.length }} 名学生 · 可横向/纵向滑动查看
          </span>
        </div>
        <TeacherScoreTable
          :themes="themes"
          :students="students"
          :loading="loading"
          max-height="360px"
        />
      </section>
    </section>
    <section class="right-pane">
      <AgentChat
        class="teacher-chat"
        title="与 Agent 对话"
        title-id="teacher-chat-title"
        subtitle="已开启长期会话记忆，可询问学生学情、班级薄弱项或课标授课建议"
        input-id="teacher-chat-input"
        placeholder="例如：DC02班哪个主题最薄弱？结合课标怎么讲？"
        empty-text="输入关于学生、班级或课标授课的问题，开始对话"
        conversation-key="teacher-default"
        chat-role="teacher"
        session-id="default"
        :auto-messages="teacherHistory"
        :loading="historyLoading"
        loading-text="正在加载教师历史聊天记录..."
      />
    </section>
  </main>
</template>

<style scoped>
.role-content {
  padding-block: 28px;
}

.split-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
}

.left-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding-right: 20px;
}

.right-pane {
  display: flex;
  min-width: 0;
  min-height: 0;
  padding-left: 20px;
  border-left: 1px dashed #c9c3b8;
}

.analysis-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
  min-height: 420px;
  padding: 20px 22px;
  border: 1px solid #eee8df;
  border-radius: 14px;
  background: #fffefa;
}

.analysis-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.analysis-area h2 {
  margin: 0;
  color: #344b68;
  font-size: 16px;
  font-weight: 600;
}

.analysis-meta {
  color: #8f969f;
  font-size: 12px;
}

@media (max-width: 700px) {
  .split-layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: max-content clamp(320px, 70vh, 540px);
    grid-template-rows: max-content clamp(320px, 70dvh, 540px);
    align-content: start;
    overflow: auto;
  }

  .left-pane {
    overflow: visible;
    padding-right: 0;
    padding-bottom: 28px;
  }

  .right-pane {
    padding: 28px 0 0;
    border-left: 0;
    border-top: 1px dashed #c9c3b8;
  }
}
</style>
