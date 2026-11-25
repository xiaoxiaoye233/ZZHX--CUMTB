<script setup>
import {
   computed,
  defineAsyncComponent,
  nextTick,
  onMounted,
  ref,
  toRef,
  watch,
} from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  ArrowUp,
  BookOpen,
  ClipboardList,
  FileSpreadsheet,
  FileText,
  LogOut,
  MessageSquare,
  Network,
  PanelLeft,
  PanelRight,
  Printer,
  SquarePen,
  Upload,
  User,
} from 'lucide-vue-next'
import { getAgentConfigAPI, updateAgentConfigAPI } from '@/apis/agent'
import { uploadTeacherDataFileAPI } from '@/apis/uploads'
import StudentReportPanel from '@/components/StudentReportPanel.vue'
import StudentTasksPanel from '@/components/StudentTasksPanel.vue'
import TeacherReportCardPanel from '@/components/TeacherReportCardPanel.vue'
import TeacherTasksPanel from '@/components/TeacherTasksPanel.vue'
import TextbookDrawer from '@/components/TextbookDrawer.vue'
import TextbookFinder from '@/components/TextbookFinder.vue'

const KnowledgeGraphPanel = defineAsyncComponent(
  () => import('@/components/KnowledgeGraphPanel.vue'),
)
import { useWorkspaceSessions } from '@/composables/useWorkspaceSessions'
import { useTextbookStore } from '@/stores/textbookStore'
import { useUserStore } from '@/stores/userStore'

const props = defineProps({
  role: { type: String, required: true }, // 'teacher' | 'student'
  studentId: { type: String, default: '' },
  initialMessages: { type: Array, default: () => [] },
  initialLoading: Boolean,
  statusHint: { type: String, default: '' },
})

const router = useRouter()
const userStore = useUserStore()
const textbookStore = useTextbookStore()
const { drawerOpen: textbookOpen, openTabs } = storeToRefs(textbookStore)

const activeSection = ref('chat')
const reportCardResetSeq = ref(0)
const historySidebarOpen = ref(true)
const messagesStreamRef = ref(null)
const composerInputRef = ref(null)

// 教师端「个人详情」里的自动打印滑动开关状态
const autoPrint = ref(localStorage.getItem('zjhx-auto-print') === 'true')
const savingAutoPrint = ref(false)
const autoPrintNotice = ref('')

async function syncAutoPrintFromServer() {
  if (props.role !== 'teacher') return
  try {
    const res = await getAgentConfigAPI()
    if (typeof res?.data?.auto_print === 'boolean') {
      autoPrint.value = res.data.auto_print
      localStorage.setItem('zjhx-auto-print', String(autoPrint.value))
    }
  } catch {
    // 后端未启动或未建立打印会话时沿用本地开关状态
  }
}

async function toggleAutoPrint() {
  if (props.role !== 'teacher' || savingAutoPrint.value) return
  const previous = autoPrint.value
  const nextVal = !previous
  autoPrint.value = nextVal
  localStorage.setItem('zjhx-auto-print', String(nextVal))
  savingAutoPrint.value = true
  autoPrintNotice.value = ''

  try {
    const res = await updateAgentConfigAPI({ autoPrint: nextVal })
    if (typeof res?.data?.auto_print === 'boolean') {
      autoPrint.value = res.data.auto_print
      localStorage.setItem('zjhx-auto-print', String(autoPrint.value))
    }
    autoPrintNotice.value = autoPrint.value ? '已开启自动打印' : '已关闭自动打印'
  } catch (err) {
    if (err?.status === 401 || err?.status === 403) {
      autoPrint.value = previous
      localStorage.setItem('zjhx-auto-print', String(previous))
      autoPrintNotice.value = err.message || '请重新登录教师账号后再修改打印开关'
    } else {
      autoPrintNotice.value = nextVal ? '已开启自动打印（本地预览）' : '已关闭自动打印（本地预览）'
    }
  } finally {
    savingAutoPrint.value = false
  }
}

