import { computed, ref, watch } from 'vue'
import { sendAgentMessageAPI } from '@/apis/agent'

function normalizeMessage(item) {
  if (typeof item === 'string') {
    return { role: 'user', text: item, tag: '' }
  }
  const isAgent = item?.role === 'agent' || item?.role === 'assistant'
  return {
    id: typeof item?.id === 'string' ? item.id : '',
    role: isAgent ? 'agent' : 'user',
    text: String(item?.text ?? item?.content ?? ''),
    tag: item?.tag ?? '',
  }
}

function makeSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function deriveTitle(messages, fallback = '新聊天') {
  const firstUser = messages.find((m) => m.role === 'user' && m.text.trim())
  if (firstUser) {
    const clean = firstUser.text.trim().replace(/\s+/g, ' ')
    return clean.length > 18 ? `${clean.slice(0, 18)}…` : clean
  }
  const firstAgent = messages.find((m) => m.role === 'agent' && m.text.trim())
  if (firstAgent) {
    return firstAgent.tag?.includes('建议') ? '个性化学习建议' : '历史对话记录'
  }
  return fallback
}

export function useWorkspaceSessions({ chatRole, studentIdRef, initialMessagesRef }) {
  const sessions = ref([])
  const activeSessionId = ref('')
  const messageInput = ref('')
  const sending = ref(false)

  const storageKey = computed(() => {
    const role = chatRole || 'guest'
    const sid = studentIdRef?.value ? String(studentIdRef.value).trim().toUpperCase() : ''
    return sid ? `zjhx-recent-chats:${role}:${sid}` : `zjhx-recent-chats:${role}`
  })

  function persistSessions() {
    try {
      localStorage.setItem(storageKey.value, JSON.stringify(sessions.value))
    } catch {
      // 忽略隐私模式或存储配额异常
    }
  }

  function loadStoredSessions() {
    try {
      const raw = localStorage.getItem(storageKey.value)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed) || !parsed.length) return null
      return parsed
        .filter((item) => item && typeof item === 'object' && item.id)
        .map((item) => ({
          id: String(item.id),
          title: String(item.title || '新聊天'),
          updatedAt: Number(item.updatedAt || Date.now()),
          seeded: Boolean(item.seeded),
          messages: Array.isArray(item.messages)
            ? item.messages.map(normalizeMessage).filter((m) => m.text.trim() !== '')
            : [],
        }))
    } catch {
      return null
    }
  }

  function initForCurrentScope() {
    const stored = loadStoredSessions()
    const serverPreset = (initialMessagesRef?.value || [])
      .map(normalizeMessage)
      .filter((m) => m.text.trim() !== '')

    if (stored && stored.length) {
      sessions.value = stored
      activeSessionId.value = stored[0].id
      return
    }

    if (serverPreset.length) {
      const seededSession = {
        id: makeSessionId(),
        title: deriveTitle(serverPreset, '历史对话记录'),
        updatedAt: Date.now(),
        seeded: true,
        messages: serverPreset,
      }
      sessions.value = [seededSession]
      activeSessionId.value = seededSession.id
      persistSessions()
      return
    }

    const blank = {
      id: makeSessionId(),
      title: '新聊天',
      updatedAt: Date.now(),
      seeded: true,
      messages: [],
    }
    sessions.value = [blank]
    activeSessionId.value = blank.id
  }

  watch(
    storageKey,
    () => {
      initForCurrentScope()
    },
    { immediate: true },
  )

  // 空会话载入历史。已有学生会话按登录编号补入新建议。
  watch(
    () => initialMessagesRef?.value,
    (incoming) => {
      const normalized = (incoming || [])
        .map(normalizeMessage)
        .filter((m) => m.text.trim() !== '')
      if (!normalized.length) return

      if (
        sessions.value.length === 1 &&
        sessions.value[0].seeded &&
        sessions.value[0].messages.length === 0
      ) {
        sessions.value[0].messages = normalized
        sessions.value[0].title = deriveTitle(normalized, '历史对话记录')
        sessions.value[0].updatedAt = Date.now()
        persistSessions()
        return
      }

      if (chatRole !== 'student' || !activeSession.value) return
      const knownIds = new Set(sessions.value.flatMap((session) => session.messages.map((message) => message.id)))
      const newAdvice = normalized.filter((message) => message.id && !knownIds.has(message.id))
      if (!newAdvice.length) return

      activeSession.value.messages.push(...newAdvice)
      activeSession.value.updatedAt = Date.now()
      if (activeSession.value.title === '新聊天') {
        activeSession.value.title = deriveTitle(activeSession.value.messages)
      }
      persistSessions()
    },
    { deep: true },
  )

  const activeSession = computed(
    () => sessions.value.find((s) => s.id === activeSessionId.value) || sessions.value[0] || null,
  )

  const activeMessages = computed(() => activeSession.value?.messages || [])

  const recentSessions = computed(() => sessions.value)

  const canSend = computed(() => !sending.value && messageInput.value.trim() !== '')

  function createNewChat() {
    const current = activeSession.value
    if (current && current.messages.length === 0) {
      return current.id
    }
    const next = {
      id: makeSessionId(),
      title: '新聊天',
      updatedAt: Date.now(),
      seeded: false,
      messages: [],
    }
    sessions.value = [next, ...sessions.value]
    activeSessionId.value = next.id
    messageInput.value = ''
    persistSessions()
    return next.id
  }

  function selectSession(sessionId) {
    if (!sessionId) return
    activeSessionId.value = sessionId
  }

  async function sendMessage() {
    if (!canSend.value) return
    let target = activeSession.value
    if (!target) {
      createNewChat()
      target = activeSession.value
    }
    if (!target) return

    const text = messageInput.value.trim()
    messageInput.value = ''

    target.messages.push({ role: 'user', text, tag: '' })
    if (target.title === '新聊天' || (target.seeded && target.messages.length === 1)) {
      target.title = deriveTitle(target.messages, '新聊天')
    }
    target.updatedAt = Date.now()

    // 将刚提问的会话置顶到「最近」最上方
    sessions.value = [target, ...sessions.value.filter((item) => item.id !== target.id)]
    persistSessions()

    if (!chatRole) return

    sending.value = true
    try {
      const res = await sendAgentMessageAPI({
        role: chatRole,
        studentId: studentIdRef?.value || undefined,
        // 教师首次会话沿用已有服务端历史，新建会话按各自的 ID 读写。
        sessionId: chatRole === 'teacher' && !target.seeded ? target.id : 'default',
        message: text,
      })
      const reply = res?.data?.reply || res?.reply || res?.msg || '暂时没有收到回复，请稍后再试。'
      target.messages.push({
        role: 'agent',
        tag: chatRole === 'teacher' ? 'AI 教研助手' : 'Agent 老师',
        text: reply,
      })
    } catch (err) {
      target.messages.push({
        role: 'agent',
        tag: '系统提示',
        text: `连接 Agent 失败：${err?.message || '请确认 FastAPI 后端已启动'}`,
      })
    } finally {
      target.updatedAt = Date.now()
      persistSessions()
      sending.value = false
    }
  }

  return {
    sessions,
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
  }
}
