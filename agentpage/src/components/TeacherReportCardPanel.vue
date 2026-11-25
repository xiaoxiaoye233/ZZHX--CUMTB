<script setup>
import { computed, onMounted, ref, shallowRef, watch } from 'vue'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-vue-next'
import { getTeacherReportCardAPI } from '@/apis/analysis'
import StudentReportPanel from '@/components/StudentReportPanel.vue'

const props = defineProps({
  resetSeq: { type: Number, default: 0 },
})

const report = shallowRef(null)
const selectedClass = ref('')
const sortOrder = ref('default') // 'default' | 'descending' | 'ascending'
const viewingStudentId = ref('')
const loading = ref(true)
const error = ref('')

watch(
  () => props.resetSeq,
  () => {
    viewingStudentId.value = ''
  },
)

const ariaSortValue = computed(() => {
  if (sortOrder.value === 'descending') return 'descending'
  if (sortOrder.value === 'ascending') return 'ascending'
  return 'none'
})

const sortedStudents = computed(() => {
  const list = report.value?.students || []
  if (sortOrder.value === 'default') return list

  const direction = sortOrder.value === 'ascending' ? 1 : -1
  return [...list].sort((a, b) => {
    const aHas =
      a.total_score !== null &&
      a.total_score !== undefined &&
      Number.isFinite(Number(a.total_score))
    const bHas =
      b.total_score !== null &&
      b.total_score !== undefined &&
      Number.isFinite(Number(b.total_score))

    // 无总分记录的学生始终排在末尾
    if (!aHas && !bHas) {
      return String(a.student_id).localeCompare(String(b.student_id), 'zh-CN', { numeric: true })
    }
    if (!aHas) return 1
    if (!bHas) return -1

    const diff = Number(a.total_score) - Number(b.total_score)
    if (diff !== 0) return direction * diff
    return String(a.student_id).localeCompare(String(b.student_id), 'zh-CN', { numeric: true })
  })
})

function cycleTotalSort() {
  if (sortOrder.value === 'default') {
    sortOrder.value = 'descending'
  } else if (sortOrder.value === 'descending') {
    sortOrder.value = 'ascending'
  } else {
    sortOrder.value = 'default'
  }
}

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
  <!-- 点击具体学号后：展示该同学的学情报告（不含个性化建议） -->
  <StudentReportPanel
    v-if="viewingStudentId"
    :student-id="viewingStudentId"
    :show-advice="false"
    :show-back="true"
    @back="viewingStudentId = ''"
  />

  <section
    v-show="!viewingStudentId"
    class="report-panel"
    aria-label="班级成绩单"
    :aria-busy="loading"
  >
    <div v-if="report?.classes.length" class="report-toolbar">
      <div class="toolbar-group">
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

      <div class="toolbar-group">
        <label for="report-card-sort">总分排序</label>
        <select
          id="report-card-sort"
          v-model="sortOrder"
          :disabled="loading"
          aria-label="按总分排序"
        >
          <option value="default">默认排序（按学号）</option>
          <option value="descending">总分从高到低</option>
          <option value="ascending">总分从低到高</option>
        </select>
      </div>
    </div>

    <p v-if="loading" class="report-state" role="status">正在加载成绩单…</p>
    <div v-else-if="error" class="report-state" role="alert">
      {{ error }}
      <button type="button" @click="loadReport()">重试</button>
    </div>
    <p v-else-if="!sortedStudents.length" class="report-state">暂无班级成绩</p>
    <div v-else class="report-table-scroll" tabindex="0" aria-label="学生得分表，可左右滚动">
      <table :aria-label="`${selectedClass} 成绩单`">
        <thead>
          <tr>
            <th scope="col" class="student-column">学号</th>
            <th scope="col" class="total-column" :aria-sort="ariaSortValue">
              <button
                type="button"
                class="total-sort-btn"
                :class="{ active: sortOrder !== 'default' }"
                title="点击切换按总分排序"
                @click="cycleTotalSort"
              >
                <span>总分</span>
                <ArrowDown v-if="sortOrder === 'descending'" :size="13" :stroke-width="2.2" />
                <ArrowUp v-else-if="sortOrder === 'ascending'" :size="13" :stroke-width="2.2" />
                <ArrowUpDown v-else :size="13" :stroke-width="1.9" class="sort-idle-icon" />
              </button>
            </th>
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
          <tr v-for="student in sortedStudents" :key="student.student_id">
            <th scope="row" class="student-column">
              <button
                type="button"
                class="student-id-btn"
                :title="`查看 ${student.student_id} 的学情报告`"
                @click="viewingStudentId = student.student_id"
              >
                {{ student.student_id }}
              </button>
            </th>
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
  flex-wrap: wrap;
  gap: 16px;
  color: #d4d4d4;
  font-size: 14px;
}

.toolbar-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.report-toolbar select,
.report-state button {
  width: auto;
  height: auto;
  padding: 6px 10px;
  border: 1px solid #454545;
  border-radius: 7px;
  background: #292929;
  color: #f5f5f5;
  font: inherit;
  letter-spacing: 0;
}

.report-toolbar select {
  color-scheme: dark;
  cursor: pointer;
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

.total-sort-btn {
  width: auto;
  height: auto;
  padding: 2px 6px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  letter-spacing: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.total-sort-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.total-sort-btn.active {
  color: #60a5fa;
}

.sort-idle-icon {
  opacity: 0.6;
}

.student-id-btn {
  width: auto;
  height: auto;
  padding: 2px 8px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #93c5fd;
  font: inherit;
  font-weight: 600;
  letter-spacing: 0;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.student-id-btn:hover {
  background: rgba(59, 130, 246, 0.18);
  color: #dbeafe;
  text-decoration: underline;
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
  min-width: 72px;
  font-weight: 600;
}

thead .student-column,
thead .total-column {
  z-index: 3;
}
</style>
