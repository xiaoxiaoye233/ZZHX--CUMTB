import { computed, ref, watch } from 'vue'
import { sendAgentMessageAPI } from '@/apis/agent'

function normalizeMessage(item) {
  if (typeof item === 'string') {
    return { role: 'user', text: item, tag: '' }
  }
  const isAgent = item?.role === 'agent' || item?.role === 'assistant'
  return {
    role: isAgent ? 'agent' : 'user',
    text: String(item?.text ?? item?.content ?? ''),
    tag: item?.tag ?? '',
  }
}

export function useChat(props) {
  const messageInput = ref('')
  const chatHistory = ref([])
  const sending = ref(false)
  const canSend = computed(
    () => !props.disabled && !sending.value && messageInput.value.trim() !== '',
  )

  watch(
    () => props.conversationKey,
    () => {
      chatHistory.value = []
    },
  )

  const messages = computed(() => {
    const preset = (props.autoMessages || [])
      .map(normalizeMessage)
      .filter((item) => item.text.trim() !== '')
    return [...preset, ...chatHistory.value]
  })

  async function sendMessage() {
    if (!canSend.value) return
    const text = messageInput.value.trim()
    chatHistory.value.push({ role: 'user', text, tag: '' })
    messageInput.value = ''

    // 未传入 chatRole 时保持原有本地消息行为
    if (!props.chatRole) return

    sending.value = true
    try {
      const res = await sendAgentMessageAPI({
        role: props.chatRole,
        studentId: props.studentId || undefined,
        sessionId: props.sessionId || 'default',
        message: text,
      })
      const reply = res?.data?.reply || res?.reply || res?.msg || '暂时没有收到回复，请稍后再试。'
      chatHistory.value.push({
        role: 'agent',
        tag: props.chatRole === 'teacher' ? 'AI 教研助手' : 'Agent 老师',
        text: reply,
      })
    } catch (err) {
      chatHistory.value.push({
        role: 'agent',
        tag: '系统提示',
        text: `连接 Agent 失败：${err?.message || '请确认后端服务已用 miniconda3 启动'}`,
      })
    } finally {
      sending.value = false
    }
  }

  return { messageInput, messages, sending, canSend, sendMessage }
}
