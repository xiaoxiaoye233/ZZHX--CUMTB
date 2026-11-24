<script setup>
import { computed, onMounted, ref } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { getTeacherTasksAPI } from '@/apis/analysis'
import { FALLBACK_TEACHER_TASKS } from '@/utils/tasksFallback'

const loading = ref(false)
const classes = ref([])
const byClass = ref({})
const selectedClassKey = ref('全年级')
const sortOrder = ref('default')

const currentIndicators = computed(() => {
  const indicators = byClass.value[selectedClassKey.value] || []
  if (sortOrder.value === 'default') return indicators

  const direction = sortOrder.value === 'ascending' ? 1 : -1
  return [...indicators].sort(
    (first, second) => direction * (numericRate(first.score_rate) - numericRate(second.score_rate)),
  )
})

function numericRate(value) {
  const rate = Number(value)
  return Number.isFinite(rate) ? rate : 0
}

function clamp01(value) {
  return Math.min(1, Math.max(0, numericRate(value)))
}

// 平均得分率越高越接近鲜明绿色，越低越接近纯黑色（0% 纯黑 #080808 -> 100% 翠绿 #199e4b）
function getHeatmapCardStyle(rate) {
  const t = clamp01(rate)
  const r = Math.round(8 + 17 * t)
  const g = Math.round(8 + 150 * t)
  const b = Math.round(8 + 67 * t)

  const borderR = Math.round(42 + 24 * t)
  const borderG = Math.round(42 + 158 * t)
  const borderB = Math.round(42 + 72 * t)

  return {
    backgroundColor: `rgb(${r}, ${g}, ${b})`,
    borderColor: `rgb(${borderR}, ${borderG}, ${borderB})`,
  }
}

