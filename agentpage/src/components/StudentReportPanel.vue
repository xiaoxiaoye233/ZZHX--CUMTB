<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  Loader2,
  Sparkles,
} from 'lucide-vue-next'
import {
  downloadStudentLearningReportPdfAPI,
  getStudentLearningReportAPI,
} from '@/apis/analysis'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraphStore'
import { useStudentStore } from '@/stores/studentStore'
import { FALLBACK_STUDENT_TASKS } from '@/utils/tasksFallback'

const props = defineProps({
  studentId: { type: String, default: 'D01' },
  showAdvice: { type: Boolean, default: true },
  showBack: { type: Boolean, default: false },
})

const emit = defineEmits(['back'])

const studentStore = useStudentStore()
const graphStore = useKnowledgeGraphStore()
const { indicators: storeIndicators, loginResult } = storeToRefs(studentStore)
const { nodes: graphNodes } = storeToRefs(graphStore)

const loading = ref(false)
const downloading = ref(false)
const downloadNotice = ref('')
const downloadError = ref(false)
const rawReport = ref(null)

const activeStudentId = computed(
  () => String(props.studentId || 'D01').trim().toUpperCase() || 'D01',
)

function cleanAdviceText(raw) {
  const text = String(raw || '').trim()
  if (!text) return ''
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`/g, '')
    .split(/\r?\n/)
    .map((line) => line.replace(/^\s*#{1,6}\s*/, '').trim())
    .filter(Boolean)
    .join('\n')
}

function buildFallbackAdvice(sid, overall, kps, wrongIds) {
  const scored = kps.filter((k) => k.score_rate !== null && k.score_rate !== undefined)
  const unanswered = kps.filter((k) => k.score_rate === null || k.score_rate === undefined)
  const desc = [...scored].sort((a, b) => b.score_rate - a.score_rate)
  const asc = [...scored].sort((a, b) => a.score_rate - b.score_rate)

  const rateText = formatRatePercent(overall.score_rate)
  const best = desc[0]
  const p1 =
    best && best.score_rate >= 0.6
      ? `1. ${sid} 同学你好！你目前已累计得分 ${formatNum(overall.score)}/${formatNum(overall.full_score)} 分（总得分率 ${rateText}），其中在「${best.name}」（得分率 ${formatRatePercent(best.score_rate)}）上掌握扎实，值得肯定。`
      : `1. ${sid} 同学你好！你目前已累计完成 ${overall.done_questions ?? 0} 道题目，总得分 ${formatNum(overall.score)}/${formatNum(overall.full_score)} 分（总得分率 ${rateText}），每一次认真练习都在稳步积累。`

  const weakList = asc.filter((k) => k.score_rate < 0.75).slice(0, 2)
  const targetWeak = weakList.length ? weakList : asc.slice(0, 2)
  const p2 = targetWeak.length
    ? `2. 建议现阶段优先巩固 ${targetWeak.map((k) => `「${k.name}」${k.textbook_scope ? `（教材：${k.textbook_scope}）` : ''}`).join('、')}${unanswered.length ? `，并逐步尝试「${unanswered[0].name}」等尚未作答的知识点` : ''}。`
    : '2. 各已学知识点整体掌握较为均衡，建议继续结合教材例题串联前后知识点。'

  const wrongPreview = wrongIds.slice(0, 6).join('、') + (wrongIds.length > 6 ? ' 等' : '')
  const p3 = wrongIds.length
    ? `3. 建议优先复盘错题 ${wrongPreview}，梳理审题关键条件与运算易错步骤；遇到卡点随时在对话框向 Agent 老师提问！`
    : '3. 目前暂无失分错题，请继续保持良好的审题和验算习惯，可在任务面板拓展更多练习！'

  return [p1, p2, p3].join('\n')
}

function buildOfflineReport(sid) {
  const inds = storeIndicators.value || []
  const kps = inds.map((ind) => ({
    id: ind.indicatorId || ind.indicatorName,
    name: ind.indicatorName || '未命名知识点',
    theme_name: ind.themeName || '',
    score: ind.score,
    full_score: ind.fullScore,
    score_rate: ind.scoreRate,
    done_count: ind.doneCount ?? 0,
    eligible_count: ind.eligibleCount ?? 0,
    has_record: Boolean(ind.hasRecord),
    textbook_scope: ind.textbookRef || '',
  }))

  const wrongMap = new Map()
  for (const ind of FALLBACK_STUDENT_TASKS?.indicators || []) {
    for (const q of ind.questions || []) {
      if (
        q.done &&
        q.score !== null &&
        q.score !== undefined &&
        q.full_score !== null &&
        q.full_score !== undefined &&
        Number(q.score) < Number(q.full_score)
      ) {
        wrongMap.set(q.question_id, {
          question_id: q.question_id,
          indicator_name: ind.indicator_name || '',
          score: Number(q.score),
          full_score: Number(q.full_score),
        })
      }
    }
  }

  const wrongQuestions = Array.from(wrongMap.values()).sort((a, b) => {
    const na = Number.parseInt(String(a.question_id).replace(/\D+/g, ''), 10) || 0
    const nb = Number.parseInt(String(b.question_id).replace(/\D+/g, ''), 10) || 0
    return na - nb || String(a.question_id).localeCompare(String(b.question_id))
  })
  const wrongIds = wrongQuestions.map((w) => w.question_id)

  const scored = kps.filter((k) => k.has_record)
  const score = scored.reduce((s, k) => s + Number(k.score || 0), 0)
  const fullScore = scored.reduce((s, k) => s + Number(k.full_score || 0), 0)
  const overall = {
    score,
    full_score: fullScore,
    score_rate: fullScore > 0 ? score / fullScore : null,
    done_questions: kps.reduce((s, k) => s + Number(k.done_count || 0), 0),
    available_questions: kps.reduce((s, k) => s + Number(k.eligible_count || 0), 0),
  }

  return {
    student_id: sid,
    class_id: '',
    overall,
    knowledge_points: kps,
    wrong_questions: wrongQuestions,
    wrong_question_ids: wrongIds,
    advice: buildFallbackAdvice(sid, overall, kps, wrongIds),
  }
}

// 动态合并知识图谱中可能新增的知识点（绝不写死数量）
const knowledgePoints = computed(() => {
  const baseList = Array.isArray(rawReport.value?.knowledge_points)
    ? rawReport.value.knowledge_points
    : []
  const graphMap = new Map(
    (graphNodes.value || [])
      .filter((n) => n && n.id)
      .map((n) => [String(n.id).trim(), n]),
  )

  const merged = baseList.map((item) => {
    const gNode = graphMap.get(String(item.id || '').trim())
    return {
      ...item,
      name: (gNode?.name && String(gNode.name).trim()) || item.name || '未命名知识点',
      theme_name: (gNode?.theme && String(gNode.theme).trim()) || item.theme_name || '',
    }
  })

  const seenIds = new Set(merged.map((m) => String(m.id || '').trim()).filter(Boolean))
  const seenNames = new Set(merged.map((m) => String(m.name || '').trim()).filter(Boolean))

  for (const node of graphNodes.value || []) {
    const nid = String(node?.id || '').trim()
    const nname = String(node?.name || '').trim()
    if (!nname || seenIds.has(nid) || seenNames.has(nname)) continue
    merged.push({
      id: nid || nname,
      name: nname,
      theme_name: String(node?.theme || '').trim(),
      score: null,
      full_score: null,
      score_rate: null,
      done_count: 0,
      eligible_count: 0,
      has_record: false,
      textbook_scope: '',
    })
    if (nid) seenIds.add(nid)
    seenNames.add(nname)
  }

  return merged
})

const overall = computed(() => rawReport.value?.overall || {})
const wrongQuestions = computed(() =>
  Array.isArray(rawReport.value?.wrong_questions) ? rawReport.value.wrong_questions : [],
)

const adviceText = computed(() => {
  const loginAdvice =
    loginResult.value?.studentId === activeStudentId.value
      ? loginResult.value?.advice?.content
      : ''
  return cleanAdviceText(loginAdvice || rawReport.value?.advice || '')
})

const adviceParagraphs = computed(() => {
  if (!adviceText.value) return []
  return adviceText.value.split(/\r?\n/).filter(Boolean)
})

function formatNum(val) {
  if (val === null || val === undefined) return '—'
  const num = Number(val)
  if (!Number.isFinite(num)) return '—'
  return Number.isInteger(num) ? String(num) : num.toFixed(1).replace(/\.0$/, '')
}

function formatRatePercent(rate) {
  if (rate === null || rate === undefined) return '暂未作答'
  const num = Number(rate)
  if (!Number.isFinite(num)) return '暂未作答'
  const pct = Math.min(100, Math.max(0, num * 100))
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`
}

