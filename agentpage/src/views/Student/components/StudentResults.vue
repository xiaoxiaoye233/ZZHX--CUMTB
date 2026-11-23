<script setup>
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStudentStore } from '@/stores/studentStore'

const studentStore = useStudentStore()
const {
  student,
  loading,
  indicators,
  themes,
  scoredIndicators,
  unansweredIndicators,
  totalScore,
  totalFullScore,
  totalLostScore,
  overallRatePercent,
  totalDoneCount,
  totalEligibleCount,
  overallCoveragePercent,
  weakIndicators,
} = storeToRefs(studentStore)

const activeThemeId = ref('all')
const activeFilter = ref('all')
const sortByWeakest = ref(false)
const expandedId = ref('')

watch(
  () => student.value?.id,
  () => {
    activeThemeId.value = 'all'
    activeFilter.value = 'all'
    expandedId.value = ''
  },
)

function formatPercentValue(pct) {
  if (pct === null || pct === undefined) return '—'
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`
}

function getAnswerStatus(item) {
  if (!item.hasRecord) return { key: 'unanswered', label: '未作答' }
  if (item.score >= item.fullScore) return { key: 'perfect', label: '已满分' }
  return { key: 'answered', label: '已作答' }
}

const filterOptions = computed(() => [
  { key: 'all', label: '全部知识点', count: indicators.value.length },
  { key: 'weak', label: '薄弱项 <60%', count: weakIndicators.value.length },
  { key: 'answered', label: '已作答', count: scoredIndicators.value.length },
  { key: 'unanswered', label: '未作答', count: unansweredIndicators.value.length },
])

const visibleIndicators = computed(() => {
  let list = indicators.value

  if (activeThemeId.value !== 'all') {
    list = list.filter((item) => item.themeId === activeThemeId.value)
  }

  if (activeFilter.value === 'weak') {
    list = list.filter((item) => item.hasRecord && item.scoreRate < 0.6)
  } else if (activeFilter.value === 'answered') {
    list = list.filter((item) => item.hasRecord)
  } else if (activeFilter.value === 'unanswered') {
    list = list.filter((item) => !item.hasRecord)
  }

  if (sortByWeakest.value) {
    return [...list].sort((a, b) => {
      if (!a.hasRecord && !b.hasRecord) return 0
      if (!a.hasRecord) return 1
      if (!b.hasRecord) return -1
      return a.scoreRate - b.scoreRate || (b.lostScore ?? 0) - (a.lostScore ?? 0)
    })
  }
  return list
})

const overallTone = computed(() => {
  if (overallRatePercent.value === null) return 'empty'
  if (overallRatePercent.value >= 85) return 'excellent'
  if (overallRatePercent.value >= 60) return 'good'
  return 'weak'
})

const answeredPercent = computed(() => {
  if (!indicators.value.length) return 0
  return Math.round((scoredIndicators.value.length / indicators.value.length) * 1000) / 10
})

// SVG 环形进度条（半径 26）
const RING_RADIUS = 26
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS
const ringDashOffset = computed(() => {
  const pct = overallRatePercent.value ?? 0
  return RING_CIRCUMFERENCE * (1 - Math.min(100, Math.max(0, pct)) / 100)
})

function toggleTheme(themeId) {
  activeThemeId.value = activeThemeId.value === themeId ? 'all' : themeId
}

function toggleExpand(indicatorId) {
  expandedId.value = expandedId.value === indicatorId ? '' : indicatorId
}
</script>

<template>
  <section class="section-card results" aria-labelledby="results-title">
    <div class="card-accent" aria-hidden="true"></div>

    <!-- 顶部标题与学号 -->
    <div class="results-header">
      <div class="section-heading">
        <div class="title-row">
          <h2 id="results-title">成绩展示与错题分析</h2>
          <span v-if="student" class="id-badge">学号 {{ student.id }}</span>
        </div>
        <p class="meta-line">
          按知识主题统计得分率与作答情况，点击任意行可查看教材范围与可补练习题
        </p>
      </div>
    </div>

    <div v-if="loading && !student" class="loading-state" role="status">
      正在加载学生成绩表...
    </div>

    <template v-else-if="student">
      <!-- 双核心统计卡片（前端实时计算） -->
      <div class="summary-grid">
        <article class="metric-card metric-score">
          <div class="score-ring-wrap" aria-hidden="true">
            <svg class="score-ring" viewBox="0 0 64 64">
              <circle class="ring-track" cx="32" cy="32" :r="RING_RADIUS" />
              <circle
                class="ring-progress"
                :class="`tone-${overallTone}`"
                cx="32"
                cy="32"
                :r="RING_RADIUS"
                :stroke-dasharray="RING_CIRCUMFERENCE"
                :stroke-dashoffset="ringDashOffset"
              />
            </svg>
            <span class="ring-value">{{ formatPercentValue(overallRatePercent) }}</span>
          </div>
          <div class="metric-body">
            <span class="metric-label">总成绩 / 总得分率</span>
            <div class="metric-main">
              <strong class="score-big">{{ totalScore }}</strong>
              <span class="score-total">/ {{ totalFullScore }} 分</span>
              <span v-if="totalLostScore > 0" class="lost-pill">-{{ totalLostScore }}</span>
            </div>
            <p class="metric-sub">
              已做 {{ totalDoneCount }}/{{ totalEligibleCount }} 题（总覆盖率
              <strong>{{ formatPercentValue(overallCoveragePercent) }}</strong>）
            </p>
          </div>
        </article>

        <article class="metric-card metric-progress">
          <span class="metric-label">作答情况</span>
          <div class="metric-main">
            <strong class="metric-num">{{ scoredIndicators.length }}</strong>
            <span class="metric-unit">/ {{ indicators.length }} 项知识点已作答</span>
            <span v-if="unansweredIndicators.length" class="unanswered-pill">
              {{ unansweredIndicators.length }} 项未作答
            </span>
          </div>
          <div class="answer-bar-row">
            <div class="answer-track" aria-hidden="true">
              <div class="answer-fill" :style="{ width: `${answeredPercent}%` }"></div>
            </div>
            <span class="answer-rate">{{ formatPercentValue(answeredPercent) }}</span>
          </div>
          <p class="metric-sub">
            累计已做 {{ totalDoneCount }} / {{ totalEligibleCount }} 题（覆盖率
            <strong>{{ formatPercentValue(overallCoveragePercent) }}</strong>）
          </p>
        </article>
      </div>

      <!-- 主题小计快览（只显示主题名称，点击可筛选对应主题） -->
      <div v-if="themes.length" class="theme-strip" role="group" aria-label="按主题筛选">
        <button
          v-for="theme in themes"
          :key="theme.themeId"
          type="button"
          class="theme-card"
          :class="{ active: activeThemeId === theme.themeId }"
          @click="toggleTheme(theme.themeId)"
        >
          <div class="theme-top">
            <span class="theme-name">{{ theme.themeName }}</span>
            <span class="theme-score">
              <template v-if="theme.hasRecord">
                <strong>{{ theme.score }}</strong>/{{ theme.fullScore }}
              </template>
              <template v-else>—</template>
            </span>
          </div>
          <div class="theme-bar-row">
            <div class="mini-track" aria-hidden="true">
              <div
                class="mini-fill"
                :class="`fill-${theme.scoreTone}`"
                :style="{ width: `${theme.scoreRatePercent ?? 0}%` }"
              ></div>
            </div>
            <span class="theme-rate">{{ formatPercentValue(theme.scoreRatePercent) }}</span>
          </div>
          <div class="theme-foot">
            已做 {{ theme.doneCount }}/{{ theme.eligibleCount }} 题 · 覆盖
            {{ formatPercentValue(theme.coveragePercent) }}
          </div>
        </button>
      </div>

      <!-- 工具栏：筛选 + 排序 -->
      <div class="table-toolbar">
        <div class="filter-group" role="tablist" aria-label="按作答情况筛选">
          <button
            v-for="tab in filterOptions"
            :key="tab.key"
            type="button"
            role="tab"
            :aria-selected="activeFilter === tab.key"
            class="filter-pill"
            :class="{ active: activeFilter === tab.key }"
            @click="activeFilter = tab.key"
          >
            <span>{{ tab.label }}</span>
            <span class="pill-count">{{ tab.count }}</span>
          </button>
        </div>

        <button
          type="button"
          class="sort-btn"
          :class="{ active: sortByWeakest }"
          @click="sortByWeakest = !sortByWeakest"
        >
          <span class="sort-icon" aria-hidden="true">{{ sortByWeakest ? '↓' : '⇅' }}</span>
          <span>{{ sortByWeakest ? '按得分率升序' : '按薄弱排序' }}</span>
        </button>
      </div>

      <!-- 主题与知识点得分明细表 -->
      <div class="table-frame">
        <div class="table-scroll">
          <table class="score-table">
            <thead>
              <tr>
                <th scope="col" class="col-theme">主题</th>
                <th scope="col" class="col-kp">知识点</th>
                <th scope="col" class="col-score">得分 / 满分</th>
                <th scope="col" class="col-rate">得分率</th>
                <th scope="col" class="col-status">作答情况</th>
              </tr>
            </thead>
            <tbody v-if="visibleIndicators.length">
              <template v-for="item in visibleIndicators" :key="item.indicatorId">
                <tr
                  class="data-row"
                  :class="{
                    'row-weak': item.hasRecord && item.scoreRate < 0.6,
                    'row-empty': !item.hasRecord,
                    'row-expanded': expandedId === item.indicatorId,
                  }"
                  @click="toggleExpand(item.indicatorId)"
                >
                  <td class="col-theme">
                    <div class="theme-cell">
                      <span class="chevron" aria-hidden="true">
                        {{ expandedId === item.indicatorId ? '▾' : '▸' }}
                      </span>
                      <span class="theme-pill">{{ item.themeName }}</span>
                    </div>
                  </td>
                  <td class="col-kp">
                    <div class="kp-cell">
                      <span class="kp-name">{{ item.indicatorName }}</span>
                      <div class="kp-meta">
                        <span>
                          已做 {{ item.doneCount ?? 0 }}/{{ item.eligibleCount ?? '—' }} 题 · 覆盖
                          {{ formatPercentValue(item.coveragePercent) }}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td class="col-score">
                    <div v-if="item.hasRecord" class="score-cell">
                      <span class="score-actual" :class="`text-${item.scoreTone}`">
                        {{ item.score }}
                      </span>
                      <span class="score-sep">/</span>
                      <span class="score-full">{{ item.fullScore }}</span>
                      <span v-if="item.lostScore > 0" class="lost-tag">-{{ item.lostScore }}</span>
                    </div>
                    <span v-else class="dash-value">—</span>
                  </td>
                  <td class="col-rate">
                    <div v-if="item.hasRecord" class="rate-cell">
                      <div class="progress-track" aria-hidden="true">
                        <div
                          class="progress-fill"
                          :class="`fill-${item.scoreTone}`"
                          :style="{ width: `${item.scoreRatePercent}%` }"
                        ></div>
                      </div>
                      <span class="rate-text">
                        {{ formatPercentValue(item.scoreRatePercent) }}
                      </span>
                    </div>
                    <span v-else class="dash-value">—</span>
                  </td>
                  <td class="col-status">
                    <span class="status-badge" :class="`status-${getAnswerStatus(item).key}`">
                      {{ getAnswerStatus(item).label }}
                    </span>
                  </td>
                </tr>

                <!-- 展开详情：作答情况、教材范围与可补练习题 -->
                <tr v-if="expandedId === item.indicatorId" class="detail-row">
                  <td colspan="5">
                    <div class="detail-panel">
                      <div class="detail-meta-grid">
                        <div>
                          <span class="detail-label">作答情况</span>
                          <span class="detail-val">
                            已做 {{ item.doneCount ?? 0 }} 题 / 可练
                            {{ item.eligibleCount ?? '—' }} 题（覆盖率
                            {{ formatPercentValue(item.coveragePercent) }}）
                          </span>
                        </div>
                        <div v-if="item.textbookRef">
                          <span class="detail-label">教材范围</span>
                          <span class="detail-val">{{ item.textbookRef }}</span>
                        </div>
                      </div>

                      <div class="practice-block">
                        <span class="detail-label">可补练习题</span>
                        <div v-if="item.recommendedQuestions.length" class="practice-chips">
                          <span
                            v-for="q in item.recommendedQuestions"
                            :key="q"
                            class="practice-chip"
                          >
                            {{ q }}
                          </span>
                        </div>
                        <span v-else class="detail-val muted">暂无待补练习题</span>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
            <tbody v-else>
              <tr>
                <td colspan="5" class="empty-cell">当前筛选条件下暂无匹配的知识点</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="2" class="foot-label">
                  全表汇总（共 {{ indicators.length }} 项知识点 · {{ scoredIndicators.length }} 项已作答）
                </td>
                <td class="col-score">
                  <div class="score-cell">
                    <span class="score-actual foot-total">{{ totalScore }}</span>
                    <span class="score-sep">/</span>
                    <span class="score-full">{{ totalFullScore }}</span>
                    <span v-if="totalLostScore > 0" class="lost-tag">-{{ totalLostScore }}</span>
                  </div>
                </td>
                <td class="col-rate">
                  <div class="rate-cell">
                    <div class="progress-track" aria-hidden="true">
                      <div
                        class="progress-fill"
                        :class="`fill-${overallTone}`"
                        :style="{ width: `${overallRatePercent ?? 0}%` }"
                      ></div>
                    </div>
                    <span class="rate-text foot-rate">
                      {{ formatPercentValue(overallRatePercent) }}
                    </span>
                  </div>
                </td>
                <td class="col-status">
                  <span class="foot-coverage">
                    已做 {{ totalDoneCount }}/{{ totalEligibleCount }} 题
                  </span>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.results {
  position: relative;
  overflow: hidden;
  padding: 26px 26px 24px;
  border: 1px solid #eee8df;
  border-radius: 18px;
  background: #fffefa;
  box-shadow: 0 12px 40px rgba(84, 73, 56, 0.055);
}

.card-accent {
  position: absolute;
  top: 0;
  left: 26px;
  width: 48px;
  height: 4px;
  border-radius: 0 0 4px 4px;
  background: #bd5b5a;
}

.title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.section-heading h2 {
  margin: 0;
  color: #203c62;
  font-size: 20px;
  letter-spacing: 0.02em;
}

.id-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: #edf3f9;
  color: #294e79;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.meta-line {
  margin: 7px 0 0;
  color: #8b939d;
  font-size: 13px;
  line-height: 1.6;
}

.loading-state {
  padding: 80px 0;
  text-align: center;
  color: #8f969f;
  font-size: 14px;
}

/* 2x2 核心统计卡片 */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
  padding: 15px 18px;
  border: 1px solid #efe9df;
  border-radius: 14px;
  background: linear-gradient(180deg, #fffefb 0%, #faf7f1 100%);
  transition: border-color 0.2s, transform 0.2s;
}

.metric-card:hover {
  border-color: #e2d8c9;
  transform: translateY(-1px);
}

.metric-score {
  flex-direction: row;
  align-items: center;
  gap: 14px;
  background: linear-gradient(135deg, #fffdf9 0%, #f7efe9 100%);
  border-color: #eadfd6;
}

.score-ring-wrap {
  position: relative;
  width: 62px;
  height: 62px;
  flex: none;
}

.score-ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ring-track {
  fill: none;
  stroke: #ebe3d8;
  stroke-width: 5.5;
}

.ring-progress {
  fill: none;
  stroke-width: 5.5;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.55s ease;
}

.ring-progress.tone-excellent {
  stroke: #2f7a5c;
}

.ring-progress.tone-good {
  stroke: #294e79;
}

.ring-progress.tone-weak {
  stroke: #bd5b5a;
}

.ring-progress.tone-empty {
  stroke: #c9c3b9;
}

.ring-value {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #203c62;
  font-size: 11.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.metric-body {
  min-width: 0;
}

.metric-label {
  display: block;
  color: #8a8f96;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.metric-main {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
}

.score-big {
  color: #1c385c;
  font-size: 27px;
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}

.score-total {
  color: #8d959f;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.lost-pill {
  padding: 1px 7px;
  border-radius: 999px;
  background: #fbeceb;
  color: #b44b4a;
  font-size: 11.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.unanswered-pill {
  padding: 1px 8px;
  border-radius: 999px;
  background: #fbeceb;
  color: #b44b4a;
  font-size: 11px;
  font-weight: 600;
}

.metric-num {
  color: #203c62;
  font-size: 24px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.metric-unit {
  color: #7d8692;
  font-size: 12.5px;
}

.metric-theme-tag {
  padding: 2px 8px;
  border-radius: 6px;
  background: #f2ede3;
  color: #4f6178;
  font-size: 11.5px;
  font-weight: 600;
}

.metric-sub {
  margin: 7px 0 0;
  color: #8b929b;
  font-size: 12px;
  line-height: 1.5;
}

.metric-sub strong {
  color: #2c4362;
}

.text-emerald {
  color: #287053;
}

.text-crimson {
  color: #bd504f;
}

/* 作答情况进度条 */
.answer-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 9px;
}

.answer-track {
  flex: 1;
  height: 7px;
  border-radius: 999px;
  overflow: hidden;
  background: #ebe5dc;
}

.answer-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #4b79ad 0%, #294e79 100%);
  transition: width 0.45s ease;
}

.answer-rate {
  color: #294e79;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* 主题小计快览条 */
.theme-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.theme-card {
  width: 100%;
  height: auto;
  padding: 13px 14px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 7px;
  border: 1px solid #ede6db;
  border-radius: 12px;
  background: #fcfaf5;
  color: #243c61;
  text-align: left;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0;
  transition: all 0.18s;
}

.theme-card:hover {
  background: #f8f4eb;
  border-color: #d9cfc0;
}

.theme-card.active {
  border-color: #294e79;
  background: #f2f6fb;
  box-shadow: 0 0 0 2px rgba(41, 78, 121, 0.12);
}

.theme-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.theme-name {
  color: #203c62;
  font-size: 13.5px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.theme-score {
  flex: none;
  color: #7c8592;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.theme-score strong {
  color: #203c62;
  font-size: 14px;
}

.theme-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-track {
  flex: 1;
  height: 5px;
  border-radius: 999px;
  overflow: hidden;
  background: #e9e3d9;
}

.mini-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s ease;
}

.theme-rate {
  color: #4f6178;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.theme-foot {
  color: #8f96a0;
  font-size: 11.5px;
}

/* 筛选与排序工具栏 */
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
  margin-bottom: 12px;
}

.filter-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}

.filter-pill {
  width: auto;
  height: 31px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #ebe4d9;
  border-radius: 999px;
  background: #fffefa;
  color: #5b6d85;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  transition: all 0.18s;
}

.filter-pill:hover {
  background: #f8f4ec;
  border-color: #ddd3c3;
  color: #203c62;
}

.filter-pill.active {
  border-color: #294e79;
  background: #294e79;
  color: #fff;
}

.pill-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(41, 78, 121, 0.09);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.filter-pill.active .pill-count {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}

.sort-btn {
  width: auto;
  height: 31px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #e8e1d6;
  border-radius: 9px;
  background: #faf7f1;
  color: #536986;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  transition: all 0.18s;
}

.sort-btn:hover {
  background: #f3ede2;
  color: #203c62;
}

.sort-btn.active {
  border-color: #d9a9a7;
  background: #fdf2f1;
  color: #a84847;
}

/* 核心明细表 */
.table-frame {
  border: 1px solid #ede6db;
  border-radius: 14px;
  overflow: hidden;
  background: #fffefa;
}

.table-scroll {
  overflow-x: auto;
}

.score-table {
  width: 100%;
  min-width: 600px;
  border-collapse: collapse;
  text-align: left;
  font-size: 13.5px;
}

.score-table thead th {
  padding: 12px 13px;
  border-bottom: 1px solid #ece5da;
  background: #f9f5ee;
  color: #6a7788;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.score-table tbody tr.data-row {
  cursor: pointer;
}

.score-table tbody tr.data-row td {
  padding: 13px;
  border-bottom: 1px solid #f3eee6;
  color: #2c415e;
  vertical-align: middle;
  transition: background 0.15s;
}

.score-table tbody tr.data-row:hover td {
  background: #fbf8f2;
}

.score-table tbody tr.row-weak td {
  background: #fffaf9;
}

.score-table tbody tr.row-weak:hover td {
  background: #fdf2f0;
}

.score-table tbody tr.row-empty td {
  background: #faf9f6;
}

.score-table tbody tr.row-expanded td {
  border-bottom-color: transparent;
  background: #f7f3eb;
}

.score-table tfoot td {
  padding: 13px;
  border-top: 1px solid #e9e2d7;
  background: #f8f4ec;
  color: #203c62;
  font-weight: 600;
}

.col-theme {
  width: 158px;
  white-space: nowrap;
}

.col-score {
  width: 118px;
  white-space: nowrap;
}

.col-rate {
  width: 132px;
}

.col-status {
  width: 92px;
  text-align: right;
  white-space: nowrap;
}

.score-table thead th.col-status {
  text-align: right;
}

.theme-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chevron {
  width: 12px;
  color: #9ba2ab;
  font-size: 11px;
}

.theme-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border: 1px solid #ebe4d8;
  border-radius: 8px;
  background: #faf7f0;
  color: #2e4869;
  font-size: 12px;
  font-weight: 600;
}

.kp-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.kp-name {
  color: #203c62;
  font-weight: 600;
  line-height: 1.45;
}

.kp-meta {
  color: #8c949f;
  font-size: 11.5px;
}

.score-cell {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  font-variant-numeric: tabular-nums;
}

.score-actual {
  font-size: 15px;
  font-weight: 700;
}

.text-excellent {
  color: #256c50;
}

.text-good {
  color: #294e79;
}

.text-weak {
  color: #bd504f;
}

.score-sep {
  color: #c1b9ae;
  font-size: 12px;
}

.score-full {
  color: #8a929d;
  font-size: 12.5px;
}

.lost-tag {
  margin-left: 4px;
  padding: 1px 5px;
  border-radius: 5px;
  background: #fbeceb;
  color: #b54c4b;
  font-size: 11px;
  font-weight: 600;
}

.dash-value {
  color: #adb3bc;
  font-weight: 600;
}

.rate-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-track {
  flex: 1;
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: #ece7de;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease;
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

.fill-empty {
  background: #d5cfc5;
}

.rate-text {
  width: 44px;
  text-align: right;
  color: #4f6076;
  font-size: 12.5px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
}

.status-perfect {
  background: #e6f4ee;
  color: #246a4d;
}

.status-answered {
  background: #eaf1f8;
  color: #294e79;
}

.status-unanswered {
  background: #fbeceb;
  color: #b44b4a;
}

/* 展开行详情 */
.detail-row td {
  padding: 0;
  border-bottom: 1px solid #ece5da;
  background: #faf7f0;
}

.detail-panel {
  padding: 14px 18px 16px 30px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px dashed #e6dfd4;
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 18px;
}

.detail-label {
  display: inline-block;
  margin-right: 8px;
  color: #8c939c;
  font-size: 12px;
  font-weight: 600;
}

.detail-val {
  color: #344b68;
  font-size: 12.5px;
}

.muted {
  color: #9ba1a9;
}

.practice-block {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}

.practice-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.practice-chip {
  padding: 3px 9px;
  border: 1px solid #e3dacb;
  border-radius: 7px;
  background: #fffefa;
  color: #294e79;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.foot-label {
  font-size: 12.5px;
  color: #465a74;
}

.foot-total,
.foot-rate {
  color: #1e3a5f;
}

.foot-coverage {
  color: #5b6d85;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.empty-cell {
  padding: 36px 14px;
  text-align: center;
  color: #9ba1a9;
}

@media (max-width: 820px) {
  .summary-grid,
  .theme-strip,
  .detail-meta-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .results {
    padding: 20px 16px;
  }

  .card-accent {
    left: 16px;
  }
}
</style>
