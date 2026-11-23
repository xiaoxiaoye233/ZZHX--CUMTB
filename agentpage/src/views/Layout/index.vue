<script setup>
import LayoutHeader from './components/LayoutHeader.vue'

defineOptions({ name: 'AppLayout' })
</script>

<template>
  <div class="page-shell">
    <LayoutHeader />
    <slot />
    <footer>中国矿业大学（北京） <span>·</span> 人工智能学院 &amp; 理学院</footer>
  </div>
</template>

<style scoped>
.page-shell { min-height: 100vh; display: flex; flex-direction: column; padding: 24px 4.5% 0; }
footer { padding: 0 0 25px; text-align: center; color: #b2ada5; font-size: 12px; letter-spacing: .04em; }
footer span { margin: 0 5px; }
@media (max-width: 520px) { .page-shell { padding: 14px 16px 0; } }
</style>
