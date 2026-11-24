import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getStudentAdviceAPI, getStudentChatHistoryAPI } from '@/apis/agent'
import { getStudentScoreTableAPI } from '@/apis/analysis'

// 请求不到后端时的静态兜底数据（与 01_按学生/D01/D01_速览.csv 完全同构）
const STATIC_OVERVIEW_CSV = `行类型,主题编号,主题名称,指标编号,指标名称,全库题数,他能考到,做过不同题目,判定线,覆盖率,得分,满分,得分率,档位,档位说明,课标范围,教材范围,可补练习题
indicator,T01,代数式与整式运算,T01I1,表示数量关系并代入求值,6,6,3,3,0.5,2,6,0.3333,证据充足,,CR01 ①②③⑤ P62/55,上册68-109,Q001(1分)、Q007(1分)、Q006(3分)
indicator,T01,代数式与整式运算,T01I2,识别同类项、去括号并化简,10,10,1,3,0.1,2,3,0.6667,证据偏少,做过的题还不够多，先记下,CR01 ①②③⑤ P62/55,上册68-109,Q003(1分)、Q004(1分)、Q005(1分)、Q008(1分)、Q010(1分)、Q012(1分)、Q016(1分)、Q017(1分)、Q009(3分)
indicator,T01,代数式与整式运算,T01I3,用整式解释具体问题,2,2,2,2,1,5,9,0.5556,证据充足,,CR01 ①②③⑤ P62/55,上册68-109,
indicator,T02,方程与方程组,T02I1,运用等式性质解一元一次方程,8,8,5,3,0.625,5,9,0.5556,证据充足,,CR02 ①②③⑧ P63/56,上册110-148；下册87-119,Q020(1分)、Q023(1分)、Q026(1分)
indicator,T02,方程与方程组,T02I2,用消元法解二元一次方程组,6,6,1,3,0.1667,0,1,0,证据偏少,做过的题还不够多，先记下,CR02 ①②③⑧ P63/56,上册110-148；下册87-119,Q029(1分)、Q032(1分)、Q035(1分)、Q028(3分)、Q031(3分)
indicator,T02,方程与方程组,T02I3,列方程或方程组解决简单实际问题并检验,4,4,1,3,0.25,1,1,1,证据偏少,做过的题还不够多，先记下,CR02 ①②③⑧ P63/56,上册110-148；下册87-119,Q033(1分)、Q034(3分)、Q036(3分)
indicator,T03,不等式与不等式组,T03I1,运用不等式性质求解，负数乘除时正确改变方向,7,7,4,3,0.5714,2,6,0.3333,证据充足,,CR03 ①②③ P63/56,下册120-145,Q038(1分)、Q042(1分)、Q040(3分)
indicator,T03,不等式与不等式组,T03I2,求两个一元一次不等式解集的交集,7,7,2,3,0.2857,1,2,0.5,证据偏少,做过的题还不够多，先记下,CR03 ①②③ P63/56,下册120-145,Q047(1分)、Q048(1分)、Q053(1分)、Q046(3分)、Q049(3分)
indicator,T03,不等式与不等式组,T03I3,根据实际限制列不等式并解释取值范围,4,4,0,3,0,,,,证据不足,这场出了这个指标的题，他没做,CR03 ①②③ P63/56,下册120-145,Q050(1分)、Q051(1分)、Q052(3分)、Q054(3分)
theme,T01,代数式与整式运算,T01 小计,代数式与整式运算,18,18,6,3,0.3333,9,18,0.5,证据充足,,CR01 ①②③⑤ P62/55,上册68-109,
theme,T02,方程与方程组,T02 小计,方程与方程组,18,18,7,3,0.3889,6,11,0.5455,证据充足,,CR02 ①②③⑧ P63/56,上册110-148；下册87-119,
theme,T03,不等式与不等式组,T03 小计,不等式与不等式组,18,18,6,3,0.3333,3,8,0.375,证据充足,,CR03 ①②③ P63/56,下册120-145,`