function getRateWidth(rate) {
  if (rate === null || rate === undefined) return '0%'
  const num = Number(rate)
  if (!Number.isFinite(num) || num <= 0) return '0%'
  return `${Math.min(100, Math.max(2, Math.round(num * 100)))}%`
}

function getRateToneClass(rate) {
  if (rate === null || rate === undefined || !Number.isFinite(Number(rate))) return 'tone-muted'
  const num = Number(rate)
  if (num >= 0.8) return 'tone-high'
  if (num >= 0.6) return 'tone-mid'
  return 'tone-low'
}

function formatWrongTooltip(item) {
  const parts = [`题号：${item.question_id}`]
  if (item.indicator_name) parts.push(`知识点：${item.indicator_name}`)
  if (item.score !== null && item.score !== undefined && item.full_score) {
    parts.push(`得分：${formatNum(item.score)} / ${formatNum(item.full_score)} 分`)
  }
  return parts.join(' · ')
}

async function loadLearningReport() {
  const sid = activeStudentId.value
  loading.value = true
  downloadNotice.value = ''
  downloadError.value = false

  try {
    const res = await getStudentLearningReportAPI(sid, { includeAdvice: props.showAdvice })
    if (res?.data) {
      rawReport.value = res.data
      return
    }
    rawReport.value = buildOfflineReport(sid)
  } catch {
    rawReport.value = buildOfflineReport(sid)
  } finally {
    loading.value = false
  }
}

