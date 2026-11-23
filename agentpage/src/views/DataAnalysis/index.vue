<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import TeacherBackLink from '@/components/TeacherBackLink.vue'
import { useTeacherStore } from '@/stores/teacherStore'

defineOptions({ name: 'DataAnalysisView' })

const teacherStore = useTeacherStore()
const { themes, classes, students, loading } = storeToRefs(teacherStore)

const selectedClass = ref('all')
const selectedThemeId = ref('all')
const minRateInput = ref('')
const maxRateInput = ref('')
const activePreset = ref('all')
const sortMode = ref('id') // 'id' | 'score-desc' | 'rate-asc'

const ratePresets = [
  { key: 'all', label: '全部', min: '', max: '' },
  { key: 'lt40', label: '< 40%', min: '0', max: '39.9' },
  { key: '40to60', label: '40% - 60%', min: '40', max: '60' },
  { key: '60to80', label: '60% - 80%', min: '60', max: '80' },
  { key: 'ge80', label: '≥ 80%', min: '80', max: '100' },
]

onMounted(() => {
  teacherStore.fetchTeacherOverview()
})

function formatScore(value) {
  if (value === null || value === undefined) return '—'
  return Number.isInteger(value) ? String(value) : Number(value).toFixed(2).replace(/\.?0+$/, '')
}

