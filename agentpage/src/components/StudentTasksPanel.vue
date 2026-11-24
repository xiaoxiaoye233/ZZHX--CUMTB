<script setup>
import { computed, ref, watch } from 'vue'
import { CheckCircle2, Circle } from 'lucide-vue-next'
import { getStudentTasksAPI } from '@/apis/analysis'
import { FALLBACK_STUDENT_TASKS } from '@/utils/tasksFallback'

const props = defineProps({
  studentId: { type: String, default: 'D01' },
})

const loading = ref(false)
const taskData = ref(null)
const filterMode = ref('all') // 'all' | 'undone' | 'done'
const expandedQid = ref('')

const indicators = computed(() => taskData.value?.indicators || [])
const totalQuestions = computed(() => taskData.value?.total_questions ?? 0)
const doneQuestions = computed(() => taskData.value?.done_questions ?? 0)

const filteredIndicators = computed(() => {
  if (filterMode.value === 'all') return indicators.value
  return indicators.value
    .map((ind) => ({
      ...ind,
      questions: ind.questions.filter((q) =>
        filterMode.value === 'done' ? q.done : !q.done,
      ),
    }))
    .filter((ind) => ind.questions.length > 0)
})

function formatScoreValue(val) {
  if (val === null || val === undefined) return '—'
  return Number.isInteger(val) ? String(val) : Number(val).toFixed(1).replace(/\.0$/, '')
}

function toggleQuestionExpand(qid) {
  expandedQid.value = expandedQid.value === qid ? '' : qid
}

async function loadTasks() {
  const sid = String(props.studentId || 'D01').trim().toUpperCase() || 'D01'
  loading.value = true
  try {
    const res = await getStudentTasksAPI(sid)
    if (res?.data?.indicators) {
      taskData.value = res.data
      return
    }
    taskData.value = { ...FALLBACK_STUDENT_TASKS, student_id: sid }
  } catch {
    taskData.value = { ...FALLBACK_STUDENT_TASKS, student_id: sid }
  } finally {
    loading.value = false
  }
}

watch(
  () => props.studentId,
  () => {
    loadTasks()
  },
  { immediate: true },
)
</script>

<template>
  <div class="student-tasks-stage">
    <!-- 顶部状态与图例栏 -->
    <div class="tasks-toolbar">
      <div class="toolbar-summary">
        <span class="student-chip">学号 {{ taskData?.student_id || studentId || 'D01' }}</span>
        <span class="progress-text">
          已完成 <strong>{{ doneQuestions }}</strong> / {{ totalQuestions }} 题
        </span>
      </div>

      <div class="toolbar-right">
        <div class="legend-group" aria-label="颜色说明">
          <span class="legend-item">
            <i class="swatch swatch-done" aria-hidden="true" />
            已做（绿底）
          </span>
          <span class="legend-item">
            <i class="swatch swatch-undone" aria-hidden="true" />
            未做（黑底）
          </span>
        </div>

        <div class="filter-pills" role="tablist" aria-label="按完成状态筛选">
          <button
            type="button"
            class="pill-btn"
            :class="{ active: filterMode === 'all' }"
            @click="filterMode = 'all'"
          >
            全部
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ active: filterMode === 'undone' }"
            @click="filterMode = 'undone'"
          >
            未做
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ active: filterMode === 'done' }"
            @click="filterMode = 'done'"
          >
            已做
          </button>
        </div>
      </div>
    </div>

    <!-- 各知识点分组题目列表 -->
    <div class="tasks-scroll">
      <div v-if="loading && !indicators.length" class="tasks-empty">
        正在加载各知识点题目…
      </div>

      <div v-else-if="!filteredIndicators.length" class="tasks-empty">
        当前筛选条件下暂无题目
      </div>

      <div v-else class="kp-sections">
        <section
          v-for="ind in filteredIndicators"
          :key="ind.indicator_id"
          class="kp-block"
          :aria-labelledby="`kp-${ind.indicator_id}`"
        >
          <header class="kp-header">
            <div class="kp-title-wrap">
              <h2 :id="`kp-${ind.indicator_id}`" class="kp-name">{{ ind.indicator_name }}</h2>
              <span v-if="ind.theme_name" class="kp-theme">{{ ind.theme_name }}</span>
            </div>
            <span class="kp-count">
              已做 {{ ind.done_count }} / {{ ind.total_count }} 题
            </span>
          </header>

          <div class="question-grid">
            <article
              v-for="q in ind.questions"
              :key="q.question_id"
              class="question-card"
              :class="[
                q.done ? 'is-done' : 'is-undone',
                { 'is-expanded': expandedQid === q.question_id },
              ]"
              @click="toggleQuestionExpand(q.question_id)"
            >
              <div class="q-top">
                <div class="q-id-group">
                  <CheckCircle2
                    v-if="q.done"
                    :size="14"
                    color="#ffffff"
                    :stroke-width="2"
                  />
                  <Circle
                    v-else
                    :size="14"
                    color="#ffffff"
                    :stroke-width="1.75"
                    class="undone-icon"
                  />
                  <span class="q-type">{{ q.question_type }}</span>
                </div>

                <span class="q-status">
                  <template v-if="q.done && q.score !== null && q.full_score !== null">
                    已做 · {{ formatScoreValue(q.score) }}/{{ formatScoreValue(q.full_score) }}分
                  </template>
                  <template v-else-if="q.done">已做</template>
                  <template v-else>
                    未做{{ q.full_score ? ` · ${formatScoreValue(q.full_score)}分` : '' }}
                  </template>
                </span>
              </div>

              <p class="q-stem">{{ q.stem || '练习题' }}</p>

              <pre
                v-if="q.options && expandedQid === q.question_id"
                class="q-options"
              >{{ q.options }}</pre>
              <span
                v-else-if="q.options"
                class="q-more-hint"
              >
                点击查看选项
              </span>
            </article>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.student-tasks-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
}