function toNullableNumber(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const text = String(value).trim()
  if (!text || text === 'null' || text === 'None' || text === 'NaN' || text === '—' || text === '-') {
    return null
  }
  const num = Number(text)
  return Number.isFinite(num) ? num : null
}

function roundNumber(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function parseCSVText(csvText) {
  const clean = String(csvText || '').replace(/^\uFEFF/, '')
  const lines = []
  let currentRow = []
  let currentField = ''
  let inQuotes = false

  for (let i = 0; i < clean.length; i += 1) {
    const ch = clean[i]
    const next = clean[i + 1]

    if (inQuotes) {
      if (ch === '"' && next === '"') {
        currentField += '"'
        i += 1
      } else if (ch === '"') {
        inQuotes = false
      } else {
        currentField += ch
      }
      continue
    }

    if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      currentRow.push(currentField)
      currentField = ''
    } else if (ch === '\r' && next === '\n') {
      currentRow.push(currentField)
      lines.push(currentRow)
      currentRow = []
      currentField = ''
      i += 1
    } else if (ch === '\n' || ch === '\r') {
      currentRow.push(currentField)
      lines.push(currentRow)
      currentRow = []
      currentField = ''
    } else {
      currentField += ch
    }
  }

  if (currentField !== '' || currentRow.length > 0) {
    currentRow.push(currentField)
    lines.push(currentRow)
  }

  const nonEmptyLines = lines.filter((row) => row.some((cell) => cell.trim() !== ''))
  if (nonEmptyLines.length < 2) return []

  const headers = nonEmptyLines[0].map((h) => h.trim())
  return nonEmptyLines.slice(1).map((cells) => {
    const record = {}
    headers.forEach((header, idx) => {
      record[header] = (cells[idx] ?? '').trim()
    })
    return record
  })
}