function formatRate(rate) {
  if (rate === null || rate === undefined) return '—'
  const pct = rate * 100
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`
}

function getRateClass(rate) {
  if (rate === null || rate === undefined) return 'is-muted'
  if (rate >= 0.8) return 'is-high'
  if (rate < 0.6) return 'is-low'
  return 'is-mid'
}

function getStudentTheme(student, themeId) {
  return student?.theme_scores?.[themeId] || { score: null, full_score: null, rate: null }
}

function getSelectedRate(student) {
  if (selectedThemeId.value === 'all') return student?.total_rate ?? null
  return student?.theme_scores?.[selectedThemeId.value]?.rate ?? null
}

function applyPreset(preset) {
  activePreset.value = preset.key
  minRateInput.value = preset.min
  maxRateInput.value = preset.max
}

function onManualRateInput() {
  activePreset.value = 'custom'
}

function resetFilters() {
  selectedClass.value = 'all'
  selectedThemeId.value = 'all'
  minRateInput.value = ''
  maxRateInput.value = ''
  activePreset.value = 'all'
  sortMode.value = 'id'
}

const classOptions = computed(() => {
  if (classes.value.length) {
    return classes.value.map((c) => ({
      name: c.class_name,
      count: c.student_count,
    }))
  }
  const map = new Map()
  for (const st of students.value) {
    if (!st.class_name) continue
    map.set(st.class_name, (map.get(st.class_name) || 0) + 1)
  }
  return Array.from(map.entries()).map(([name, count]) => ({ name, count }))
})

const classScopedStudents = computed(() => {
  if (selectedClass.value === 'all') return students.value
  return students.value.filter((st) => st.class_name === selectedClass.value)
})

const sheetTitle = computed(() =>
  selectedClass.value === 'all' ? '学生成绩单' : `${selectedClass.value} 班学生成绩单`,
)

const activeThemeLabel = computed(() => {
  if (selectedThemeId.value === 'all') return '总得分率'
  const found = themes.value.find((t) => t.theme_id === selectedThemeId.value)
  return found ? `${found.theme_name}得分率` : '得分率'
})

// 成绩单顶部与底部的统计汇总
const sheetSummary = computed(() => {
  const list = filteredStudents.value
  const validScores = list.map((s) => s.total_score).filter((v) => v !== null && v !== undefined)
  const validFulls = list
    .map((s) => s.total_full_score)
    .filter((v) => v !== null && v !== undefined)

  const sumScore = validScores.reduce((a, b) => a + b, 0)
  const sumFull = validFulls.reduce((a, b) => a + b, 0)
  const avgScore = validScores.length ? sumScore / validScores.length : null
  const avgRate = sumFull > 0 ? sumScore / sumFull : null

  const themeAvgs = {}
  const themeRates = {}
  for (const t of themes.value) {
    let ts = 0
    let tf = 0
    let cnt = 0
    for (const st of list) {
      const cell = getStudentTheme(st, t.theme_id)
      if (cell.score !== null && cell.score !== undefined) {
        ts += cell.score
        cnt += 1
      }
      if (cell.full_score !== null && cell.full_score !== undefined) {
        tf += cell.full_score
      }
    }
    themeAvgs[t.theme_id] = cnt > 0 ? ts / cnt : null
    themeRates[t.theme_id] = tf > 0 ? ts / tf : null
  }

  // 当前班级（或全体）最低得分率主题
  const allRatedThemes = themes.value
    .map((t) => {
      let ts = 0
      let tf = 0
      for (const st of classScopedStudents.value) {
        const cell = getStudentTheme(st, t.theme_id)
        if (cell.score !== null && cell.full_score > 0) {
          ts += cell.score
          tf += cell.full_score
        }
      }
      return { theme_id: t.theme_id, theme_name: t.theme_name, rate: tf > 0 ? ts / tf : null }
    })
    .filter((t) => t.rate !== null)

  const lowestTheme = allRatedThemes.length
    ? [...allRatedThemes].sort((a, b) => a.rate - b.rate)[0]
    : null

  return {
    avgScore,
    avgRate,
    themeAvgs,
    themeRates,
    lowestTheme,
  }
})

const filteredStudents = computed(() => {
  const minVal = minRateInput.value === '' ? null : Number(minRateInput.value)
  const maxVal = maxRateInput.value === '' ? null : Number(maxRateInput.value)
  const hasMin = minVal !== null && Number.isFinite(minVal)
  const hasMax = maxVal !== null && Number.isFinite(maxVal)

  const matched = classScopedStudents.value.filter((student) => {
    if (!hasMin && !hasMax) return true
    const rate = getSelectedRate(student)
    if (rate === null || rate === undefined) return false
    const pct = rate * 100
    if (hasMin && pct < minVal) return false
    if (hasMax && pct > maxVal) return false
    return true
  })

  if (sortMode.value === 'score-desc') {
    return [...matched].sort((a, b) => (b.total_score ?? -1) - (a.total_score ?? -1))
  }
  if (sortMode.value === 'rate-asc') {
    return [...matched].sort((a, b) => {
      const ra = getSelectedRate(a)
      const rb = getSelectedRate(b)
      if (ra === null && rb === null) return 0
      if (ra === null) return 1
      if (rb === null) return -1
      return ra - rb
    })
  }
  return matched
})

const hasActiveFilter = computed(
  () =>
    selectedClass.value !== 'all' ||
    selectedThemeId.value !== 'all' ||
    minRateInput.value !== '' ||
    maxRateInput.value !== '' ||
    sortMode.value !== 'id',
)
</script>

<template>
  <main class="role-content details-page">
    <TeacherBackLink />

    <section class="transcript-sheet" aria-labelledby="sheet-title">
      <div class="sheet-top-bar" aria-hidden="true"></div>

      <!-- 成绩单表头 -->
      <header class="sheet-header">
        <p class="sheet-org">中国矿业大学（北京） · 智能教学学情统计</p>
        <h1 id="sheet-title">{{ sheetTitle }}</h1>

        <!-- 成绩单概要信息条 -->
        <div class="sheet-meta-strip">
          <div class="meta-item">
            <span class="meta-label">统计人数</span>
            <strong class="meta-value">
              {{ filteredStudents.length }} / {{ classScopedStudents.length }} 人
            </strong>
          </div>
          <div class="meta-divider" aria-hidden="true"></div>
          <div class="meta-item">
            <span class="meta-label">平均总分</span>
            <strong class="meta-value">{{ formatScore(sheetSummary.avgScore) }} 分</strong>
          </div>
          <div class="meta-divider" aria-hidden="true"></div>
          <div class="meta-item">
            <span class="meta-label">总得分率</span>
            <strong class="meta-value">{{ formatRate(sheetSummary.avgRate) }}</strong>
          </div>
          <div class="meta-divider" aria-hidden="true"></div>
          <div class="meta-item">
            <span class="meta-label">薄弱主题</span>
            <strong v-if="sheetSummary.lowestTheme" class="meta-value is-low">
              {{ sheetSummary.lowestTheme.theme_name }}（{{
                formatRate(sheetSummary.lowestTheme.rate)
              }}）
            </strong>
            <strong v-else class="meta-value">—</strong>
          </div>
        </div>

        <!-- 班级均分与最低主题一行简报（点击可直接切到对应班级成绩单） -->
        <div v-if="classes.length" class="class-brief-bar">
          <button
            v-for="cls in classes"
            :key="cls.class_name"
            type="button"
            class="class-brief-item"
            :class="{ active: selectedClass === cls.class_name }"
            @click="selectedClass = selectedClass === cls.class_name ? 'all' : cls.class_name"
          >
            <strong>{{ cls.class_name }}</strong>
            均分 {{ formatScore(cls.avg_score) }} 分
            <template v-if="cls.lowest_theme">
              · 最低主题：<em>{{ cls.lowest_theme.theme_name }}</em>
              （{{ formatRate(cls.lowest_theme.rate) }}）
            </template>
          </button>
        </div>
      </header>

      <!-- 成绩单筛选与排序栏 -->
      <div class="sheet-toolbar">
        <div v-if="classOptions.length" class="toolbar-row">
          <span class="tool-label">筛选班级</span>
          <div class="pill-group" role="group" aria-label="按班级筛选成绩单">
            <button
              type="button"
              class="tool-pill"
              :class="{ active: selectedClass === 'all' }"
              @click="selectedClass = 'all'"
            >
              全部班级（{{ students.length }}人）
            </button>
            <button
              v-for="cls in classOptions"
              :key="cls.name"
              type="button"
              class="tool-pill"
              :class="{ active: selectedClass === cls.name }"
              @click="selectedClass = cls.name"
            >
              {{ cls.name }} 班（{{ cls.count }}人）
            </button>
          </div>
        </div>

        <div class="toolbar-row">
          <span class="tool-label">筛选主题</span>
          <div class="pill-group">
            <button
              type="button"
              class="tool-pill"
              :class="{ active: selectedThemeId === 'all' }"
              @click="selectedThemeId = 'all'"
            >
              总得分率
            </button>
            <button
              v-for="theme in themes"
              :key="theme.theme_id"
              type="button"
              class="tool-pill"
              :class="{ active: selectedThemeId === theme.theme_id }"
              @click="selectedThemeId = theme.theme_id"
            >
              {{ theme.theme_name }}
            </button>
          </div>
        </div>

        <div class="toolbar-row">
          <span class="tool-label">得分率</span>
          <div class="rate-row">
            <div class="pill-group">
              <button
                v-for="preset in ratePresets"
                :key="preset.key"
                type="button"
                class="tool-pill soft"
                :class="{ active: activePreset === preset.key }"
                @click="applyPreset(preset)"
              >
                {{ preset.label }}
              </button>
            </div>

            <div class="range-inputs">
              <label class="range-box">
                <input
                  v-model="minRateInput"
                  type="number"
                  min="0"
                  max="100"
                  placeholder="0"
                  @input="onManualRateInput"
                />
                <span>%</span>
              </label>
              <span class="range-sep">~</span>
              <label class="range-box">
                <input
                  v-model="maxRateInput"
                  type="number"
                  min="0"
                  max="100"
                  placeholder="100"
                  @input="onManualRateInput"
                />
                <span>%</span>
              </label>
            </div>

            <div class="sort-group">
              <button
                type="button"
                class="sort-pill"
                :class="{ active: sortMode === 'id' }"
                @click="sortMode = 'id'"
              >
                按学号
              </button>
              <button
                type="button"
                class="sort-pill"
                :class="{ active: sortMode === 'score-desc' }"
                @click="sortMode = 'score-desc'"
              >
                按总分降序
              </button>
              <button
                type="button"
                class="sort-pill"
                :class="{ active: sortMode === 'rate-asc' }"
                @click="sortMode = 'rate-asc'"
              >
                按得分率升序
              </button>
              <button
                v-if="hasActiveFilter"
                type="button"
                class="reset-pill"
                @click="resetFilters"
              >
                重置
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 成绩单主体网格表格 -->
      <div v-if="loading && !students.length" class="sheet-loading" role="status">
        正在加载成绩单...
      </div>

      <div v-else class="sheet-table-wrap">
        <table class="transcript-table">
          <thead>
            <tr>
              <th scope="col" class="col-index">序号</th>
              <th scope="col" class="col-id">学号</th>
              <th scope="col" class="col-class">班级</th>
              <th
                v-for="theme in themes"
                :key="theme.theme_id"
                scope="col"
                class="col-theme"
                :class="{ 'is-selected': selectedThemeId === theme.theme_id }"
              >
                {{ theme.theme_name }}
              </th>
              <th
                scope="col"
                class="col-total"
                :class="{ 'is-selected': selectedThemeId === 'all' }"
              >
                总得分
              </th>
              <th scope="col" class="col-rate">{{ activeThemeLabel }}</th>
            </tr>
          </thead>

          <tbody v-if="filteredStudents.length">
            <tr v-for="(student, idx) in filteredStudents" :key="student.id">
              <td class="col-index">{{ idx + 1 }}</td>
              <td class="col-id">{{ student.id }}</td>
              <td class="col-class">{{ student.class_name || '—' }}</td>
              <td
                v-for="theme in themes"
                :key="theme.theme_id"
                class="col-theme"
                :class="{ 'is-selected': selectedThemeId === theme.theme_id }"
              >
                <template v-if="getStudentTheme(student, theme.theme_id).score !== null">
                  <span class="cell-score">
                    {{ formatScore(getStudentTheme(student, theme.theme_id).score) }}
                  </span>
                  <span
                    class="cell-subrate"
                    :class="getRateClass(getStudentTheme(student, theme.theme_id).rate)"
                  >
                    {{ formatRate(getStudentTheme(student, theme.theme_id).rate) }}
                  </span>
                </template>
                <span v-else class="is-muted">—</span>
              </td>
              <td
                class="col-total"
                :class="{ 'is-selected': selectedThemeId === 'all' }"
              >
                <strong>{{ formatScore(student.total_score) }}</strong>
                <span v-if="student.total_full_score !== null" class="cell-full">
                  / {{ formatScore(student.total_full_score) }}
                </span>
              </td>
              <td class="col-rate">
                <strong :class="getRateClass(getSelectedRate(student))">
                  {{ formatRate(getSelectedRate(student)) }}
                </strong>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr>
              <td :colspan="themes.length + 5" class="empty-row">
                当前筛选条件下暂无符合要求的学生成绩记录
              </td>
            </tr>
          </tbody>

          <tfoot v-if="filteredStudents.length">
            <tr>
              <td colspan="3" class="foot-title">
                {{ selectedClass === 'all' ? '本表' : `${selectedClass} 班` }}平均 / 汇总（共
                {{ filteredStudents.length }} 人）
              </td>
              <td
                v-for="theme in themes"
                :key="theme.theme_id"
                class="col-theme"
                :class="{ 'is-selected': selectedThemeId === theme.theme_id }"
              >
                <span class="cell-score">
                  {{ formatScore(sheetSummary.themeAvgs[theme.theme_id]) }}
                </span>
                <span
                  class="cell-subrate"
                  :class="getRateClass(sheetSummary.themeRates[theme.theme_id])"
                >
                  {{ formatRate(sheetSummary.themeRates[theme.theme_id]) }}
                </span>
              </td>
              <td class="col-total">
                <strong>{{ formatScore(sheetSummary.avgScore) }}</strong>
                <span class="cell-full"> 均分</span>
              </td>
              <td class="col-rate">
                <strong
                  :class="
                    getRateClass(
                      selectedThemeId === 'all'
                        ? sheetSummary.avgRate
                        : sheetSummary.themeRates[selectedThemeId],
                    )
                  "
                >
                  {{
                    formatRate(
                      selectedThemeId === 'all'
                        ? sheetSummary.avgRate
                        : sheetSummary.themeRates[selectedThemeId],
                    )
                  }}
                </strong>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  </main>
</template>

<style scoped>
.details-page {
  padding-top: 24px;
  padding-bottom: 60px;
}

.transcript-sheet {
  position: relative;
  overflow: hidden;
  padding: 34px 36px 36px;
  border: 1px solid #e4dccf;
  border-radius: 14px;
  background: #fffefa;
  box-shadow: 0 14px 44px rgba(84, 73, 56, 0.06);
}

.sheet-top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #203c62 0%, #294e79 68%, #bd5b5a 68%, #bd5b5a 100%);
}

/* 成绩单抬头 */
.sheet-header {
  text-align: center;
  padding-bottom: 20px;
  border-bottom: 2px double #d7cec0;
}

.sheet-org {
  margin: 0;
  color: #8f959d;
  font-size: 12px;
  letter-spacing: 0.14em;
}

.sheet-header h1 {
  margin: 8px 0 18px;
  color: #1c385c;
  font-size: 26px;
  letter-spacing: 0.22em;
}

.sheet-meta-strip {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 14px 22px;
  padding: 12px 18px;
  border: 1px solid #ece5da;
  border-radius: 10px;
  background: #faf7f0;
}

.meta-item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}

.meta-label {
  color: #8a919b;
  font-size: 12.5px;
}

.meta-value {
  color: #203c62;
  font-size: 14.5px;
  font-variant-numeric: tabular-nums;
}

.meta-divider {
  width: 1px;
  height: 16px;
  background: #dfd7ca;
}

.class-brief-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 12px;
}

.class-brief-item {
  width: auto;
  height: auto;
  padding: 4px 12px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: #6b7685;
  font-size: 12.5px;
  font-weight: 400;
  letter-spacing: 0;
  transition: background 0.15s, border-color 0.15s;
}

.class-brief-item:hover {
  border-color: #e4ddd1;
  background: #f8f4ec;
  color: #203c62;
}

.class-brief-item.active {
  border-color: #294e79;
  background: #edf3f9;
  color: #203c62;
}

.class-brief-item strong {
  margin-right: 4px;
  color: #203c62;
}

.class-brief-item em {
  font-style: normal;
  color: #b44b4a;
  font-weight: 600;
}

/* 筛选与排序条 */
.sheet-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 18px 0 16px;
  padding: 14px 16px;
  border: 1px solid #eee7dc;
  border-radius: 10px;
  background: #fbf9f4;
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tool-label {
  width: 62px;
  flex: none;
  color: #707b8a;
  font-size: 12.5px;
  font-weight: 600;
}

.pill-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.rate-row {
  flex: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.tool-pill,
.sort-pill,
.reset-pill {
  width: auto;
  height: 29px;
  padding: 0 11px;
  border: 1px solid #e2dbd0;
  border-radius: 6px;
  background: #fffefa;
  color: #4f6178;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  transition: all 0.15s;
}

.tool-pill:hover,
.sort-pill:hover,
.reset-pill:hover {
  background: #f2ece2;
  color: #203c62;
}

.tool-pill.active {
  border-color: #203c62;
  background: #203c62;
  color: #fff;
}

.tool-pill.soft.active {
  border-color: #bd5b5a;
  background: #bd5b5a;
  color: #fff;
}

.sort-group {
  margin-left: auto;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.sort-pill.active {
  border-color: #294e79;
  background: #edf3f9;
  color: #203c62;
}

.reset-pill {
  border-style: dashed;
  color: #a94443;
}

.range-inputs {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.range-box {
  display: inline-flex;
  align-items: center;
  height: 29px;
  padding: 0 8px;
  border: 1px solid #dfd8cc;
  border-radius: 6px;
  background: #fffefa;
  color: #828b96;
  font-size: 12px;
}

.range-box input {
  width: 44px;
  height: 24px;
  margin: 0;
  padding: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: #203c62;
  font-size: 12.5px;
  font-weight: 600;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.range-sep {
  color: #a8a197;
}

.sheet-loading {
  padding: 56px 0;
  text-align: center;
  color: #8f969f;
  font-size: 14px;
}

/* 经典成绩单网格表格 */
.sheet-table-wrap {
  overflow-x: auto;
  border: 1px solid #d9d0c3;
  border-radius: 8px;
}

.transcript-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
}

.transcript-table th,
.transcript-table td {
  padding: 11px 14px;
  border: 1px solid #e7e0d4;
  text-align: center;
  white-space: nowrap;
}

.transcript-table thead th {
  border-bottom: 2px solid #cfc5b6;
  background: #f4efe6;
  color: #203c62;
  font-size: 13px;
  font-weight: 700;
}

.transcript-table tbody tr:nth-child(even) td {
  background: #fcfaf5;
}

.transcript-table tbody tr:hover td {
  background: #f4f7fb;
}

.transcript-table th.is-selected {
  background: #e7eff8;
  color: #183a66;
}

.transcript-table tbody td.is-selected {
  background: #f5f9fd;
}

.transcript-table tbody tr:hover td.is-selected {
  background: #eaf1fa;
}

.transcript-table tfoot td {
  border-top: 2px solid #cfc5b6;
  background: #f5f0e7;
  color: #203c62;
  font-weight: 700;
}

.col-index {
  width: 58px;
  color: #8c949f;
}

.col-id {
  width: 86px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 700;
  color: #203c62;
}

.col-class {
  width: 86px;
  color: #55677e;
}

.cell-score {
  font-weight: 600;
  color: #203c62;
}

.cell-subrate {
  margin-left: 6px;
  font-size: 11.5px;
  font-weight: 600;
}

.cell-full {
  color: #8c939d;
  font-size: 12px;
  font-weight: 400;
}

.foot-title {
  text-align: left !important;
  padding-left: 18px !important;
}

.is-high {
  color: #256c50;
}

.is-mid {
  color: #294e79;
}

.is-low {
  color: #bd4c4b;
}

.is-muted {
  color: #b5bbc3;
}

.empty-row {
  padding: 40px 16px !important;
  color: #949ba3;
}

@media (max-width: 760px) {
  .transcript-sheet {
    padding: 24px 16px;
  }

  .meta-divider {
    display: none;
  }

  .sort-group {
    margin-left: 0;
  }
}
</style>