onMounted(() => {
  syncAutoPrintFromServer()
})

const uploadInput = ref(null)
const uploadStorageKey = `zjhx-teacher-upload-step:${userStore.account}`
const awaitingRecords = ref(
  props.role === 'teacher' && sessionStorage.getItem(uploadStorageKey) === 'records',
)
const uploading = ref(false)
const uploadError = ref(false)
const uploadNotice = ref('')
const uploadFileLabel = computed(() => awaitingRecords.value ? '作答记录' : '模拟学生')

async function uploadTeacherFile(event) {
  const input = event.currentTarget
  const file = input.files?.[0]
  input.value = ''
  if (!file || uploading.value) return

  const step = awaitingRecords.value ? 2 : 1
  const label = uploadFileLabel.value
  if (!file.name.toLowerCase().endsWith('.csv') || file.size === 0) {
    uploadError.value = true
    uploadNotice.value = `请选择非空的「${label}」CSV 文件。`
    return
  }

  uploading.value = true
  uploadError.value = false
  uploadNotice.value = step === 1 ? '正在上传模拟学生…' : '正在上传作答记录并同步学情…'
  try {
    await uploadTeacherDataFileAPI({ file, step })
    awaitingRecords.value = step === 1
    if (awaitingRecords.value) {
      sessionStorage.setItem(uploadStorageKey, 'records')
      uploadNotice.value = '模拟学生已提交，请上传作答记录。'
    } else {
      sessionStorage.removeItem(uploadStorageKey)
      uploadNotice.value = '作答记录已提交，学情数据已更新。'
    }
  } catch (error) {
    uploadError.value = true
    uploadNotice.value = error.message || `${label}上传失败，请重试。`
  } finally {
    uploading.value = false
  }
}

const studentIdRef = toRef(props, 'studentId')
const initialMessagesRef = toRef(props, 'initialMessages')

const {
  recentSessions,
  activeSession,
  activeSessionId,
  activeMessages,
  messageInput,
  sending,
  canSend,
  createNewChat,
  selectSession,
  sendMessage,
} = useWorkspaceSessions({
  chatRole: props.role,
  studentIdRef,
  initialMessagesRef,
})

const topNavItems = computed(() => [
  { key: 'chat', label: '对话', icon: MessageSquare },
  { key: 'textbook', label: '教材', icon: BookOpen },
  { key: 'tasks', label: '任务', icon: ClipboardList },
  ...(props.role === 'teacher'
    ? [{ key: 'report-card', label: '成绩单', icon: FileSpreadsheet }]
    : []),
])

// 从底部向上：个人详情（最底）、知识梳理（倒数第二）；学生端在知识梳理正上方增加「学情报告」
const bottomNavItems = computed(() => [
  ...(props.role === 'student'
    ? [{ key: 'learning-report', label: '学情报告', icon: FileText }]
    : []),
  { key: 'knowledge', label: '知识梳理', icon: Network },
  { key: 'profile', label: '个人详情', icon: User },
])

const headerTitle = computed(() => {
  if (activeSection.value === 'textbook') return '教材'
  if (activeSection.value === 'tasks') return '任务'
  if (activeSection.value === 'report-card') return '成绩单'
  if (activeSection.value === 'learning-report') return '学情报告'
  if (activeSection.value === 'knowledge') return '知识梳理'
  if (activeSection.value === 'profile') return '个人详情'
  return activeSession.value?.title || '新聊天'
})

const displayAccount = computed(() => {
  if (userStore.account) return userStore.account
  return props.role === 'teacher' ? '教师账号' : props.studentId || '学生账号'
})

function handleNavClick(key) {
  if (key === 'report-card') {
    reportCardResetSeq.value += 1
  }
  activeSection.value = key
  if (key === 'profile' && props.role === 'teacher') {
    syncAutoPrintFromServer()
  }
}

function handleNewChat() {
  activeSection.value = 'chat'
  createNewChat()
  nextTick(() => {
    composerInputRef.value?.focus()
  })
}