function formatRatePercent(rate) {
  const pct = numericRate(rate) * 100
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`
}

function formatNum(val) {
  if (val === null || val === undefined) return '—'
  const n = Number(val)
  if (!Number.isFinite(n)) return '—'
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, '')
}

function applyPayload(payload) {
  const clsList = Array.isArray(payload?.classes) ? payload.classes : []
  const mapObj = payload?.by_class && typeof payload.by_class === 'object' ? payload.by_class : {}
  classes.value = clsList
  byClass.value = mapObj
  if (clsList.length && !clsList.some((c) => c.key === selectedClassKey.value)) {
    selectedClassKey.value = clsList[0].key
  }
}

async function fetchTeacherTasks() {
  loading.value = true
  try {
    const res = await getTeacherTasksAPI()
    if (res?.data?.classes?.length) {
      applyPayload(res.data)
      return
    }
    applyPayload(FALLBACK_TEACHER_TASKS)
  } catch {
    applyPayload(FALLBACK_TEACHER_TASKS)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTeacherTasks()
})
</script>

<template>
  <div class="teacher-tasks-stage">
    <!-- 顶部班级切换栏与热力图例 -->
    <div class="teacher-toolbar">
      <div class="class-switcher" role="tablist" aria-label="切换班级">
        <button
          v-for="cls in classes"
          :key="cls.key"
          type="button"
          role="tab"
          :aria-selected="selectedClassKey === cls.key"
          class="class-tab"
          :class="{ active: selectedClassKey === cls.key }"
          @click="selectedClassKey = cls.key"
        >
          <span>{{ cls.label }}</span>
          <span v-if="cls.student_count" class="class-count">{{ cls.student_count }}人</span>
        </button>
      </div>

      <div class="toolbar-right">
        <label class="task-sort">
          <span>排序</span>
          <select v-model="sortOrder" aria-label="按知识点平均得分率排序">
            <option value="default">默认排序</option>
            <option value="descending">从高到低</option>
            <option value="ascending">从低到高</option>
          </select>
        </label>

        <div class="heat-legend" aria-label="得分率颜色图例">
          <span>低 0%</span>
          <i class="heat-gradient-bar" aria-hidden="true" />
          <span>100% 高</span>
        </div>

        <button
          type="button"
          class="refresh-btn"
          title="刷新知识点数据"
          aria-label="刷新知识点数据"
          @click="fetchTeacherTasks"
        >
          <RefreshCw :size="14" color="#ffffff" :stroke-width="1.9" />
        </button>
      </div>
    </div>

    <!-- 主体：各知识点平均得分率热力卡片网格 -->
    <div class="teacher-scroll">
      <div v-if="loading && !currentIndicators.length" class="teacher-empty">
        正在加载班级知识点得分率…
      </div>

      <div v-else-if="!currentIndicators.length" class="teacher-empty">
        暂无该班级的知识点统计数据
      </div>

      <div v-else class="heatmap-wrap">
        <div class="kp-heat-grid">
          <article
            v-for="item in currentIndicators"
            :key="item.indicator_id"
            class="kp-heat-card"
            :style="getHeatmapCardStyle(item.score_rate)"
          >
            <div class="card-top">
              <span v-if="item.theme_name" class="ind-theme">{{ item.theme_name }}</span>
              <span v-else />
              <strong class="rate-figure">{{ formatRatePercent(item.score_rate) }}</strong>
            </div>

            <h3 class="ind-title">{{ item.indicator_name }}</h3>

            <div class="rate-bar-track" aria-hidden="true">
              <div
                class="rate-bar-fill"
                :style="{ width: `${Math.round(clamp01(item.score_rate) * 100)}%` }"
              />
            </div>

            <div class="card-meta">
              <span>得分 {{ formatNum(item.score) }} / {{ formatNum(item.full_score) }}</span>
              <span>作答 {{ item.recorded_students ?? 0 }}/{{ item.student_count ?? 0 }} 人</span>
            </div>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.teacher-tasks-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
}

.teacher-toolbar {
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

.class-switcher {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 3px;
  border-radius: 10px;
  background: #151515;
  border: 1px solid #303030;
  gap: 3px;
}

.class-tab {
  width: auto;
  height: 32px;
  padding: 0 13px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #a3a3a3;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background-color 0.16s ease, color 0.16s ease;
}

.class-tab:hover {
  color: #efefef;
}

.class-tab.active {
  background: #2d2d2d;
  color: #ffffff;
  font-weight: 600;
}

.class-count {
  font-size: 11.5px;
  opacity: 0.72;
}

.toolbar-right {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.task-sort {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #d4d4d4;
  font-size: 13px;
}

.task-sort select {
  min-height: 30px;
  padding: 0 8px;
  border: 1px solid #363636;
  border-radius: 7px;
  background: #2a2a2a;
  color: #efefef;
  color-scheme: dark;
  font: inherit;
}

.heat-legend {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #a6a6a6;
  font-size: 12px;
}

.heat-gradient-bar {
  width: 96px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, #080808 0%, #104e27 50%, #199e4b 100%);
  border: 1px solid #383838;
  display: inline-block;
}

.refresh-btn {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid #363636;
  border-radius: 7px;
  background: #2a2a2a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0.85;
}

.refresh-btn:hover {
  background: #353535;
  opacity: 1;
}

.teacher-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 24px 34px;
  scrollbar-width: thin;
  scrollbar-color: #383838 transparent;
}

.teacher-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #828282;
  font-size: 14px;
}

.heatmap-wrap {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.heatmap-heading h2 {
  margin: 0;
  color: #f3f3f3;
  font-size: 17px;
  font-weight: 600;
}

.heatmap-heading p {
  margin: 6px 0 0;
  color: #8a8a8a;
  font-size: 13px;
}

.kp-heat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(216px, 236px));
  gap: 24px 26px;
}

.kp-heat-card {
  padding: 13px 15px 12px;
  border-width: 1px;
  border-style: solid;
  border-radius: 12px;
  color: #f5f5f5;
  display: flex;
  flex-direction: column;
  gap: 9px;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.32);
  transition: background-color 0.32s ease, border-color 0.32s ease, transform 0.16s ease;
}

.kp-heat-card:hover {
  transform: translateY(-2px);
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.card-badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
}

.ind-code {
  padding: 1.5px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.ind-theme {
  padding: 1.5px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.26);
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
}

.rate-figure {
  font-size: 19px;
  font-weight: 700;
  line-height: 1;
  color: #ffffff;
  font-variant-numeric: tabular-nums;
}

.ind-title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.42;
  color: #ffffff;
  min-height: 38px;
}

.rate-bar-track {
  width: 100%;
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  overflow: hidden;
}

.rate-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  transition: width 0.35s ease;
}

.card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.78);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 640px) {
  .teacher-scroll {
    padding: 14px;
  }
}
</style>