async function handleDownloadPdf() {
  if (downloading.value) return
  downloading.value = true
  downloadNotice.value = ''
  downloadError.value = false

  try {
    const { blob, filename } = await downloadStudentLearningReportPdfAPI(activeStudentId.value, {
      includeAdvice: props.showAdvice,
    })
    const blobUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = blobUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1500)
    downloadNotice.value = 'PDF 已开始下载'
  } catch (err) {
    if (!err?.status && typeof window !== 'undefined' && typeof window.print === 'function') {
      window.print()
      return
    }
    downloadError.value = true
    downloadNotice.value = err?.message || '下载 PDF 失败，请确认后端服务已启动'
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  graphStore.fetchGraph()
})

watch(
  activeStudentId,
  () => {
    loadLearningReport()
  },
  { immediate: true },
)
</script>

<template>
  <div class="student-report-stage">
    <!-- 页面顶部栏：左侧学生信息，右上角一键下载 PDF 图标按钮 -->
    <div class="report-topbar">
      <div class="topbar-meta">
        <button
          v-if="props.showBack"
          type="button"
          class="back-report-btn"
          @click="emit('back')"
        >
          <ArrowLeft :size="14" color="#ffffff" :stroke-width="2" />
          <span>返回成绩单</span>
        </button>
        <span class="student-chip">学号 {{ activeStudentId }}</span>
        <span v-if="rawReport?.class_id" class="class-chip">班级 {{ rawReport.class_id }}</span>
        <span class="count-hint">共 {{ knowledgePoints.length }} 个知识点</span>
      </div>

      <div class="topbar-actions">
        <span
          v-if="downloadNotice"
          class="download-toast"
          :class="{ 'is-error': downloadError }"
          role="status"
        >
          {{ downloadNotice }}
        </span>

        <button
          type="button"
          class="download-pdf-btn"
          :disabled="downloading || loading"
          aria-label="下载学情报告 PDF"
          title="下载学情报告 PDF"
          @click="handleDownloadPdf"
        >
          <Loader2
            v-if="downloading"
            :size="17"
            color="#ffffff"
            :stroke-width="2"
            class="spin-icon"
          />
          <Download v-else :size="17" color="#ffffff" :stroke-width="2" />
        </button>
      </div>
    </div>

    <!-- 报告主体滚动区 -->
    <div class="report-scroll">
      <div v-if="loading && !rawReport" class="report-empty">
        正在生成学情报告…
      </div>

      <div v-else class="report-content">
        <!-- 1. 总得分率总览卡片 -->
        <section class="overall-card" aria-label="总得分率概览">
          <div class="overall-main">
            <div class="overall-info">
              <h2 class="overall-label">总得分率</h2>
              <p class="overall-sub">
                总得分 <strong>{{ formatNum(overall.score) }}</strong> /
                {{ formatNum(overall.full_score) }} 分 · 已作答
                {{ overall.done_questions ?? 0 }} / {{ overall.available_questions ?? 0 }} 题
              </p>
            </div>

            <div class="overall-rate-value" :class="getRateToneClass(overall.score_rate)">
              {{ formatRatePercent(overall.score_rate) }}
            </div>
          </div>

          <div class="overall-bar-track" aria-hidden="true">
            <div
              class="overall-bar-fill"
              :class="getRateToneClass(overall.score_rate)"
              :style="{ width: getRateWidth(overall.score_rate) }"
            />
          </div>
        </section>

        <!-- 2. 各知识点得分率（动态渲染，不固定数量） -->
        <section class="report-block" aria-labelledby="kp-rates-heading">
          <header class="block-header">
            <h2 id="kp-rates-heading" class="block-title">各知识点得分率</h2>
            <span class="block-badge">{{ knowledgePoints.length }} 个知识点</span>
          </header>

          <div v-if="!knowledgePoints.length" class="block-empty">
            暂无知识点记录
          </div>

          <div v-else class="kp-rate-grid" role="list">
            <article
              v-for="kp in knowledgePoints"
              :key="kp.id"
              role="listitem"
              class="kp-rate-card"
            >
              <div class="kp-card-top">
                <span v-if="kp.theme_name" class="kp-theme-tag">{{ kp.theme_name }}</span>
                <span v-else />
                <strong class="kp-rate-num" :class="getRateToneClass(kp.score_rate)">
                  {{ formatRatePercent(kp.score_rate) }}
                </strong>
              </div>

              <h3 class="kp-card-name">{{ kp.name }}</h3>

              <div class="kp-bar-track" aria-hidden="true">
                <div
                  class="kp-bar-fill"
                  :class="getRateToneClass(kp.score_rate)"
                  :style="{ width: getRateWidth(kp.score_rate) }"
                />
              </div>

              <div class="kp-card-foot">
                <span v-if="kp.has_record">
                  得分 {{ formatNum(kp.score) }} / {{ formatNum(kp.full_score) }} 分
                </span>
                <span v-else>暂未作答</span>
                <span v-if="kp.eligible_count">
                  已做 {{ kp.done_count ?? 0 }}/{{ kp.eligible_count }} 题
                </span>
              </div>
            </article>
          </div>
        </section>

        <!-- 3. 错题列表（陈列错题题号） -->
        <section class="report-block" aria-labelledby="wrong-list-heading">
          <header class="block-header">
            <div class="title-with-icon">
              <AlertCircle
                v-if="wrongQuestions.length"
                :size="16"
                color="#f87171"
                :stroke-width="2"
              />
              <CheckCircle2 v-else :size="16" color="#4ade80" :stroke-width="2" />
              <h2 id="wrong-list-heading" class="block-title">错题列表</h2>
            </div>
            <span class="block-badge" :class="{ 'badge-warn': wrongQuestions.length > 0 }">
              {{ wrongQuestions.length ? `共 ${wrongQuestions.length} 题` : '0 题' }}
            </span>
          </header>

          <div v-if="!wrongQuestions.length" class="wrong-empty">
            暂无错题记录，表现非常棒，继续保持！
          </div>

          <div v-else class="wrong-chip-grid" role="list" aria-label="错题题号列表">
            <span
              v-for="item in wrongQuestions"
              :key="item.question_id"
              role="listitem"
              class="wrong-qid-chip"
              :title="formatWrongTooltip(item)"
            >
              {{ item.question_id }}
            </span>
          </div>
        </section>

        <!-- 4. 个性化建议（仅学生端展示；教师从成绩单点击学号进入时不展示） -->
        <section
          v-if="props.showAdvice"
          class="report-block advice-block"
          aria-labelledby="advice-heading"
        >
          <header class="block-header">
            <div class="title-with-icon">
              <Sparkles :size="16" color="#60a5fa" :stroke-width="2" />
              <h2 id="advice-heading" class="block-title">个性化建议</h2>
            </div>
          </header>

          <div v-if="adviceParagraphs.length" class="advice-body">
            <p v-for="(para, idx) in adviceParagraphs" :key="idx" class="advice-paragraph">
              {{ para }}
            </p>
          </div>
          <p v-else class="block-empty">正在生成个性化学习建议…</p>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.student-report-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
}

