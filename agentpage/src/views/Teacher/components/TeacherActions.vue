<script setup>
import { computed, ref } from 'vue'
import { uploadTeacherDataFileAPI } from '@/apis/uploads'
import { useTeacherStore } from '@/stores/teacherStore'

const teacherStore = useTeacherStore()

const uploadStep = ref(1)
const uploading = ref(false)
const progress = ref(0)
const notice = ref('')
const noticeTone = ref('info')

const buttonLabel = computed(() => {
  if (uploading.value) {
    return uploadStep.value === 1
      ? `上传模拟学生 ${progress.value}%`
      : `上传作答记录并运行脚本...`
  }
  return uploadStep.value === 1 ? '导入数据（1/2 模拟学生）' : '导入数据（2/2 作答记录）'
})

const stepHint = computed(() => {
  if (uploadStep.value === 1) {
    return '请依次导入 2 份文件：第 1 次请上传「模拟学生」（将覆盖保存为 模拟学生），第 2 次请上传「作答记录」。'
  }
  return '请继续上传第 2 份文件「作答记录」，全部导入后后端将自动运行数据处理脚本并更新图表。'
})

function resetStep() {
  if (uploading.value) return
  uploadStep.value = 1
  notice.value = '已重置为第 1 步，请先上传「模拟学生」文件。'
  noticeTone.value = 'info'
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const currentStep = uploadStep.value
  uploading.value = true
  progress.value = 0
  notice.value =
    currentStep === 1
      ? `正在上传第 1 份文件「${file.name}」，将保存为「模拟学生」...`
      : `正在上传第 2 份文件「${file.name}」，保存为「作答记录」并自动运行数据处理脚本...`
  noticeTone.value = 'info'

  try {
    const result = await uploadTeacherDataFileAPI({
      file,
      step: currentStep,
      onUploadProgress: (e) => {
        if (e.total) progress.value = Math.round((e.loaded / e.total) * 100)
      },
    })

    if (currentStep === 1) {
      uploadStep.value = 2
      notice.value =
        result?.message ||
        result?.msg ||
        '第 1 步完成：「模拟学生」已替换保存，请继续点击上传第 2 份「作答记录」。'
      noticeTone.value = 'success'
    } else {
      uploadStep.value = 1
      notice.value =
        result?.message ||
        result?.msg ||
        '全部导入完成：「作答记录」已保存，数据处理脚本已运行完毕，数据已更新。'
      noticeTone.value = 'success'
      await teacherStore.fetchTeacherOverview({ force: true })
    }
  } catch (err) {
    const respData = err?.response?.data
    const baseMsg =
      respData?.message ||
      respData?.error?.message ||
      respData?.detail ||
      err?.message ||
      '上传失败，请检查后端服务是否已启动'
    const detailMsg = respData?.data?.error_detail
    notice.value = detailMsg ? `${baseMsg}：${detailMsg}` : baseMsg
    noticeTone.value = 'error'
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}
</script>

<template>
  <div class="teacher-actions">
    <button
      v-open-file="'teacher-data-file'"
      class="import-button"
      :class="{ 'is-step-two': uploadStep === 2 }"
      type="button"
      :disabled="uploading"
    >
      {{ buttonLabel }}
    </button>
    <input
      id="teacher-data-file"
      type="file"
      accept=".csv,.xlsx,.xls"
      hidden
      @change="onFileChange"
    />
    <RouterLink class="config-link" to="/teacher/agent-config">设置 Agent 配置</RouterLink>
    <RouterLink class="config-link" to="/teacher/data-analysis">查看数据详情</RouterLink>

    <div class="upload-guide" :class="`tone-${notice ? noticeTone : 'info'}`" role="status">
      <span class="step-badge">步骤 {{ uploadStep }}/2</span>
      <span class="guide-text">{{ notice || stepHint }}</span>
      <button
        v-if="uploadStep === 2 && !uploading"
        type="button"
        class="reset-link"
        @click="resetStep"
      >
        重新从第 1 步开始
      </button>
    </div>
  </div>
</template>

<style scoped>
.teacher-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.import-button {
  width: auto;
  height: 42px;
  padding: 0 20px;
  letter-spacing: 0.03em;
  transition: background 0.18s;
}

.import-button.is-step-two {
  background: #bd5b5a;
}

.import-button.is-step-two:hover {
  background: #a34847;
}

.import-button:disabled {
  cursor: progress;
  opacity: 0.72;
}

.config-link {
  display: inline-flex;
  align-items: center;
  height: 42px;
  padding: 0 20px;
  border: 1px solid #294e79;
  border-radius: 8px;
  color: #294e79;
  background: #fffefa;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}

.config-link:hover {
  background: #f0f3f5;
}

.upload-guide {
  flex-basis: 100%;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 9px 13px;
  border: 1px solid #ece5da;
  border-radius: 10px;
  background: #faf7f0;
  color: #5b6d85;
  font-size: 12.5px;
  line-height: 1.5;
}

.upload-guide.tone-success {
  border-color: #cde4d9;
  background: #f2faf6;
  color: #25644a;
}

.upload-guide.tone-error {
  border-color: #f0d4d2;
  background: #fdf4f3;
  color: #a94443;
}

.step-badge {
  flex: none;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e7eef6;
  color: #294e79;
  font-size: 11.5px;
  font-weight: 700;
}

.upload-guide.tone-success .step-badge {
  background: #daf0e5;
  color: #206447;
}

.upload-guide.tone-error .step-badge {
  background: #f6dfdc;
  color: #a94443;
}

.guide-text {
  flex: 1;
  min-width: 180px;
}

.reset-link {
  width: auto;
  height: auto;
  padding: 2px 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #294e79;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  text-decoration: underline;
}

.reset-link:hover {
  background: rgba(41, 78, 121, 0.08);
}
</style>
