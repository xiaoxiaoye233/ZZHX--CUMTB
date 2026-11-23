<script setup>
import { ref } from 'vue'

const tone = ref('')
const aiKey = ref('')
const autoPrint = ref('')
</script>

<template>
  <section class="config-card" aria-labelledby="config-title">
    <h1 id="config-title">Agent 配置</h1>
    <p class="description">设置学生端 Agent 的使用方式</p>
    <form @submit.prevent>
      <label for="agent-tone">学生端 Agent 语气</label>
      <select id="agent-tone" v-model="tone">
        <option disabled value="">请选择语气</option>
        <option value="gentle">温柔</option>
        <option value="serious">严肃</option>
        <option value="concise">言简意赅</option>
      </select>
      <label for="ai-key">AI Key</label>
      <input
        id="ai-key"
        v-model="aiKey"
        type="password"
        placeholder="请输入 AI Key"
        autocomplete="off"
      />
      <label for="auto-print">是否自动打印</label>
      <select id="auto-print" v-model="autoPrint">
        <option disabled value="">请选择</option>
        <option value="yes">是</option>
        <option value="no">否</option>
      </select>
    </form>
  </section>
</template>

<style scoped>
.config-card {
  width: 100%;
  padding: 40px;
  border: 1px solid #eee8df;
  border-radius: 16px;
  background: #fffefa;
  box-shadow: 0 12px 40px rgba(84, 73, 56, .05);
}

.config-card h1 {
  font-size: 24px;
}

.description {
  margin: 10px 0 28px;
  color: #9299a2;
  font-size: 14px;
}

input,
select {
  display: block;
  min-width: 0;
  width: 100%;
  margin-bottom: 24px;
}

select {
  height: 50px;
  padding: 0 16px;
  border: 1px solid #e8e8e5;
  border-radius: 8px;
  outline: none;
  background: #fbfbf9;
  color: #243c61;
  font: inherit;
}

select:focus {
  border-color: #7891ad;
  box-shadow: 0 0 0 3px rgba(80, 119, 159, .1);
}

form > :last-child {
  margin-bottom: 0;
}

@media (max-width: 520px) {
  .config-card {
    padding: 24px;
  }
}
</style>
