<script setup>
import { onMounted, ref } from 'vue'
import { getAgentConfigAPI, updateAgentConfigAPI } from '@/apis/agent'

const aiKey = ref('')
const autoPrint = ref(false)
const loadingConfig = ref(true)
const configLoaded = ref(false)
const savingConfig = ref(false)
const configMessage = ref('')

onMounted(async () => {
  try {
    const result = await getAgentConfigAPI()
    autoPrint.value = result.data.auto_print
    configLoaded.value = true
  } catch (error) {
    configMessage.value = error.message || '无法读取自动打印设置'
  } finally {
    loadingConfig.value = false
  }
})

async function saveAutoPrint(event) {
  const selected = event.target.value === 'yes'
  savingConfig.value = true
  configMessage.value = ''
  try {
    const result = await updateAgentConfigAPI({ autoPrint: selected })
    autoPrint.value = result.data.auto_print
    configMessage.value = '自动打印设置已保存'
  } catch (error) {
    event.target.value = autoPrint.value ? 'yes' : 'no'
    configMessage.value = error.message || '无法保存自动打印设置'
  } finally {
    savingConfig.value = false
  }
}
</script>

<template>
  <section class="config-card" aria-labelledby="config-title">
    <h1 id="config-title">Agent 配置</h1>
    <p class="description">设置学生端 Agent 的使用方式</p>
    <form @submit.prevent>
      <label for="ai-key">AI Key</label>
      <input
        id="ai-key"
        v-model="aiKey"
        type="password"
        placeholder="请输入 AI Key"
        autocomplete="off"
      />
      <label for="auto-print">是否自动打印</label>
      <select
        id="auto-print"
        :value="configLoaded ? (autoPrint ? 'yes' : 'no') : ''"
        :disabled="!configLoaded || savingConfig"
        @change="saveAutoPrint"
      >
        <option disabled value="">{{ loadingConfig ? '正在读取设置' : '设置不可用' }}</option>
        <option value="yes">是</option>
        <option value="no">否</option>
      </select>
      <p v-if="configMessage" class="config-message" role="status">{{ configMessage }}</p>
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

.config-message {
  margin: -12px 0 0;
  color: #42566d;
  font-size: 13px;
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