.report-topbar {
  padding: 11px 24px;
  background: #222222;
  border-bottom: 1px solid #2d2d2d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  flex-shrink: 0;
}

.topbar-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.back-report-btn {
  width: auto;
  height: 28px;
  padding: 0 11px;
  border: 1px solid #3c3c3c;
  border-radius: 7px;
  background: #2b2b2b;
  color: #f0f0f0;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.back-report-btn:hover {
  background: #383838;
  border-color: #525252;
}

.student-chip,
.class-chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: #2e2e2e;
  border: 1px solid #3c3c3c;
  color: #f0f0f0;
  font-size: 12px;
  font-weight: 600;
}

.class-chip {
  background: #252b35;
  border-color: #364152;
  color: #cbd5e1;
}

.count-hint {
  color: #9a9a9a;
  font-size: 12.5px;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.download-toast {
  font-size: 12px;
  color: #86efac;
}

.download-toast.is-error {
  color: #fca5a5;
}

.download-pdf-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid #3c3c3c;
  border-radius: 8px;
  background: #2b2b2b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.14s ease;
}

.download-pdf-btn:hover:not(:disabled) {
  background: #0a84ff;
  border-color: #3b9eff;
  transform: translateY(-1px);
}

.download-pdf-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin-icon {
  animation: report-spin 0.9s linear infinite;
}