function parseRecommendedList(raw) {
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean)
  }
  const text = String(raw || '').trim()
  if (!text) return []
  return text
    .split(/[、,，;；\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function getTierKey(tierLabel) {
  if (tierLabel === '证据充足') return 'sufficient'
  if (tierLabel === '证据偏少') return 'limited'
  return 'insufficient'
}

function getScoreTone(rate) {
  if (rate === null || rate === undefined) return 'empty'
  if (rate >= 0.85) return 'excellent'
  if (rate >= 0.6) return 'good'
  return 'weak'
}

// 从后端返回中提取原始速览数据（支持 msg 为 CSV 字符串或行对象数组）
function extractOverviewRows(res) {
  if (!res) return null

  const candidate =
    res.msg !== undefined ? res.msg : res.data !== undefined ? res.data : res.rows ?? res

  if (typeof candidate === 'string') {
    const trimmed = candidate.trim()
    if (!trimmed.includes(',') && !trimmed.includes('\n')) return null
    const parsed = parseCSVText(trimmed)
    return parsed.length ? parsed : null
  }

  if (Array.isArray(candidate) && candidate.length) {
    return candidate
  }

  if (candidate && typeof candidate === 'object') {
    if (typeof candidate.csv === 'string') {
      const parsed = parseCSVText(candidate.csv)
      return parsed.length ? parsed : null
    }
    const nestedRows = candidate.rows || candidate.indicators || candidate.records || candidate.items
    if (Array.isArray(nestedRows) && nestedRows.length) return nestedRows
  }

  return null
}

function extractAdviceText(res) {
  if (typeof res === 'string' && res.trim()) return res.trim()
  if (!res || typeof res !== 'object') return ''

  const candidate =
    res.msg ??
    res.reply ??
    res.advice ??
    res.text ??
    res.content ??
    (typeof res.data === 'string' ? res.data : undefined) ??
    res.data?.msg ??
    res.data?.reply ??
    res.data?.advice

  if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  if (Array.isArray(candidate) && candidate.length) {
    return candidate
      .map((item) => (typeof item === 'string' ? item : item?.text || item?.content || ''))
      .filter(Boolean)
      .join('\n')
  }
  return ''
}

function normalizeRow(row, index) {
  const rowType = String(row['行类型'] ?? row.row_type ?? row.rowType ?? 'indicator')
    .trim()
    .toLowerCase()
  const themeId = String(row['主题编号'] ?? row.theme_id ?? row.themeId ?? '').trim()
  const themeName = String(row['主题名称'] ?? row.theme_name ?? row.themeName ?? '').trim()
  const indicatorId = String(
    row['指标编号'] ?? row.indicator_id ?? row.indicatorId ?? `I${index + 1}`,
  ).trim()
  const indicatorName = String(
    row['指标名称'] ?? row.indicator_name ?? row.indicatorName ?? '',
  ).trim()

  const totalBankCount = toNullableNumber(row['全库题数'] ?? row.total_questions)
  const eligibleCount = toNullableNumber(row['他能考到'] ?? row.eligible_questions)
  const doneCount = toNullableNumber(row['做过不同题目'] ?? row.done_questions)
  const threshold = toNullableNumber(row['判定线'] ?? row.threshold)

  const score = toNullableNumber(row['得分'] ?? row.score)
  const fullScore = toNullableNumber(row['满分'] ?? row.full_score ?? row.fullScore)

  // 前端自算得分率、失分与覆盖率（不依赖后端预计算）
  const hasRecord = score !== null && fullScore !== null && fullScore > 0
  const scoreRate = hasRecord ? Math.min(1, Math.max(0, score / fullScore)) : null
  const scoreRatePercent = scoreRate !== null ? roundNumber(scoreRate * 100, 1) : null
  const lostScore = hasRecord ? Math.max(0, roundNumber(fullScore - score, 2)) : null

  const computedCoverage =
    doneCount !== null && eligibleCount !== null && eligibleCount > 0
      ? Math.min(1, Math.max(0, doneCount / eligibleCount))
      : toNullableNumber(row['覆盖率'] ?? row.coverage_rate ?? row.coverage)
  const coveragePercent = computedCoverage !== null ? roundNumber(computedCoverage * 100, 1) : null

  const tier = String(row['档位'] ?? row.tier ?? row.evidence_tier ?? '').trim() || (hasRecord ? '证据充足' : '证据不足')
  const tierNote = String(row['档位说明'] ?? row.tier_note ?? row.evidence_note ?? '').trim()
  const curriculumRef = String(row['课标范围'] ?? row.curriculum_ref ?? '').trim()
  const textbookRef = String(row['教材范围'] ?? row.textbook_ref ?? '').trim()
  const recommendedQuestions = parseRecommendedList(
    row['可补练习题'] ?? row.recommended_questions ?? row.practice_questions,
  )

  return {
    rowType,
    themeId,
    themeName,
    indicatorId,
    indicatorName,
    totalBankCount,
    eligibleCount,
    doneCount,
    threshold,
    coverageRate: computedCoverage,
    coveragePercent,
    score,
    fullScore,
    lostScore,
    hasRecord,
    scoreRate,
    scoreRatePercent,
    scoreTone: getScoreTone(scoreRate),
    tier,
    tierKey: getTierKey(tier),
    tierNote,
    curriculumRef,
    textbookRef,
    recommendedQuestions,
  }
}

function buildOverviewModel(rawRows, studentId) {
  const normalized = rawRows.map(normalizeRow)
  const indicators = normalized.filter((item) => item.rowType !== 'theme')
  const rawThemeMap = new Map(
    normalized
      .filter((item) => item.rowType === 'theme')
      .map((item) => [item.themeId, item]),
  )

  // 按主题分组并由前端自主计算各主题得分、满分、得分率、覆盖率
  const themeGroups = new Map()
  for (const item of indicators) {
    const key = item.themeId || 'OTHER'
    if (!themeGroups.has(key)) {
      themeGroups.set(key, [])
    }
    themeGroups.get(key).push(item)
  }

  const themes = Array.from(themeGroups.entries()).map(([themeId, items]) => {
    const rawTheme = rawThemeMap.get(themeId)
    const scoredItems = items.filter((item) => item.hasRecord)
    const score = scoredItems.length
      ? roundNumber(scoredItems.reduce((sum, item) => sum + item.score, 0), 2)
      : null
    const fullScore = scoredItems.length
      ? roundNumber(scoredItems.reduce((sum, item) => sum + item.fullScore, 0), 2)
      : null
    const hasRecord = score !== null && fullScore !== null && fullScore > 0
    const scoreRate = hasRecord ? score / fullScore : null
    const doneCount = items.reduce((sum, item) => sum + (item.doneCount ?? 0), 0)
    const eligibleCount = items.reduce((sum, item) => sum + (item.eligibleCount ?? 0), 0)
    const coverageRate = eligibleCount > 0 ? doneCount / eligibleCount : null

    return {
      themeId,
      themeName: rawTheme?.themeName || items[0]?.themeName || themeId,
      indicatorCount: items.length,
      answeredCount: scoredItems.length,
      score,
      fullScore,
      lostScore: hasRecord ? Math.max(0, roundNumber(fullScore - score, 2)) : null,
      hasRecord,
      scoreRate,
      scoreRatePercent: scoreRate !== null ? roundNumber(scoreRate * 100, 1) : null,
      scoreTone: getScoreTone(scoreRate),
      doneCount,
      eligibleCount,
      coverageRate,
      coveragePercent: coverageRate !== null ? roundNumber(coverageRate * 100, 1) : null,
      tier: rawTheme?.tier || '',
      textbookRef: rawTheme?.textbookRef || items[0]?.textbookRef || '',
    }
  })

  return {
    id: String(studentId),
    indicators,
    themes,
  }
}

export const useStudentStore = defineStore('student', () => {
  const student = ref(null)
  const loading = ref(false)
  const adviceLoading = ref(false)
  const agentAdvice = ref('')
  const chatHistory = ref([])
  let requestSeq = 0

  const indicators = computed(() => student.value?.indicators || [])
  const themes = computed(() => student.value?.themes || [])
  const scoredIndicators = computed(() => indicators.value.filter((item) => item.hasRecord))
  const unansweredIndicators = computed(() => indicators.value.filter((item) => !item.hasRecord))

  const totalScore = computed(() =>
    roundNumber(
      scoredIndicators.value.reduce((sum, item) => sum + item.score, 0),
      2,
    ) ?? 0,
  )
  const totalFullScore = computed(() =>
    roundNumber(
      scoredIndicators.value.reduce((sum, item) => sum + item.fullScore, 0),
      2,
    ) ?? 0,
  )
  const totalLostScore = computed(() =>
    Math.max(0, roundNumber(totalFullScore.value - totalScore.value, 2) ?? 0),
  )
  const overallRate = computed(() =>
    totalFullScore.value > 0 ? totalScore.value / totalFullScore.value : null,
  )
  const overallRatePercent = computed(() =>
    overallRate.value !== null ? roundNumber(overallRate.value * 100, 1) : null,
  )

  const totalDoneCount = computed(() =>
    indicators.value.reduce((sum, item) => sum + (item.doneCount ?? 0), 0),
  )
  const totalEligibleCount = computed(() =>
    indicators.value.reduce((sum, item) => sum + (item.eligibleCount ?? 0), 0),
  )
  const overallCoverageRate = computed(() =>
    totalEligibleCount.value > 0 ? totalDoneCount.value / totalEligibleCount.value : null,
  )
  const overallCoveragePercent = computed(() =>
    overallCoverageRate.value !== null ? roundNumber(overallCoverageRate.value * 100, 1) : null,
  )

  // 前端自算：最高分 / 最低分（按单项得分）与最高得分率 / 最低得分率（仅统计已作答指标）
  const maxScore = computed(() => {
    if (!scoredIndicators.value.length) return null
    return Math.max(...scoredIndicators.value.map((item) => item.score))
  })
  const maxScoreItems = computed(() =>
    maxScore.value === null
      ? []
      : scoredIndicators.value.filter((item) => item.score === maxScore.value),
  )

  const minScore = computed(() => {
    if (!scoredIndicators.value.length) return null
    return Math.min(...scoredIndicators.value.map((item) => item.score))
  })
  const minScoreItems = computed(() =>
    minScore.value === null
      ? []
      : scoredIndicators.value.filter((item) => item.score === minScore.value),
  )

  const maxRateItem = computed(() => {
    if (!scoredIndicators.value.length) return null
    return [...scoredIndicators.value].sort(
      (a, b) => b.scoreRate - a.scoreRate || b.score - a.score,
    )[0]
  })

  const minRateItem = computed(() => {
    if (!scoredIndicators.value.length) return null
    return [...scoredIndicators.value].sort(
      (a, b) => a.scoreRate - b.scoreRate || b.lostScore - a.lostScore,
    )[0]
  })

  const weakIndicators = computed(() =>
    scoredIndicators.value.filter((item) => item.scoreRate < 0.6),
  )

  const tierCounts = computed(() => {
    let sufficient = 0
    let limited = 0
    let insufficient = 0
    for (const item of indicators.value) {
      if (item.tierKey === 'sufficient') sufficient += 1
      else if (item.tierKey === 'limited') limited += 1
      else insufficient += 1
    }
    return { sufficient, limited, insufficient }
  })

  async function fetchStudentPageData(studentId = 'D01') {
    const targetId = String(studentId || 'D01').trim().toUpperCase() || 'D01'
    const currentSeq = ++requestSeq
    loading.value = true
    adviceLoading.value = true
    agentAdvice.value = ''
    chatHistory.value = []

    // 1. 请求后端获取该学生的速览数据，失败则用静态 D01_速览 数据兜底
    let resolvedRows = null
    try {
      const res = await getStudentScoreTableAPI(targetId)
      resolvedRows = extractOverviewRows(res)
    } catch {
      // 后端未就绪时静默回退静态数据
    }

    if (currentSeq !== requestSeq) return

    const rowsToUse = resolvedRows || parseCSVText(STATIC_OVERVIEW_CSV)
    student.value = buildOverviewModel(rowsToUse, targetId)
    loading.value = false

    // 2. 先读取该学生的长期会话历史；如果已有历史记录，直接完整展示
    try {
      const historyRes = await getStudentChatHistoryAPI(targetId)
      if (currentSeq !== requestSeq) return
      const savedList = Array.isArray(historyRes?.data) ? historyRes.data : []
      if (savedList.length > 0) {
        chatHistory.value = savedList
        adviceLoading.value = false
        return
      }
    } catch {
      // 后端未就绪或暂无记录时继续走下方生成个性化建议
    }

    if (currentSeq !== requestSeq) return

    // 3. 首次进入还没有历史记录：自动请求 Agent 生成个性化建议（后端会自动存成长期会话首条记录）
    try {
      const adviceRes = await getStudentAdviceAPI(targetId)
      if (currentSeq !== requestSeq) return
      const advice = extractAdviceText(adviceRes)
      if (!advice) return
      agentAdvice.value = advice
      chatHistory.value = [
        { role: 'assistant', tag: 'Agent 老师 · 个性化建议', content: advice },
      ]
    } catch {
      if (currentSeq !== requestSeq) return
      chatHistory.value = [
        { role: 'assistant', tag: '系统提示', content: '暂时无法生成个性化建议，请稍后再试。' },
      ]
    } finally {
      if (currentSeq === requestSeq) adviceLoading.value = false
    }
  }

  return {
    student,
    loading,
    adviceLoading,
    agentAdvice,
    chatHistory,
    indicators,
    themes,
    scoredIndicators,
    unansweredIndicators,
    totalScore,
    totalFullScore,
    totalLostScore,
    overallRate,
    overallRatePercent,
    totalDoneCount,
    totalEligibleCount,
    overallCoverageRate,
    overallCoveragePercent,
    maxScore,
    maxScoreItems,
    minScore,
    minScoreItems,
    maxRateItem,
    minRateItem,
    weakIndicators,
    tierCounts,
    fetchStudentPageData,
  }
})
