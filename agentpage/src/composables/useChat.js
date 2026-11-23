import { computed, ref, watch } from 'vue'

function normalizeMessage(item) {
  if (typeof item === 'string') {
    return { role: 'user', text: item, tag: '' }
  }
  return {
    role: item?.role === 'agent' ? 'agent' : 'user',
    text: String(item?.text ?? ''),
    tag: item?.tag ?? '',
  }
}

export function useChat(props) {
  const messageInput = ref('')
  const userMessages = ref([])
  const canSend = computed(() => !props.disabled && messageInput.value.trim() !== '')

  watch(
    () => props.conversationKey,
    () => {
      userMessages.value = []
    },
  )

  const messages = computed(() => {
    const preset = (props.autoMessages || [])
      .map(normalizeMessage)
      .filter((item) => item.text.trim() !== '')
    return [...preset, ...userMessages.value]
  })

  function sendMessage() {
    if (!canSend.value) return
    userMessages.value.push({ role: 'user', text: messageInput.value.trim(), tag: '' })
    messageInput.value = ''
  }

  return { messageInput, messages, canSend, sendMessage }
}
