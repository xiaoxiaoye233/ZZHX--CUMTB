<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineOptions({ name: 'AppLayout' })

const route = useRoute()
const isLogin = computed(() => route.name === 'login')
const isWorkspace = computed(() => Boolean(route.meta.fixedWorkspace))
</script>

<template>
  <div
    class="page-shell"
    :class="{
      'page-shell--workspace': isWorkspace,
      'page-shell--login': isLogin,
    }"
  >
    <slot />
  </div>
</template>

<style scoped>
.page-shell { min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; padding: 24px 4.5% 0; }
.page-shell--workspace {
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  background: #141414;
  color: #ececec;
}
.page-shell--login {
  background: #000000;
  color: #e3e3e3;
  padding: 0 20px;
}
@media (max-width: 520px) {
  .page-shell { padding: 14px 16px 0; }
  .page-shell--workspace { padding: 0; }
  .page-shell--login { padding: 0 16px; }
}
</style>
