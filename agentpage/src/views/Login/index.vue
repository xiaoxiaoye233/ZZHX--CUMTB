<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'

defineOptions({ name: 'LoginView' })

const router = useRouter()
const userStore = useUserStore()
const account = ref('')
const password = ref('')
const remember = ref(false)
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
      remember: remember.value,
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
  <main class="main-content">
    <div class="login-area">
      <section class="login-card" aria-labelledby="login-title">
        <div class="card-accent"></div>
        <p class="eyebrow">WELCOME BACK <span></span></p>
        <h1 id="login-title">欢迎登录</h1>
        <p class="subtitle">请输入您的账号和密码</p>
        <form @submit.prevent="login">
          <label for="account">账号</label>
          <input id="account" v-model="account" name="account" type="text" placeholder="请输入账号" autocomplete="username" />
          <label for="password">密码</label>
          <input id="password" v-model="password" name="password" type="password" placeholder="请输入密码" autocomplete="current-password" />
          <label class="remember"><input v-model="remember" type="checkbox" name="remember" /> <span>记住密码</span></label>
          <p v-if="error" class="login-error" role="alert">{{ error }}</p>
          <button type="submit" :disabled="submitting">
            {{ submitting ? '登录中...' : '登 录' }} <span aria-hidden="true">→</span>
          </button>
        </form>
        <p class="card-note">账号由学校统一提供</p>
      </section>
    </div>
  </main>
</template>

<style scoped>
.main-content { flex: 1; display: grid; grid-template-columns: 1fr minmax(340px, 430px) .2fr; align-items: center; padding: 70px 0; }
.login-area { grid-column: 2; }
.login-card { position: relative; overflow: hidden; padding: 49px 48px 34px; background: #fffefa; border: 1px solid #eee8df; border-radius: 22px; box-shadow: 0 20px 70px rgba(84,73,56,.08); }
.card-accent { position: absolute; top: 0; left: 48px; width: 46px; height: 4px; background: #bd5b5a; border-radius: 0 0 4px 4px; }
.eyebrow { display: flex; align-items: center; gap: 12px; margin: 0 0 16px; color: #b66b67; font-size: 10px; font-weight: 700; letter-spacing: .19em; }
.eyebrow span { width: 30px; height: 1px; background: #e6c7bf; }
.subtitle { margin: 12px 0 37px; color: #9299a2; font-size: 14px; }
.remember { display: flex; align-items: center; gap: 7px; width: fit-content; margin: 0 0 30px; color: #7c8792; font-size: 13px; cursor: pointer; }
.remember input { width: 15px; height: 15px; margin: 0; accent-color: #31577f; }
button span { position: absolute; right: 20px; font-size: 20px; line-height: 1; font-weight: 400; }
.card-note { margin: 24px 0 0; text-align: center; color: #a6a9a7; font-size: 12px; }
.login-error { margin: -15px 0 16px; color: #b24c4c; font-size: 13px; }
@media (max-width: 850px) { .main-content { grid-template-columns: 1fr minmax(300px, 430px) 1fr; } }
@media (max-width: 520px) { .main-content { display: block; padding: 56px 0; } .login-card { padding: 42px 28px 30px; } .card-accent { left: 28px; } }
</style>
