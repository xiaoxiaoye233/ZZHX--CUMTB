<script setup>
import { nextTick, ref, watch } from 'vue'
import { useChat } from '@/composables/useChat'

const props = defineProps({
  title: { type: String, required: true },
  titleId: { type: String, required: true },
  inputId: { type: String, required: true },
  subtitle: { type: String, default: '' },
  emptyText: { type: String, required: true },
  inputLabel: { type: String, default: '输入消息' },
  placeholder: { type: String, default: '输入消息...' },
  disabled: Boolean,
  conversationKey: { type: String, default: '' },
  chatRole: { type: String, default: '' },
  studentId: { type: String, default: '' },
  sessionId: { type: String, default: 'default' },
  autoMessages: { type: Array, default: () => [] },
  loading: Boolean,
  loadingText: { type: String, default: 'Agent 正在生成个性化建议...' },
})

const { messageInput, messages, sending, canSend, sendMessage } = useChat(props)
const messagesRef = ref(null)

watch(
  () => [messages.value.length, sending.value],
  async () => {
    await nextTick()
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  },
)
</script>

<template>
  <section class="chat-card" :aria-labelledby="titleId">
    <div class="chat-header">
      <h2 :id="titleId">{{ title }}</h2>
      <p v-if="subtitle">{{ subtitle }}</p>
    </div>
    <div
      ref="messagesRef"
      class="messages"
      role="log"
      aria-live="polite"
      :aria-labelledby="titleId"
      tabindex="0"
    >
      <div v-if="loading && !messages.length" class="message-row is-agent">
        <div class="message-bubble agent-bubble loading-bubble">
          <span class="agent-tag">{{ chatRole === 'teacher' ? 'AI 教研助手' : 'Agent 老师' }}</span>
          <p class="bubble-text">{{ loadingText }}</p>
        </div>
      </div>
      <p v-else-if="!messages.length" class="empty-chat">{{ emptyText }}</p>
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message-row"
        :class="message.role === 'agent' ? 'is-agent' : 'is-user'"
      >
        <div
          class="message-bubble"
          :class="message.role === 'agent' ? 'agent-bubble' : 'user-bubble'"
        >
          <span v-if="message.role === 'agent' && message.tag" class="agent-tag">
            {{ message.tag }}
          </span>
          <div class="bubble-text">{{ message.text }}</div>
        </div>
      </div>
      <div v-if="sending" class="message-row is-agent">
        <div class="message-bubble agent-bubble loading-bubble">
          <span class="agent-tag">{{ chatRole === 'teacher' ? 'AI 教研助手' : 'Agent 老师' }}</span>
          <p class="bubble-text">正在查阅资料并思考中...</p>
        </div>
      </div>
    </div>
    <form class="composer" @submit.prevent="sendMessage">
      <label class="visually-hidden" :for="inputId">{{ inputLabel }}</label>
      <input
        :id="inputId"
        v-model="messageInput"
        type="text"
        :placeholder="placeholder"
        :disabled="disabled || sending"
      />
      <button type="submit" :disabled="!canSend">{{ sending ? '思考中' : '发送' }}</button>
    </form>
  </section>
</template>

<style scoped>
.chat-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #eee8df;
  border-radius: 18px;
  background: #fffefa;
  box-shadow: 0 12px 40px rgba(84, 73, 56, .055);
}

.chat-header,
.composer {
  flex-shrink: 0;
}

.chat-header {
  padding: 20px 24px;
  border-bottom: 1px solid #f0ece5;
}

.chat-header h2 {
  margin: 0;
  color: #203c62;
  font-size: 16px;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #cfc6b8 #f7f3eb;
  padding: 20px 22px;
}

.messages:focus-visible {
  outline: 2px solid #7891ad;
  outline-offset: -2px;
}

.empty-chat {
  margin: 50px 0 0;
  text-align: center;
  color: #a6a9a7;
  font-size: 13px;
}

.message-row {
  display: flex;
  margin-bottom: 14px;
}

.message-row.is-user {
  justify-content: flex-end;
}

.message-row.is-agent {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 86%;
  padding: 12px 16px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  font-size: 13.5px;
  line-height: 1.7;
}

.user-bubble {
  border-radius: 14px 14px 3px 14px;
  background: #e5edf5;
  color: #294e79;
}

.agent-bubble {
  max-width: 94%;
  border: 1px solid #ede5d8;
  border-radius: 3px 14px 14px 14px;
  background: linear-gradient(180deg, #fdfbf6 0%, #f8f3ea 100%);
  color: #2a405c;
  box-shadow: 0 4px 16px rgba(84, 73, 56, .04);
}

.loading-bubble {
  color: #7c8792;
}

.agent-tag {
  display: inline-flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 2px 9px;
  border-radius: 999px;
  background: #f5e6e3;
  color: #a84d4b;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: .02em;
}

.bubble-text {
  margin: 0;
}

.composer {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 16px;
  border-top: 1px solid #f0ece5;
  background: #fffefa;
}

.composer input {
  flex: 1;
  min-width: 0;
  height: 44px;
  margin: 0;
  padding: 0 14px;
  border: 1px solid #e8e4dc;
  border-radius: 10px;
  outline: none;
  background: #fbfbf9;
  color: #243c61;
  font-size: 14px;
  transition: border-color .2s, box-shadow .2s;
}

.composer input::placeholder {
  color: #b0b5bc;
}

.composer input:focus {
  border-color: #7891ad;
  box-shadow: 0 0 0 3px rgba(80, 119, 159, .1);
}

.composer button {
  width: auto;
  height: 44px;
  flex: none;
  padding: 0 22px;
  border-radius: 10px;
  letter-spacing: .04em;
}

.composer button:disabled {
  opacity: .45;
  cursor: not-allowed;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.teacher-chat,
.student-chat {
  width: 100%;
  height: 100%;
  min-height: 0;
  margin-top: 0;
}

.student-chat .chat-header {
  padding: 22px 24px 18px;
}

.student-chat h2 {
  color: #203c62;
  font-size: 18px;
}

.student-chat .chat-header p {
  margin: 6px 0 0;
  color: #8f969f;
  font-size: 13px;
  line-height: 1.55;
}

.student-chat .empty-chat {
  font-size: 14px;
}

.config-chat {
  min-height: 490px;
  height: min(65vh, 700px);
}

.config-chat .chat-header p {
  margin: 7px 0 0;
  color: #9299a2;
  font-size: 12px;
}

.config-chat .composer input {
  margin-bottom: 0;
}

@media (max-width: 700px) {
  .config-chat {
    min-height: 420px;
  }
}
</style>
