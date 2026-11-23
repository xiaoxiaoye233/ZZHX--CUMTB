<script setup>
import { computed } from 'vue'

const props = defineProps({
  themes: { type: Array, default: () => [] },
  students: { type: Array, default: () => [] },
  loading: Boolean,
  maxHeight: { type: String, default: '360px' },
  highlightThemeId: { type: String, default: '' },
  showRateColumn: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无学生成绩数据' },
})

const activeThemeName = computed(() => {
  if (!props.highlightThemeId || props.highlightThemeId === 'all') return '总得分率'
  const match = props.themes.find((t) => t.theme_id === props.highlightThemeId)
  return match ? `${match.theme_name}得分率` : '得分率'
})

function formatScore(value) {
  if (value === null || value === undefined) return '—'
  return Number.isInteger(value) ? String(value) : Number(value).toFixed(1)
}

function formatRate(rate) {
  if (rate === null || rate === undefined) return '—'
  const pct = rate * 100
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`
}

function getStudentThemeScore(student, themeId) {
  return student?.theme_scores?.[themeId]?.score ?? null
}

function getTargetRate(student) {
  if (!props.highlightThemeId || props.highlightThemeId === 'all') {
    return student?.total_rate ?? null
  }
  return student?.theme_scores?.[props.highlightThemeId]?.rate ?? null
}

function getRateTone(rate) {
  if (rate === null || rate === undefined) return 'empty'
  if (rate >= 0.8) return 'excellent'
  if (rate >= 0.6) return 'good'
  return 'weak'
}
</script>

<template>
  <div class="table-shell">
    <div v-if="loading && !students.length" class="state-box" role="status">
      正在加载学生数据...
    </div>

    <div
      v-else
      class="table-viewport"
      :style="{ '--table-max-height': maxHeight }"
      tabindex="0"
      aria-label="学生各主题得分与总得分表格，支持横向与纵向滚动"
    >
      <table class="teacher-table">
        <thead>
          <tr>
            <th scope="col" class="col-id sticky-col">ID</th>
            <th scope="col" class="col-class">班级</th>
            <th
              v-for="theme in themes"
              :key="theme.theme_id"
              scope="col"
              class="col-theme"
              :class="{ 'is-highlight': highlightThemeId === theme.theme_id }"
            >
              {{ theme.theme_name }}
            </th>
            <th
              scope="col"
              class="col-total"
              :class="{ 'is-highlight': showRateColumn && highlightThemeId === 'all' }"
            >
              总得分
            </th>
            <th v-if="showRateColumn" scope="col" class="col-rate">
              {{ activeThemeName }}
            </th>
          </tr>
        </thead>
        <tbody v-if="students.length">
          <tr v-for="student in students" :key="student.id">
            <td class="col-id sticky-col">
              <span class="id-chip">{{ student.id }}</span>
            </td>
            <td class="col-class">
              <span class="class-chip">{{ student.class_name || '—' }}</span>
            </td>
            <td
              v-for="theme in themes"
              :key="theme.theme_id"
              class="col-theme"
              :class="{ 'is-highlight': highlightThemeId === theme.theme_id }"
            >
              <span
                class="score-val"
                :class="{ muted: getStudentThemeScore(student, theme.theme_id) === null }"
              >
                {{ formatScore(getStudentThemeScore(student, theme.theme_id)) }}
              </span>
            </td>
            <td
              class="col-total"
              :class="{ 'is-highlight': showRateColumn && highlightThemeId === 'all' }"
            >
              <strong class="total-val">{{ formatScore(student.total_score) }}</strong>
            </td>
            <td v-if="showRateColumn" class="col-rate">
              <div v-if="getTargetRate(student) !== null" class="rate-cell">
                <div class="rate-track" aria-hidden="true">
                  <div
                    class="rate-fill"
                    :class="`fill-${getRateTone(getTargetRate(student))}`"
                    :style="{ width: `${Math.min(100, Math.round(getTargetRate(student) * 100))}%` }"
                  ></div>
                </div>
                <span class="rate-num" :class="`tone-${getRateTone(getTargetRate(student))}`">
                  {{ formatRate(getTargetRate(student)) }}
                </span>
              </div>
              <span v-else class="score-val muted">—</span>
            </td>
          </tr>
        </tbody>
        <tbody v-else>
          <tr>
            <td :colspan="themes.length + (showRateColumn ? 4 : 3)" class="empty-cell">
              {{ emptyText }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.table-shell {
  width: 100%;
  min-width: 0;
}

.state-box {
  padding: 48px 16px;
  text-align: center;
  color: #8f969f;
  font-size: 13.5px;
}

.table-viewport {
  width: 100%;
  max-height: var(--table-max-height, 360px);
  overflow: auto;
  border: 1px solid #ede6db;
  border-radius: 12px;
  background: #fffefa;
  scrollbar-width: thin;
  scrollbar-color: #cfc6b8 #f7f3eb;
}

.table-viewport::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.table-viewport::-webkit-scrollbar-track {
  background: #f7f3eb;
  border-radius: 8px;
}

.table-viewport::-webkit-scrollbar-thumb {
  background: #cfc6b8;
  border-radius: 8px;
}

.table-viewport::-webkit-scrollbar-thumb:hover {
  background: #b5aa9a;
}

.teacher-table {
  width: max-content;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  text-align: left;
  font-size: 13.5px;
}

.teacher-table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 11px 14px;
  border-bottom: 1px solid #e9e2d6;
  background: #f8f4ec;
  color: #5c6c80;
  font-size: 12.5px;
  font-weight: 600;
  white-space: nowrap;
}

.teacher-table thead th.sticky-col {
  left: 0;
  z-index: 4;
  box-shadow: 2px 0 6px rgba(84, 73, 56, 0.05);
}

.teacher-table tbody td {
  padding: 11px 14px;
  border-bottom: 1px solid #f2ede5;
  background: #fffefa;
  color: #293f5c;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.teacher-table tbody td.sticky-col {
  position: sticky;
  left: 0;
  z-index: 1;
  box-shadow: 2px 0 6px rgba(84, 73, 56, 0.04);
}

.teacher-table tbody tr:last-child td {
  border-bottom: 0;
}

.teacher-table tbody tr:hover td {
  background: #faf6ee;
}

.teacher-table th.is-highlight {
  background: #edf3f9;
  color: #203c62;
}

.teacher-table tbody td.is-highlight {
  background: #f6f9fc;
}

.teacher-table tbody tr:hover td.is-highlight {
  background: #edf3f9;
}

.col-id {
  min-width: 78px;
}

.col-class {
  min-width: 82px;
}

.col-theme {
  min-width: 128px;
  text-align: right;
}

.col-total {
  min-width: 88px;
  text-align: right;
}

.col-rate {
  min-width: 146px;
}

.id-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  border: 1px solid #e5dfd5;
  border-radius: 6px;
  background: #faf8f3;
  color: #294e79;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.class-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1ede4;
  color: #4f6178;
  font-size: 12px;
  font-weight: 600;
}

.score-val {
  color: #2c4362;
  font-weight: 500;
}

.score-val.muted {
  color: #b4bac2;
}

.total-val {
  color: #1c385c;
  font-size: 14.5px;
  font-weight: 700;
}

.rate-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rate-track {
  flex: 1;
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: #ebe5dc;
}

.rate-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.35s ease;
}

.fill-excellent {
  background: linear-gradient(90deg, #3f9673 0%, #2b7557 100%);
}

.fill-good {
  background: linear-gradient(90deg, #4b79ad 0%, #294e79 100%);
}

.fill-weak {
  background: linear-gradient(90deg, #d77472 0%, #bd504f 100%);
}

.rate-num {
  width: 44px;
  text-align: right;
  font-size: 12.5px;
  font-weight: 700;
}

.tone-excellent {
  color: #266b4f;
}

.tone-good {
  color: #294e79;
}

.tone-weak {
  color: #b54c4b;
}

.empty-cell {
  padding: 36px 16px;
  text-align: center;
  color: #9ba1a9;
}
</style>
