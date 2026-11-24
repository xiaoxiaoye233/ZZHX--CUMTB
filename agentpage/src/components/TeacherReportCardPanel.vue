<script setup>
import { onMounted, ref, shallowRef } from 'vue'
import { getTeacherReportCardAPI } from '@/apis/analysis'

const report = shallowRef(null)
const selectedClass = ref('')
const loading = ref(true)
const error = ref('')

async function loadReport(classId = selectedClass.value) {
  selectedClass.value = classId
  loading.value = true
  error.value = ''
  try {
    const { data } = await getTeacherReportCardAPI(classId)
    report.value = data
    selectedClass.value = data.class_id || ''
  } catch (err) {
    error.value = err.message || '加载成绩单失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => loadReport())
</script>

<template>
  <section class="report-panel" aria-label="班级成绩单" :aria-busy="loading">
    <div v-if="report?.classes.length" class="report-toolbar">
      <label for="report-card-class">班级</label>
      <select
        id="report-card-class"
        :value="selectedClass"
        :disabled="loading"
        @change="loadReport($event.target.value)"
      >
        <option v-for="classId in report.classes" :key="classId" :value="classId">
          {{ classId }}
        </option>
      </select>
    </div>
    <p v-if="loading" class="report-state" role="status">正在加载成绩单…</p>
    <div v-else-if="error" class="report-state" role="alert">
      {{ error }}
      <button type="button" @click="loadReport()">重试</button>
    </div>
    <p v-else-if="!report?.students.length" class="report-state">暂无班级成绩</p>
    <div v-else class="report-table-scroll" tabindex="0" aria-label="学生得分表，可左右滚动">
      <table :aria-label="`${selectedClass} 成绩单`">
        <thead>
          <tr>
            <th scope="col" class="student-column">学号</th>
            <th scope="col" class="total-column">总分</th>
            <th
              v-for="(question, index) in report.questions"
              :key="index"
              scope="col"
            >
              <span v-if="question.exam_id" class="exam-label">{{ question.exam_id }}</span>
              {{ question.question_id }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in report.students" :key="student.student_id">
            <th scope="row" class="student-column">{{ student.student_id }}</th>
            <td class="total-column">{{ student.total_score ?? '—' }}</td>
            <td v-for="(score, index) in student.scores" :key="index">{{ score ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.report-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  min-height: 0;
  padding: 16px clamp(10px, 2.5vw, 28px);
}

.report-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #d4d4d4;
  font-size: 14px;
}

.report-toolbar select,
.report-state button {
  padding: 6px 10px;
  border: 1px solid #454545;
  border-radius: 7px;
  background: #292929;
  color: #f5f5f5;
  font: inherit;
}

.report-toolbar select {
  max-width: calc(100% - 3em);
  color-scheme: dark;
}

.report-state {
  margin: 0;
  color: #d4d4d4;
  font-size: 14px;
}

.report-state button {
  margin-left: 6px;
  cursor: pointer;
}

.report-table-scroll {
  min-height: 0;
  overflow: auto;
  border: 1px solid #363636;
  border-radius: 9px;
}

.report-table-scroll:focus-visible {
  outline: 2px solid #a3a3a3;
  outline-offset: 2px;
}

table {
  --student-column-width: 88px;
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  color: #ececec;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

th,
td {
  min-width: 56px;
  padding: 8px 10px;
  border-right: 1px solid #323232;
  border-bottom: 1px solid #323232;
  text-align: center;
}

thead th {
  position: sticky;
  z-index: 2;
  top: 0;
  background: #292929;
  vertical-align: bottom;
}

.exam-label {
  display: block;
  color: #b0b0b0;
  font-size: 11px;
  font-weight: 400;
}

tbody th,
tbody td {
  background: #222;
}

tbody tr:nth-child(even) th,
tbody tr:nth-child(even) td {
  background: #262626;
}

.student-column,
.total-column {
  position: sticky;
  z-index: 1;
}

.student-column {
  box-sizing: border-box;
  left: 0;
  width: var(--student-column-width);
  min-width: var(--student-column-width);
  max-width: var(--student-column-width);
  overflow: hidden;
  text-overflow: ellipsis;
}

.total-column {
  left: var(--student-column-width);
  font-weight: 600;
}

thead .student-column,
thead .total-column {
  z-index: 3;
}
</style>