.tasks-toolbar {
  padding: 12px 22px;
  background: #222222;
  border-bottom: 1px solid #2d2d2d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  flex-shrink: 0;
}

.toolbar-summary {
  display: flex;
  align-items: center;
  gap: 12px;
}

.student-chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: #2e2e2e;
  border: 1px solid #3c3c3c;
  color: #f0f0f0;
  font-size: 12px;
  font-weight: 600;
}

.progress-text {
  color: #a6a6a6;
  font-size: 13px;
}

.progress-text strong {
  color: #4ade80;
  font-weight: 700;
}

.toolbar-right {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.legend-group {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #a8a8a8;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  display: inline-block;
}

.swatch-done {
  background: #166534;
  border: 1px solid #22c55e;
}

.swatch-undone {
  background: #0b0b0b;
  border: 1px solid #383838;
}

.filter-pills {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: #161616;
  border: 1px solid #303030;
  gap: 2px;
}

.pill-btn {
  width: auto;
  height: 26px;
  padding: 0 11px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #9e9e9e;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
  cursor: pointer;
}

.pill-btn:hover {
  color: #ededed;
}

.pill-btn.active {
  background: #2c2c2c;
  color: #ffffff;
}

.tasks-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px 24px 32px;
  scrollbar-width: thin;
  scrollbar-color: #383838 transparent;
}

.tasks-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #828282;
  font-size: 14px;
}

.kp-sections {
  max-width: 1140px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.kp-block {
  padding: 18px 22px 22px;
  border-radius: 14px;
  background: #181818;
  border: 1px solid #292929;
}

.kp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.kp-title-wrap {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
}

.kp-code {
  padding: 2px 8px;
  border-radius: 6px;
  background: #262626;
  color: #d4d4d4;
  font-size: 11.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.kp-name {
  margin: 0;
  color: #f3f3f3;
  font-size: 14.5px;
  font-weight: 600;
}

.kp-theme {
  color: #7c7c7c;
  font-size: 12px;
}

.kp-count {
  color: #9e9e9e;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.question-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
  gap: 18px 20px;
}

.question-card {
  padding: 10px 12px;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
}

.question-card:hover {
  transform: translateY(-1px);
}

/* 做过的题目：绿色底 */
.question-card.is-done {
  background: #14532d;
  border: 1px solid #228b4e;
  color: #f0fdf4;
}

.question-card.is-done:hover {
  background: #166534;
  border-color: #2eb868;
}

/* 没做过的题目：黑色底 */
.question-card.is-undone {
  background: #0a0a0a;
  border: 1px solid #292929;
  color: #dedede;
}

.question-card.is-undone:hover {
  background: #111111;
  border-color: #3d3d3d;
}

.q-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.q-id-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.undone-icon {
  opacity: 0.48;
}

.q-id {
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.q-type {
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  font-size: 10.5px;
  color: rgba(255, 255, 255, 0.85);
}

.q-status {
  font-size: 11px;
  opacity: 0.88;
  font-variant-numeric: tabular-nums;
}

.q-stem {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: inherit;
  opacity: 0.94;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.question-card.is-expanded .q-stem {
  display: block;
}

.q-options {
  margin: 2px 0 0;
  padding: 8px 10px;
  border-radius: 7px;
  background: rgba(0, 0, 0, 0.28);
  font-family: inherit;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: rgba(255, 255, 255, 0.9);
}

.q-more-hint {
  font-size: 11px;
  opacity: 0.6;
}

@media (max-width: 640px) {
  .tasks-scroll {
    padding: 14px;
  }

  .kp-block {
    padding: 14px;
  }
}
</style>