function handleSelectRecent(sessionId) {
  activeSection.value = 'chat'
  selectSession(sessionId)
}

function handleComposerKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

async function handleLogout() {
  try {
    await userStore.logout()
  } catch {
    // 服务暂不可用时也退出本地工作台。
  }
  router.push({ name: 'login' })
}

watch(
  () => [activeMessages.value.length, sending.value, activeSessionId.value],
  async () => {
    await nextTick()
    if (messagesStreamRef.value) {
      messagesStreamRef.value.scrollTop = messagesStreamRef.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="codex-workspace">
    <!-- 最左侧纯白图标窄栏：顶部向下（对话、教材、任务），底部向上（个人详情、知识梳理） -->
    <nav class="icon-rail" aria-label="主功能导航">
      <div class="rail-group">
        <button
          v-for="item in topNavItems"
          :key="item.key"
          type="button"
          class="rail-btn"
          :class="{ active: activeSection === item.key }"
          :title="item.label"
          :aria-label="item.label"
          @click="handleNavClick(item.key)"
        >
          <component :is="item.icon" :size="19" color="#ffffff" :stroke-width="1.85" />
        </button>
      </div>

      <div class="rail-group rail-bottom">
        <button
          v-for="item in bottomNavItems"
          :key="item.key"
          type="button"
          class="rail-btn"
          :class="{ active: activeSection === item.key }"
          :title="item.label"
          :aria-label="item.label"
          @click="handleNavClick(item.key)"
        >
          <component :is="item.icon" :size="19" color="#ffffff" :stroke-width="1.85" />
        </button>
      </div>
    </nav>

    <!-- 第二列：智教慧学 + 新聊天 + 最近历史聊天 -->
    <aside
      v-show="historySidebarOpen"
      class="history-column"
      aria-label="聊天记录侧栏"
    >
      <div class="brand-header">
        <span class="brand-name">智教慧学</span>
      </div>

      <div class="new-chat-wrap">
        <button type="button" class="new-chat-btn" @click="handleNewChat">
          <SquarePen :size="16" color="#ffffff" :stroke-width="1.85" />
          <span>新聊天</span>
        </button>
      </div>

      <div class="recent-section">
        <div class="recent-label">最近</div>
        <div class="recent-list" role="list">
          <button
            v-for="session in recentSessions"
            :key="session.id"
            type="button"
            class="recent-item"
            :class="{ active: activeSection === 'chat' && session.id === activeSessionId }"
            :title="session.title"
            @click="handleSelectRecent(session.id)"
          >
            <span class="recent-title">{{ session.title }}</span>
            <span
              v-if="activeSection === 'chat' && session.id === activeSessionId"
              class="recent-dot"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </aside>

    <!-- 右侧主体区：聊天主区（或对应图标占位页） + 可展开的浏览器标签式教材侧边栏 -->
    <div class="main-stage">
      <section class="primary-pane">
        <!-- 顶部工具条 -->
        <header class="stage-topbar">
          <div class="topbar-left">
            <button
              type="button"
              class="topbar-icon-btn"
              :title="historySidebarOpen ? '收起会话列表' : '展开会话列表'"
              aria-label="切换会话列表栏"
              @click="historySidebarOpen = !historySidebarOpen"
            >
              <PanelLeft :size="16" color="#ffffff" :stroke-width="1.85" />
            </button>
            <h1 class="stage-title">{{ headerTitle }}</h1>
            <span v-if="statusHint" class="stage-hint">{{ statusHint }}</span>
          </div>

          <div class="topbar-right">
            <button
              type="button"
              class="topbar-textbook-btn"
              :class="{ active: textbookOpen }"
              :title="textbookOpen ? '收起右侧阅读器' : '展开右侧阅读器'"
              @click="textbookStore.toggleDrawer()"
            >
              <PanelRight :size="16" color="#ffffff" :stroke-width="1.85" />
              <span>阅读器{{ openTabs.length ? ` (${openTabs.length})` : '' }}</span>
            </button>
          </div>
        </header>

        <!-- 主体 1：对话界面 -->
        <template v-if="activeSection === 'chat'">
          <div
            ref="messagesStreamRef"
            class="chat-stream"
            role="log"
            aria-live="polite"
            aria-label="对话消息流"
          >
            <div class="chat-stream-inner">
              <div
                v-if="initialLoading && !activeMessages.length"
                class="agent-turn loading-turn"
              >
                <span class="turn-tag">
                  {{ role === 'teacher' ? 'AI 教研助手' : 'Agent 老师' }}
                </span>
                <p class="agent-text">正在加载对话记录与学情建议…</p>
              </div>

              <div v-else-if="!activeMessages.length" class="empty-greeting">
                <p>快来提问吧！</p>
              </div>

              <template v-for="(msg, idx) in activeMessages" :key="idx">
                <div v-if="msg.role === 'user'" class="user-turn">
                  <div class="user-bubble">{{ msg.text }}</div>
                </div>
                <div v-else class="agent-turn">
                  <span v-if="msg.tag" class="turn-tag">{{ msg.tag }}</span>
                  <div class="agent-text">{{ msg.text }}</div>
                  <button
                    v-if="msg.textbookRef?.name"
                    type="button"
                    class="textbook-ref-pill"
                    :title="`打开 ${msg.textbookRef.name} 第 ${msg.textbookRef.page || 1} 页`"
                    @click="textbookStore.openTextbookAtPage(msg.textbookRef)"
                  >
                    <BookOpen :size="13" color="#9ecbff" :stroke-width="1.9" />
                    <span>
                      已定位教材：{{ msg.textbookRef.title || msg.textbookRef.name }}
                      <template v-if="msg.textbookRef.page">
                        · 第 {{ msg.textbookRef.page }} 页
                      </template>
                    </span>
                  </button>
                </div>
              </template>

              <div v-if="sending" class="agent-turn loading-turn">
                <span class="turn-tag">
                  {{ role === 'teacher' ? 'AI 教研助手' : 'Agent 老师' }}
                </span>
                <p class="agent-text">正在查阅资料并思考中…</p>
              </div>
            </div>
          </div>

          <!-- 底部提问栏：只保留输入框与发送键 -->
          <div class="composer-shell">
            <form class="composer-box" @submit.prevent="sendMessage">
              <textarea
                ref="composerInputRef"
                v-model="messageInput"
                class="composer-textarea"
                rows="2"
                placeholder="快来提问吧！"
                aria-label="快来提问吧！"
                :disabled="sending"
                @keydown="handleComposerKeydown"
              />
              <div class="composer-footer">
                <button
                  type="submit"
                  class="send-only-btn"
                  :disabled="!canSend"
                  aria-label="发送"
                  title="发送"
                >
                  <ArrowUp :size="17" color="#ffffff" :stroke-width="2.2" />
                </button>
              </div>
            </form>
          </div>
        </template>

        <!-- 主体 2：教材（仿 macOS 文件夹大图预览，双击打开右侧阅读器侧边栏；教师可管理，学生只读） -->
        <TextbookFinder
          v-else-if="activeSection === 'textbook'"
          :is-teacher="role === 'teacher'"
        />

        <!-- 主体 3：任务（学生端按知识点展示绿/黑底题目；教师端按班级展示黑到绿得分率知识点） -->
        <template v-else-if="activeSection === 'tasks'">
          <TeacherTasksPanel v-if="role === 'teacher'" />
          <StudentTasksPanel v-else :student-id="studentId" />
        </template>

        <TeacherReportCardPanel
          v-else-if="activeSection === 'report-card' && role === 'teacher'"
          :reset-seq="reportCardResetSeq"
        />

        <!-- 学生端学情报告（展示总得分率、各知识点得分率、错题列表与个性化建议，支持右上角下载 PDF） -->
        <StudentReportPanel
          v-else-if="activeSection === 'learning-report' && role === 'student'"
          :student-id="studentId"
        />

        <!-- 主体 4：知识梳理（Cytoscape 开源知识图谱：教师端可交互编辑，学生端可交互探索） -->
        <KnowledgeGraphPanel
          v-else-if="activeSection === 'knowledge'"
          :is-teacher="role === 'teacher'"
        />

        <!-- 主体 4：个人详情（暗黑框架 + 退出登录） -->
        <div v-else-if="activeSection === 'profile'" class="placeholder-stage">
          <div class="placeholder-card profile-card">
            <User :size="28" color="#ffffff" :stroke-width="1.75" />
            <h2>个人详情</h2>
            <div class="profile-meta">
              <div class="meta-row">
                <span>当前身份</span>
                <strong>{{ role === 'teacher' ? '教师端' : '学生端' }}</strong>
              </div>
              <div class="meta-row">
                <span>登录账号</span>
                <strong>{{ displayAccount }}</strong>
              </div>
              <div v-if="role === 'student' && studentId" class="meta-row">
                <span>学生学号</span>
                <strong>{{ studentId }}</strong>
              </div>
              <div v-if="role === 'teacher'" class="meta-row switch-row">
                <span class="switch-label">上传{{ uploadFileLabel }}</span>
                <button
                  type="button"
                  class="teacher-upload-btn"
                  :class="{ 'awaiting-records': awaitingRecords }"
                  :aria-label="`上传${uploadFileLabel}`"
                  :title="`上传${uploadFileLabel}`"
                  :disabled="uploading"
                  @click="uploadInput?.click()"
                >
                  <Upload :size="17" :stroke-width="1.8" aria-hidden="true" />
                </button>
                <input
                  ref="uploadInput"
                  type="file"
                  accept=".csv,text/csv"
                  hidden
                  @change="uploadTeacherFile"
                />
              </div>
              <div v-if="role === 'teacher'" class="meta-row switch-row">
                <span class="switch-label">
                  <Printer :size="15" color="#ffffff" :stroke-width="1.85" />
                  <span>是否自动打印</span>
                </span>
                <button
                  type="button"
                  role="switch"
                  class="print-switch"
                  :class="{ 'is-on': autoPrint }"
                  :aria-checked="autoPrint"
                  :disabled="savingAutoPrint"
                  aria-label="是否自动打印"
                  @click="toggleAutoPrint"
                >
                  <span class="switch-thumb" aria-hidden="true" />
                </button>
              </div>
            </div>
            <p v-if="role === 'teacher' && autoPrintNotice" class="print-notice" role="status">
              {{ autoPrintNotice }}
            </p>
            <p
              v-if="role === 'teacher' && uploadNotice"
              class="upload-notice"
              :class="{ 'upload-error': uploadError }"
              role="status"
            >
              {{ uploadNotice }}
            </p>
            <button type="button" class="logout-btn" @click="handleLogout">
              <LogOut :size="15" color="#ffffff" :stroke-width="1.9" />
              <span>退出登录</span>
            </button>
          </div>
        </div>
      </section>

      <!-- 侧边栏展开：浏览器标签式 PDF 阅读器面板 -->
      <TextbookDrawer v-if="textbookOpen" :is-teacher="role === 'teacher'" />
    </div>
  </div>
</template>

<style scoped>
.codex-workspace {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  display: flex;
  overflow: hidden;
  background: #141414;
  color: #ececec;
}

/* 1. 最左侧图标窄栏 */
.icon-rail {
  width: 50px;
  height: 100%;
  padding: 10px 0 14px;
  background: #121212;
  border-right: 1px solid #222222;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.rail-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.rail-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: 9px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.72;
  cursor: pointer;
  transition: background-color 0.16s ease, opacity 0.16s ease;
}

.rail-btn:hover {
  background: #232323;
  opacity: 1;
}

.rail-btn.active {
  background: #2a2a2a;
  opacity: 1;
}

/* 2. 第二列：智教慧学 + 新聊天 + 最近 */
.history-column {
  width: 244px;
  height: 100%;
  background: #171717;
  border-right: 1px solid #252525;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-width: 0;
}

.brand-header {
  height: 48px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #f5f5f5;
}

.new-chat-wrap {
  padding: 2px 10px 14px;
  flex-shrink: 0;
}

.new-chat-btn {
  width: 100%;
  height: 36px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #ededed;
  font-size: 13.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.new-chat-btn:hover {
  background: #242424;
}

.recent-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 8px 12px;
}

.recent-label {
  padding: 0 8px 8px;
  color: #808080;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.03em;
  flex-shrink: 0;
}

.recent-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  scrollbar-width: thin;
  scrollbar-color: #2f2f2f transparent;
}

.recent-item {
  width: 100%;
  height: 35px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #bdbdbd;
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  text-align: left;
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.14s ease, color 0.14s ease;
}

.recent-item:hover {
  background: #222222;
  color: #f0f0f0;
}

.recent-item.active {
  background: #2a2a2a;
  color: #ffffff;
  font-weight: 500;
}

.recent-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  border: 1.5px solid #a8a8a8;
  flex-shrink: 0;
}

/* 3. 右侧主体舞台 */
.main-stage {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  background: #1e1e1e;
}

.primary-pane {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
}

.stage-topbar {
  height: 48px;
  padding: 0 16px;
  border-bottom: 1px solid #272727;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}

.topbar-left {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar-icon-btn {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.78;
  cursor: pointer;
  flex-shrink: 0;
}

.topbar-icon-btn:hover {
  background: #2b2b2b;
  opacity: 1;
}

.stage-title {
  margin: 0;
  color: #ececec;
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-hint {
  color: #878787;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.topbar-textbook-btn {
  width: auto;
  height: 30px;
  padding: 0 11px;
  border: 1px solid #303030;
  border-radius: 8px;
  background: #252525;
  color: #ededed;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.topbar-textbook-btn:hover,
.topbar-textbook-btn.active {
  background: #303030;
  border-color: #454545;
}

/* 对话消息流 */
.chat-stream {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 28px 24px 16px;
  scrollbar-width: thin;
  scrollbar-color: #363636 transparent;
}

.chat-stream-inner {
  width: 100%;
  max-width: 780px;
  min-height: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.empty-greeting {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #767676;
  font-size: 15px;
  letter-spacing: 0.04em;
}

.empty-greeting p {
  margin: 0;
}

.user-turn {
  display: flex;
  justify-content: flex-end;
}

.user-bubble {
  max-width: min(78%, 540px);
  padding: 10px 16px;
  border-radius: 18px;
  background: #1d4477;
  color: #f3f7fd;
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.agent-turn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.turn-tag {
  color: #8b8b8b;
  font-size: 12px;
  font-weight: 500;
}

.agent-text {
  margin: 0;
  max-width: 100%;
  color: #e8e8e8;
  font-size: 14px;
  line-height: 1.78;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.loading-turn .agent-text {
  color: #969696;
}

/* 底部输入框（仅保留发送键） */
.composer-shell {
  padding: 8px 24px 20px;
  flex-shrink: 0;
}

.composer-box {
  width: 100%;
  max-width: 780px;
  margin: 0 auto;
  padding: 12px 12px 10px 16px;
  border-radius: 18px;
  background: #282828;
  border: 1px solid #383838;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color 0.18s ease;
}

.composer-box:focus-within {
  border-color: #505050;
}

.composer-textarea {
  width: 100%;
  min-height: 44px;
  max-height: 160px;
  padding: 0;
  border: 0;
  outline: none;
  resize: none;
  background: transparent;
  color: #f0f0f0;
  font: inherit;
  font-size: 14px;
  line-height: 1.6;
}

.composer-textarea::placeholder {
  color: #7c7c7c;
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.send-only-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: #2563eb;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.16s ease, opacity 0.16s ease;
}

.send-only-btn:hover:not(:disabled) {
  background: #3b82f6;
}

.send-only-btn:disabled {
  background: #3c3c3c;
  opacity: 0.55;
  cursor: not-allowed;
}

/* 其余图标的暗黑占位面板 */
.placeholder-stage {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 32px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-card {
  width: 100%;
  max-width: 380px;
  padding: 32px 28px;
  border-radius: 16px;
  background: #242424;
  border: 1px solid #323232;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}

.placeholder-card h2 {
  margin: 2px 0 0;
  color: #f2f2f2;
  font-size: 18px;
  font-weight: 600;
}

.placeholder-card p {
  margin: 0;
  color: #8f8f8f;
  font-size: 13.5px;
  line-height: 1.6;
}

.profile-card {
  margin: auto;
  flex-shrink: 0;
}

.profile-meta {
  width: 100%;
  margin-top: 6px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #1b1b1b;
  border: 1px solid #2d2d2d;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #969696;
}

.meta-row strong {
  color: #efefef;
  font-weight: 500;
}

.switch-row {
  padding-top: 8px;
  border-top: 1px solid #292929;
}

.switch-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #dcdcdc;
  font-weight: 500;
}

.print-switch {
  position: relative;
  width: 46px;
  height: 26px;
  padding: 3px;
  border: 1px solid #3f3f46;
  border-radius: 999px;
  background: #2c2c30;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  flex-shrink: 0;
  cursor: pointer;
  transition: background-color 0.24s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.24s ease;
}

.print-switch:hover:not(:disabled) {
  border-color: #52525b;
}

.print-switch.is-on {
  background: #22c55e;
  border-color: #16a34a;
}

.print-switch:disabled {
  opacity: 0.65;
  cursor: wait;
}

.switch-thumb {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.36);
  transform: translateX(0);
  transition: transform 0.24s cubic-bezier(0.4, 0, 0.2, 1);
}

.print-switch.is-on .switch-thumb {
  transform: translateX(20px);
}

.teacher-upload-btn {
  display: grid;
  place-items: center;
  width: 38px;
  height: 34px;
  border: 1px solid #3a3a3a;
  border-radius: 8px;
  background: #242424;
  color: #fff;
  cursor: pointer;
}

.teacher-upload-btn.awaiting-records {
  color: #4ade80;
}

.teacher-upload-btn:hover:not(:disabled) {
  background: #333;
}

.teacher-upload-btn:disabled {
  cursor: wait;
}

.placeholder-card .upload-notice {
  color: #d4d4d4;
  font-size: 12px;
}

.placeholder-card .upload-notice.upload-error {
  color: #fca5a5;
}

.print-notice {
  margin: -2px 0 0;
  color: #4ade80 !important;
  font-size: 12px !important;
}

.logout-btn {
  width: 100%;
  height: 38px;
  margin-top: 8px;
  padding: 0 16px;
  border: 1px solid #3a3a3a;
  border-radius: 10px;
  background: #181818;
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 500;
  letter-spacing: 0.04em;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.logout-btn:hover {
  background: #2c1f1f;
  border-color: #6b3434;
}

.textbook-ref-pill {
  align-self: flex-start;
  width: auto;
  height: 28px;
  margin-top: 6px;
  padding: 0 11px;
  border: 1px solid rgba(10, 132, 255, 0.36);
  border-radius: 999px;
  background: rgba(10, 132, 255, 0.12);
  color: #cfe6ff;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.01em;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.textbook-ref-pill:hover {
  background: rgba(10, 132, 255, 0.24);
  border-color: rgba(59, 158, 255, 0.65);
}

@media (max-width: 760px) {
  .history-column {
    position: fixed;
    top: 0;
    left: 50px;
    bottom: 0;
    z-index: 30;
    box-shadow: 16px 0 40px rgba(0, 0, 0, 0.6);
  }

  .chat-stream,
  .composer-shell {
    padding-inline: 14px;
  }
}
</style>