@keyframes report-spin {
  to {
    transform: rotate(360deg);
  }
}

.report-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 24px 36px;
  scrollbar-width: thin;
  scrollbar-color: #383838 transparent;
}

.report-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8a8a8a;
  font-size: 14px;
}

.report-content {
  max-width: 1120px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* 1. 总得分率卡片 */
.overall-card {
  padding: 20px 24px;
  border-radius: 14px;
  background: linear-gradient(135deg, #1b2432 0%, #171d26 100%);
  border: 1px solid #2e3b4e;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.overall-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.overall-label {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #f4f6f8;
}

.overall-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #9fb0c4;
}

.overall-sub strong {
  color: #ffffff;
  font-weight: 700;
}

.overall-rate-value {
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.overall-bar-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.overall-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.35s ease;
}

/* 通用区块容器 */
.report-block {
  padding: 20px 22px 22px;
  border-radius: 14px;
  background: #181818;
  border: 1px solid #2a2a2a;
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.title-with-icon {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.block-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #f3f3f3;
}

.block-badge {
  padding: 2px 9px;
  border-radius: 999px;
  background: #252525;
  border: 1px solid #343434;
  color: #b5b5b5;
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}

.block-badge.badge-warn {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.32);
  color: #fca5a5;
}

.block-empty {
  margin: 0;
  color: #828282;
  font-size: 13.5px;
}

/* 2. 各知识点得分率自适应网格（不限定数量） */
.kp-rate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px 16px;
}

.kp-rate-card {
  padding: 14px 15px 13px;
  border-radius: 11px;
  background: #202020;
  border: 1px solid #2e2e2e;
  display: flex;
  flex-direction: column;
  gap: 9px;
  transition: border-color 0.16s ease, transform 0.16s ease;
}

.kp-rate-card:hover {
  border-color: #3e3e3e;
  transform: translateY(-1px);
}

.kp-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kp-theme-tag {
  padding: 1.5px 7px;
  border-radius: 5px;
  background: #2a2a2a;
  color: #9e9e9e;
  font-size: 11px;
}

.kp-rate-num {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.kp-card-name {
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.45;
  color: #efefef;
  min-height: 38px;
}

.kp-bar-track {
  width: 100%;
  height: 5px;
  border-radius: 999px;
  background: #2e2e2e;
  overflow: hidden;
}

.kp-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.35s ease;
}

.kp-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11.5px;
  color: #8c8c8c;
  font-variant-numeric: tabular-nums;
}

/* 得分率色彩语义 */
.tone-high {
  color: #4ade80;
}
.overall-bar-fill.tone-high,
.kp-bar-fill.tone-high {
  background: #22c55e;
}

.tone-mid {
  color: #60a5fa;
}
.overall-bar-fill.tone-mid,
.kp-bar-fill.tone-mid {
  background: #3b82f6;
}

.tone-low {
  color: #fbbf24;
}
.overall-bar-fill.tone-low,
.kp-bar-fill.tone-low {
  background: #f59e0b;
}

.tone-muted {
  color: #7c7c7c;
  font-size: 13px;
  font-weight: 500;
}
.overall-bar-fill.tone-muted,
.kp-bar-fill.tone-muted {
  background: #525252;
}

/* 3. 错题题号列表 */
.wrong-empty {
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.22);
  color: #bbf7d0;
  font-size: 13px;
}

.wrong-chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.wrong-qid-chip {
  padding: 6px 14px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.34);
  color: #fecaca;
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  cursor: default;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.wrong-qid-chip:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(248, 113, 113, 0.55);
}

/* 4. 个性化建议 */
.advice-block {
  background: linear-gradient(180deg, #191d24 0%, #17181b 100%);
  border-color: #2b3544;
}

.advice-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.advice-paragraph {
  margin: 0;
  color: #e2e8f0;
  font-size: 13.5px;
  line-height: 1.75;
}

@media (max-width: 640px) {
  .report-scroll {
    padding: 14px;
  }

  .report-block,
  .overall-card {
    padding: 16px;
  }
}

@media print {
  .report-topbar {
    display: none;
  }

  .student-report-stage,
  .report-scroll {
    overflow: visible;
    background: #ffffff;
    color: #111827;
  }
}
</style>
