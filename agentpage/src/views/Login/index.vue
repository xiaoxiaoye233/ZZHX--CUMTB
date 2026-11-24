<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'

defineOptions({ name: 'LoginView' })

const router = useRouter()
const userStore = useUserStore()
const account = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function login() {
  if (submitting.value) return
  submitting.value = true
  error.value = ''

  try {
    const session = await userStore.login({
      account: account.value,
      password: password.value,
    })

    if (session.role === 'student' && session.studentId) {
      router.push({ name: 'student', params: { id: session.studentId } })
      return
    }
    router.push(`/${session.role}`)
  } catch (err) {
    error.value = err?.message || '账号或密码错误，请重新输入'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="gemini-login">
    <div class="login-stack">
      <h1 id="login-title" class="brand-title">智教慧学</h1>

      <form class="login-form" aria-labelledby="login-title" @submit.prevent="login">
        <input
          id="account"
          v-model="account"
          class="field-input"
          name="account"
          type="text"
          aria-label="账号"
          placeholder="账号"
          autocomplete="username"
        />

        <input
          id="password"
          v-model="password"
          class="field-input"
          name="password"
          type="password"
          aria-label="密码"
          placeholder="密码"
          autocomplete="current-password"
        />

        <p v-if="error" class="login-error" role="alert">{{ error }}</p>

        <button class="login-btn" type="submit" :disabled="submitting">
          {{ submitting ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </main>
</template>

<style scoped>
.gemini-login {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000000;
}

.login-stack {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 68px;
  transform: translateY(-16px);
}

.brand-title {
  margin: 0;
  font-size: clamp(50px, 7vw, 72px);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: 0.14em;
  text-indent: 0.14em;
  background: linear-gradient(
    92deg,
    #4285f4 0%,
    #6fa8ff 24%,
    #9b72cb 52%,
    #d96570 78%,
    #f49c6b 100%
  );
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: gemini-flow 6s ease-in-out infinite alternate;
}

.login-form {
  width: 260px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.field-input {
  width: 100%;
  height: 40px;
  margin: 0;
  padding: 0 14px;
  border: 1px solid #2b2d30;
  border-radius: 10px;
  outline: none;
  background: #121315;
  color: #e3e3e3;
  font-size: 14px;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.field-input::placeholder {
  color: #707377;
}

.field-input:hover {
  border-color: #3f4246;
  background: #17181b;
}

.field-input:focus {
  border-color: #8ab4f8;
  background: #121315;
  box-shadow: 0 0 0 3px rgba(138, 180, 248, 0.14);
}

.field-input:-webkit-autofill,
.field-input:-webkit-autofill:hover,
.field-input:-webkit-autofill:focus {
  -webkit-box-shadow: 0 0 0 1000px #121315 inset;
  -webkit-text-fill-color: #e3e3e3;
  caret-color: #e3e3e3;
}

.login-error {
  width: 100%;
  margin: 0;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(242, 139, 130, 0.1);
  border: 1px solid rgba(242, 139, 130, 0.28);
  color: #f28b82;
  font-size: 12px;
  text-align: center;
}

.login-btn {
  width: 112px;
  height: 36px;
  margin-top: 6px;
  padding: 0 20px;
  border: 1px solid #2b2d30;
  border-radius: 10px;
  background: #0b0c0e;
  color: #e3e3e3;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-indent: 0.12em;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, opacity 0.2s ease;
}

.login-btn:hover:not(:disabled) {
  background: #181a1d;
  border-color: #45484d;
  color: #ffffff;
}

.login-btn:active:not(:disabled) {
  background: #101113;
}

.login-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

@keyframes gemini-flow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 100% 50%;
  }
}
</style>
