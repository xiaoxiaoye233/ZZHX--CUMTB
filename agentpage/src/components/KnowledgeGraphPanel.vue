<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import cytoscape from 'cytoscape'
import {
  ArrowDownRight,
  ArrowUpLeft,
  BookOpen,
  Check,
  ChevronDown,
  Download,
  ExternalLink,
  FileCode2,
  GitBranch,
  Maximize2,
  Plus,
  RotateCcw,
  Trash2,
  Workflow,
  X,
} from 'lucide-vue-next'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraphStore'
import { useTextbookStore } from '@/stores/textbookStore'
import { normalizeTextbookRefs } from '@/utils/defaultKnowledgeGraph'
import {
  exportKnowledgeGraphAsHtml,
  exportKnowledgeGraphAsXmind,
} from '@/utils/exportKnowledgeGraph'

const props = defineProps({
  isTeacher: Boolean,
})

const graphStore = useKnowledgeGraphStore()
const textbookStore = useTextbookStore()
const { nodes, edges, saving, saveMessage } = storeToRefs(graphStore)
const { textbooks } = storeToRefs(textbookStore)

const FALLBACK_TEXTBOOK_NAMES = [
  'B01_相关资料切片.pdf',
  'B02_相关资料切片.pdf',
  'B03_相关资料切片.pdf',
  'B04_相关资料切片.pdf',
  'B05_相关资料切片.pdf',
  'B06_相关资料切片.pdf',
  'B07_相关资料切片.pdf',
  'B08_相关资料切片.pdf',
]

const CARD_COLOR_PRESETS = [
  { label: '星海蓝', hex: '#3b82f6' },
  { label: '星云紫', hex: '#8b5cf6' },
  { label: '翡翠绿', hex: '#10b981' },
  { label: '琥珀橙', hex: '#f59e0b' },
  { label: '珊瑚粉', hex: '#ec4899' },
  { label: '极光青', hex: '#06b6d4' },
  { label: '靛青蓝', hex: '#6366f1' },
  { label: '石墨灰', hex: '#71717a' },
]

const THEME_DEFAULT_COLORS = {
  代数式与整式运算: '#3b82f6',
  方程与方程组: '#8b5cf6',
  不等式与不等式组: '#10b981',
}

function normalizeHex(raw, fallback = '#3b82f6') {
  const s = String(raw || '').trim()
  if (/^#[0-9a-fA-F]{6}$/.test(s)) return s.toLowerCase()
  return fallback
}

// 根据主题边框色自动合成协调的深色卡片底色，确保白字始终清晰
function deriveCardPalette(node) {
  const fallback = THEME_DEFAULT_COLORS[node?.theme] || '#3b82f6'
  const borderHex = normalizeHex(node?.color, fallback)
  const r = parseInt(borderHex.slice(1, 3), 16)
  const g = parseInt(borderHex.slice(3, 5), 16)
  const b = parseInt(borderHex.slice(5, 7), 16)
  const bgR = Math.round(r * 0.28 + 18 * 0.72)
  const bgG = Math.round(g * 0.28 + 20 * 0.72)
  const bgB = Math.round(b * 0.28 + 24 * 0.72)
  return {
    bg: `rgb(${bgR}, ${bgG}, ${bgB})`,
    border: borderHex,
  }
}

const canvasRef = ref(null)
const exportMenuRef = ref(null)
const exportMenuOpen = ref(false)
const exportNotice = ref('')
let exportTimer = null
const selectedNodeId = ref('')
const newPrevTargetId = ref('')
const newPrevRelation = ref('')
const newNextTargetId = ref('')
const newNextRelation = ref('')
const newRefFile = ref('')
const newRefPage = ref(1)
const newRefLabel = ref('')

// 新增知识点弹窗状态（创建时可直接选颜色、填名称、介绍及对应教材页码）
const showCreateModal = ref(false)
const createForm = reactive({
  name: '',
  color: '#3b82f6',
  description: '',
  refFile: '',
  refPage: 1,
  refLabel: '',
})

const editForm = reactive({
  name: '',
  color: '#3b82f6',
  description: '',
})

let cy = null
let resizeObserver = null

const selectedNode = computed(
  () => nodes.value.find((n) => n.id === selectedNodeId.value) || null,
)

const selectedTextbookRefs = computed(() =>
  normalizeTextbookRefs(selectedNode.value?.textbook_refs),
)

const availableTextbookNames = computed(() => {
  const fromStore = (textbooks.value || []).map((b) => b.name).filter(Boolean)
  return fromStore.length ? fromStore : FALLBACK_TEXTBOOK_NAMES
})

function textbookOptionsWithCurrent(currentName) {
  const list = [...availableTextbookNames.value]
  if (currentName && !list.includes(currentName)) {
    list.unshift(currentName)
  }
  return list
}

const incomingRelations = computed(() => {
  if (!selectedNodeId.value) return []
  return edges.value
    .filter((e) => e.target === selectedNodeId.value)
    .map((e) => {
      const src = nodes.value.find((n) => n.id === e.source)
      return {
        ...e,
        otherId: e.source,
        otherName: src?.name || '未命名知识点',
      }
    })
})

const outgoingRelations = computed(() => {
  if (!selectedNodeId.value) return []
  return edges.value
    .filter((e) => e.source === selectedNodeId.value)
    .map((e) => {
      const dst = nodes.value.find((n) => n.id === e.target)
      return {
        ...e,
        otherId: e.target,
        otherName: dst?.name || '未命名知识点',
      }
    })
})

const candidatePrevNodes = computed(() => {
  if (!selectedNodeId.value) return []
  const existingPrev = new Set(incomingRelations.value.map((r) => r.otherId))
  return nodes.value.filter(
    (n) => n.id !== selectedNodeId.value && !existingPrev.has(n.id),
  )
})

const candidateNextNodes = computed(() => {
  if (!selectedNodeId.value) return []
  const existingNext = new Set(outgoingRelations.value.map((r) => r.otherId))
  return nodes.value.filter(
    (n) => n.id !== selectedNodeId.value && !existingNext.has(n.id),
  )
})

function syncEditForm(node) {
  if (!node) {
    editForm.name = ''
    editForm.color = '#3b82f6'
    editForm.description = ''
    return
  }
  const fallback = THEME_DEFAULT_COLORS[node.theme] || '#3b82f6'
  editForm.name = node.name || ''
  editForm.color = normalizeHex(node.color, fallback)
  editForm.description = node.description || ''
  newPrevTargetId.value = ''
  newPrevRelation.value = ''
  newNextTargetId.value = ''
  newNextRelation.value = ''
  newRefFile.value = ''
  newRefPage.value = 1
  newRefLabel.value = ''
}

function buildCyElements() {
  const nodeEls = nodes.value.map((n) => {
    const palette = deriveCardPalette(n)
    return {
      group: 'nodes',
      data: {
        id: n.id,
        label: n.name,
        bgColor: palette.bg,
        borderColor: palette.border,
      },
      position: {
        x: Number.isFinite(Number(n.x)) ? Number(n.x) : 300,
        y: Number.isFinite(Number(n.y)) ? Number(n.y) : 240,
      },
    }
  })

  const validIds = new Set(nodes.value.map((n) => n.id))
  const edgeEls = edges.value
    .filter((e) => validIds.has(e.source) && validIds.has(e.target))
    .map((e) => ({
      group: 'edges',
      data: {
        id: e.id || `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
      },
    }))

  return [...nodeEls, ...edgeEls]
}

function updateCyHighlight(targetId) {
  if (!cy) return
  cy.elements().removeClass('is-selected is-prev is-next is-dimmed')
  if (!targetId) return

  const center = cy.getElementById(targetId)
  if (!center || center.empty()) return

  const prevEls = center.incomers()
  const nextEls = center.outgoers()
  const focusSet = center.union(prevEls).union(nextEls)

  cy.elements().not(focusSet).addClass('is-dimmed')
  prevEls.addClass('is-prev')
  nextEls.addClass('is-next')
  center.addClass('is-selected')
}

function selectNodeById(nodeId, { panTo = false } = {}) {
  selectedNodeId.value = nodeId
  const found = nodes.value.find((n) => n.id === nodeId) || null
  syncEditForm(found)
  updateCyHighlight(nodeId)

  if (panTo && cy && nodeId) {
    const el = cy.getElementById(nodeId)
    if (el && !el.empty()) {
      cy.animate({
        center: { eles: el },
        duration: 240,
      })
    }
  }
}

function rebuildCytoscape({ fit = true } = {}) {
  if (!cy) return
  cy.elements().remove()
  cy.add(buildCyElements())
  if (fit && cy.nodes().length) {
    cy.fit(undefined, 36)
  }
  if (selectedNodeId.value && nodes.value.some((n) => n.id === selectedNodeId.value)) {
    updateCyHighlight(selectedNodeId.value)
  } else if (nodes.value.length) {
    selectNodeById(nodes.value[0].id)
  } else {
    selectedNodeId.value = ''
    syncEditForm(null)
  }
}

function initCytoscape() {
  if (!canvasRef.value) return
  cy = cytoscape({
    container: canvasRef.value,
    elements: buildCyElements(),
    layout: { name: 'preset' },
    minZoom: 0.35,
    maxZoom: 2.5,
    wheelSensitivity: 0.22,
    style: [
      {
        selector: 'node',
        style: {
          shape: 'round-rectangle',
          'corner-radius': 12,
          width: 236,
          height: 84,
          padding: '12px',
          label: 'data(label)',
          color: '#f8fafc',
          'font-size': 16.5,
          'line-height': 1.35,
          'font-weight': 600,
          'text-wrap': 'wrap',
          'text-max-width': 208,
          'text-valign': 'center',
          'text-halign': 'center',
          'background-color': 'data(bgColor)',
          'border-width': 2.5,
          'border-color': 'data(borderColor)',
          'transition-property': 'opacity, border-color, border-width',
          'transition-duration': '0.18s',
        },
      },
      {
        selector: 'edge',
        style: {
          width: 2.4,
          'curve-style': 'bezier',
          'line-color': '#52525b',
          'target-arrow-color': '#71717a',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1.2,
          'transition-property': 'opacity, line-color, target-arrow-color, width',
          'transition-duration': '0.18s',
        },
      },
      {
        selector: 'node.is-selected',
        style: {
          'border-width': 3.5,
          'border-color': '#ffffff',
        },
      },
      {
        selector: 'node.is-prev',
        style: {
          'border-width': 3,
          'border-color': '#38bdf8',
        },
      },
      {
        selector: 'edge.is-prev',
        style: {
          width: 3,
          'line-color': '#38bdf8',
          'target-arrow-color': '#38bdf8',
        },
      },
      {
        selector: 'node.is-next',
        style: {
          'border-width': 3,
          'border-color': '#34d399',
        },
      },
      {
        selector: 'edge.is-next',
        style: {
          width: 3,
          'line-color': '#34d399',
          'target-arrow-color': '#34d399',
        },
      },
      {
        selector: '.is-dimmed',
        style: {
          opacity: 0.24,
        },
      },
    ],
  })

  if (cy.nodes().length) {
    cy.fit(undefined, 36)
  }

  cy.on('tap', 'node', (evt) => {
    const id = evt.target.id()
    selectNodeById(id)
  })

  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      cy.elements().removeClass('is-prev is-next is-dimmed')
      if (selectedNodeId.value) {
        cy.getElementById(selectedNodeId.value).addClass('is-selected')
      }
    }
  })

  cy.on('dragfree', 'node', (evt) => {
    if (!props.isTeacher) return
    const dragged = evt.target
    const pos = dragged.position()
    const target = nodes.value.find((n) => n.id === dragged.id())
    if (target) {
      target.x = Math.round(pos.x)
      target.y = Math.round(pos.y)
      graphStore.persistGraph(
        { nodes: nodes.value, edges: edges.value },
        '已保存节点位置',
      )
    }
  })
}

function fitGraph() {
  if (cy && cy.nodes().length) {
    cy.fit(undefined, 36)
  }
}

async function runAutoLayout() {
  if (!cy || !cy.nodes().length) return
  const layout = cy.layout({
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.5,
    padding: 36,
    animate: true,
    animationDuration: 280,
    transform: (_node, pos) => ({ x: pos.y * 1.45, y: pos.x * 1.05 }),
  })
  layout.run()

  window.setTimeout(() => {
    if (!cy) return
    for (const n of nodes.value) {
      const el = cy.getElementById(n.id)
      if (el && !el.empty()) {
        const p = el.position()
        n.x = Math.round(p.x)
        n.y = Math.round(p.y)
      }
    }
    cy.fit(undefined, 36)
    if (props.isTeacher) {
      graphStore.persistGraph({ nodes: nodes.value, edges: edges.value }, '已应用自动排版')
    }
  }, 320)
}

function onLiveNodeInput() {
  if (!props.isTeacher || !selectedNode.value) return
  const trimmedName = editForm.name.trim() || '未命名知识点'
  selectedNode.value.name = trimmedName
  selectedNode.value.color = normalizeHex(editForm.color)
  selectedNode.value.description = editForm.description

  if (cy) {
    const el = cy.getElementById(selectedNode.value.id)
    if (el && !el.empty()) {
      const palette = deriveCardPalette(selectedNode.value)
      el.data({
        label: trimmedName,
        bgColor: palette.bg,
        borderColor: palette.border,
      })
    }
  }
}

function selectEditColor(hex) {
  editForm.color = hex
  onLiveNodeInput()
  saveCurrentNode()
}

async function saveCurrentNode() {
  if (!props.isTeacher || !selectedNode.value) return
  onLiveNodeInput()
  await graphStore.persistGraph(
    { nodes: nodes.value, edges: edges.value },
    `已保存「${selectedNode.value.name}」`,
  )
}

function openCreateDialog() {
  if (!props.isTeacher) return
  createForm.name = ''
  createForm.color = '#3b82f6'
  createForm.description = ''
  createForm.refFile = ''
  createForm.refPage = 1
  createForm.refLabel = ''
  showCreateModal.value = true
}

async function confirmCreateNode() {
  if (!props.isTeacher) return
  const name = createForm.name.trim() || '新知识点'
  let seq = nodes.value.length + 1
  let nextId = `node-${Date.now()}-${seq}`
  while (nodes.value.some((n) => n.id === nextId)) {
    seq += 1
    nextId = `node-${Date.now()}-${seq}`
  }

  let spawnX = 640
  let spawnY = 260
  if (cy) {
    const ext = cy.extent()
    spawnX = Math.round((ext.x1 + ext.x2) / 2)
    spawnY = Math.round((ext.y1 + ext.y2) / 2)
  }

  const initialRefs = createForm.refFile
    ? [
        {
          name: createForm.refFile,
          page: Math.max(1, Number.parseInt(createForm.refPage, 10) || 1),
          label: createForm.refLabel.trim(),
        },
      ]
    : []

  const newNode = {
    id: nextId,
    name,
    color: normalizeHex(createForm.color),
    description: createForm.description.trim(),
    textbook_refs: initialRefs,
    x: spawnX,
    y: spawnY,
  }
  nodes.value.push(newNode)
  showCreateModal.value = false
  await graphStore.persistGraph(
    { nodes: nodes.value, edges: edges.value },
    `已创建「${name}」`,
  )
  rebuildCytoscape({ fit: false })
  selectNodeById(nextId, { panTo: true })
}

function jumpToTextbookLocation(refItem) {
  const fileName = String(refItem?.name || '').trim()
  if (!fileName) return
  const pageNum = Math.max(1, Number.parseInt(refItem?.page, 10) || 1)
  textbookStore.openTextbookAtPage({
    name: fileName,
    title: fileName.replace(/\.[^.]+$/, ''),
    page: pageNum,
  })
}

async function addTextbookLocation() {
  if (!props.isTeacher || !selectedNode.value || !newRefFile.value) return
  const nextList = normalizeTextbookRefs(selectedNode.value.textbook_refs)
  const pageNum = Math.max(1, Number.parseInt(newRefPage.value, 10) || 1)
  nextList.push({
    name: newRefFile.value,
    page: pageNum,
    label: newRefLabel.value.trim(),
  })
  selectedNode.value.textbook_refs = nextList
  newRefFile.value = ''
  newRefPage.value = 1
  newRefLabel.value = ''
  await graphStore.persistGraph(
    { nodes: nodes.value, edges: edges.value },
    '已添加对应教材位置',
  )
}

async function updateTextbookLocation(index, patch) {
  if (!props.isTeacher || !selectedNode.value) return
  const nextList = normalizeTextbookRefs(selectedNode.value.textbook_refs)
  if (!nextList[index]) return
  const merged = {
    ...nextList[index],
    ...patch,
  }
  merged.name = String(merged.name || '').trim()
  merged.page = Math.max(1, Number.parseInt(merged.page, 10) || 1)
  merged.label = String(merged.label || '').trim()
  if (!merged.name) return
  nextList[index] = merged
  selectedNode.value.textbook_refs = nextList
  await graphStore.persistGraph(
    { nodes: nodes.value, edges: edges.value },
    '已保存教材位置配置',
  )
}

async function removeTextbookLocation(index) {
  if (!props.isTeacher || !selectedNode.value) return
  const nextList = normalizeTextbookRefs(selectedNode.value.textbook_refs)
  nextList.splice(index, 1)
  selectedNode.value.textbook_refs = nextList
  await graphStore.persistGraph(
    { nodes: nodes.value, edges: edges.value },
    '已移除教材位置',
  )
}

async function deleteSelectedNode() {
  if (!props.isTeacher || !selectedNode.value) return
  const targetId = selectedNode.value.id
  const targetName = selectedNode.value.name
  nodes.value = nodes.value.filter((n) => n.id !== targetId)
  edges.value = edges.value.filter((e) => e.source !== targetId && e.target !== targetId)
  await graphStore.persistGraph(
    { nodes: nodes.value, edges: edges.value },
    `已删除「${targetName}」`,
  )
  rebuildCytoscape({ fit: false })
}

async function addPrerequisiteEdge() {
  if (!props.isTeacher || !selectedNodeId.value || !newPrevTargetId.value) return
  const source = newPrevTargetId.value
  const target = selectedNodeId.value
  const edgeId = `${source}->${target}`
  if (edges.value.some((e) => e.source === source && e.target === target)) return

  edges.value.push({
    id: edgeId,
    source,
    target,
    relation: newPrevRelation.value.trim() || '掌握前置基础后方可推进本知识点。',
  })
  newPrevTargetId.value = ''
  newPrevRelation.value = ''
  await graphStore.persistGraph({ nodes: nodes.value, edges: edges.value }, '已添加前置关系')
  rebuildCytoscape({ fit: false })
  updateCyHighlight(target)
}

async function addSuccessorEdge() {
  if (!props.isTeacher || !selectedNodeId.value || !newNextTargetId.value) return
  const source = selectedNodeId.value
  const target = newNextTargetId.value
  const edgeId = `${source}->${target}`
  if (edges.value.some((e) => e.source === source && e.target === target)) return

  edges.value.push({
    id: edgeId,
    source,
    target,
    relation: newNextRelation.value.trim() || '本知识点直接支撑该后续内容的学习。',
  })
  newNextTargetId.value = ''
  newNextRelation.value = ''
  await graphStore.persistGraph({ nodes: nodes.value, edges: edges.value }, '已添加后续关系')
  rebuildCytoscape({ fit: false })
  updateCyHighlight(source)
}

async function removeEdge(source, target) {
  if (!props.isTeacher) return
  edges.value = edges.value.filter((e) => !(e.source === source && e.target === target))
  await graphStore.persistGraph({ nodes: nodes.value, edges: edges.value }, '已移除前后关系')
  rebuildCytoscape({ fit: false })
  if (selectedNodeId.value) updateCyHighlight(selectedNodeId.value)
}

async function saveEdgeRelationNote(edgeItem, newText) {
  if (!props.isTeacher) return
  const target = edges.value.find(
    (e) => e.source === edgeItem.source && e.target === edgeItem.target,
  )
  if (target) {
    target.relation = newText.trim()
    await graphStore.persistGraph({ nodes: nodes.value, edges: edges.value }, '已更新关系说明')
  }
}

async function handleResetGraph() {
  if (!props.isTeacher) return
  await graphStore.resetToDefault()
  rebuildCytoscape({ fit: true })
}

function snapshotNodesWithLivePositions() {
  if (!cy) return nodes.value
  return nodes.value.map((n) => {
    const el = cy.getElementById(n.id)
    if (el && !el.empty()) {
      const pos = el.position()
      return { ...n, x: Math.round(pos.x), y: Math.round(pos.y) }
    }
    return { ...n }
  })
}

function showExportFeedback(text) {
  exportNotice.value = text
  if (exportTimer) window.clearTimeout(exportTimer)
  exportTimer = window.setTimeout(() => {
    exportNotice.value = ''
  }, 3200)
}

function handleExportGraph(format) {
  exportMenuOpen.value = false
  if (!nodes.value.length) return
  const liveNodes = snapshotNodesWithLivePositions()
  if (format === 'xmind') {
    exportKnowledgeGraphAsXmind({ nodes: liveNodes, edges: edges.value })
    showExportFeedback('已导出 XMind 思维导图 (.xmind)')
  } else {
    exportKnowledgeGraphAsHtml({
      nodes: liveNodes,
      edges: edges.value,
      isTeacher: props.isTeacher,
    })
    showExportFeedback('已导出交互式 HTML 图谱 (.html)')
  }
}

function handleGlobalPointerDown(event) {
  if (!exportMenuOpen.value) return
  if (exportMenuRef.value && !exportMenuRef.value.contains(event.target)) {
    exportMenuOpen.value = false
  }
}

function handleGlobalKeydown(event) {
  if (event.key === 'Escape' && exportMenuOpen.value) {
    exportMenuOpen.value = false
  }
}

onMounted(async () => {
  window.addEventListener('pointerdown', handleGlobalPointerDown)
  window.addEventListener('keydown', handleGlobalKeydown)
  textbookStore.fetchTextbooks()
  await graphStore.fetchGraph()
  await nextTick()
  initCytoscape()
  if (nodes.value.length) {
    selectNodeById(nodes.value[0].id)
  }

  if (canvasRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      if (cy) cy.resize()
    })
    resizeObserver.observe(canvasRef.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', handleGlobalPointerDown)
  window.removeEventListener('keydown', handleGlobalKeydown)
  if (exportTimer) window.clearTimeout(exportTimer)
  resizeObserver?.disconnect()
  cy?.destroy()
  cy = null
})
</script>

<template>
  <div class="kg-workspace">
    <!-- 左侧主体：Cytoscape 可交互知识图谱画布 -->
    <div class="kg-stage">
      <div class="kg-toolbar">
        <div class="kg-actions">
          <button
            v-if="isTeacher"
            type="button"
            class="kg-btn primary"
            @click="openCreateDialog"
          >
            <Plus :size="14" color="#ffffff" :stroke-width="2" />
            <span>新增知识点</span>
          </button>

          <button
            type="button"
            class="kg-btn"
            title="自动整理前后层级排版"
            @click="runAutoLayout"
          >
            <Workflow :size="14" color="#ffffff" :stroke-width="1.9" />
            <span>自动排版</span>
          </button>

          <button
            type="button"
            class="kg-btn"
            title="自适应居中显示完整知识图谱"
            @click="fitGraph"
          >
            <Maximize2 :size="14" color="#ffffff" :stroke-width="1.9" />
            <span>居中</span>
          </button>

          <button
            v-if="isTeacher"
            type="button"
            class="kg-btn"
            title="恢复默认知识图谱"
            @click="handleResetGraph"
          >
            <RotateCcw :size="14" color="#ffffff" :stroke-width="1.9" />
            <span>重置</span>
          </button>

          <!-- 教师端与学生端共用的知识图谱导出菜单（支持 HTML 与 XMind） -->
          <div ref="exportMenuRef" class="export-menu-wrap">
            <button
              type="button"
              class="kg-btn export-trigger"
              :disabled="!nodes.length"
              :aria-expanded="exportMenuOpen"
              aria-haspopup="menu"
              title="导出当前知识图谱为 HTML 或 XMind"
              @click="exportMenuOpen = !exportMenuOpen"
            >
              <Download :size="14" color="#ffffff" :stroke-width="1.9" />
              <span>导出图谱</span>
              <ChevronDown
                :size="13"
                color="#ffffff"
                :stroke-width="1.9"
                class="export-chevron"
                :class="{ open: exportMenuOpen }"
              />
            </button>

            <div v-if="exportMenuOpen" class="export-dropdown" role="menu">
              <button
                type="button"
                class="export-option"
                role="menuitem"
                @click="handleExportGraph('html')"
              >
                <FileCode2 :size="16" color="#60a5fa" :stroke-width="1.9" />
                <div class="export-opt-text">
                  <strong>导出为 HTML 网页</strong>
                  <span>独立可交互离线图谱 (.html)</span>
                </div>
              </button>

              <button
                type="button"
                class="export-option"
                role="menuitem"
                @click="handleExportGraph('xmind')"
              >
                <GitBranch :size="16" color="#34d399" :stroke-width="1.9" />
                <div class="export-opt-text">
                  <strong>导出为 XMind 导图</strong>
                  <span>标准思维导图含备注与关联 (.xmind)</span>
                </div>
              </button>
            </div>
          </div>

          <span v-if="exportNotice" class="save-toast" role="status">
            {{ exportNotice }}
          </span>
          <span v-else-if="saveMessage && isTeacher" class="save-toast" role="status">
            {{ saveMessage }}
          </span>
        </div>
      </div>

      <!-- Cytoscape 容器 -->
      <div ref="canvasRef" class="cy-canvas" aria-label="知识图谱交互画布" />

      <!-- 教师端创建新知识点弹窗（可直接选择卡片颜色） -->
      <div
        v-if="showCreateModal && isTeacher"
        class="create-modal-backdrop"
        @click.self="showCreateModal = false"
      >
        <form class="create-modal" @submit.prevent="confirmCreateNode">
          <div class="modal-header">
            <h3>新增知识点</h3>
            <button
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="showCreateModal = false"
            >
              <X :size="15" color="#ffffff" />
            </button>
          </div>

          <div class="editor-group">
            <label class="editor-label" for="create-kp-name">知识点名称</label>
            <input
              id="create-kp-name"
              v-model="createForm.name"
              type="text"
              class="editor-input"
              placeholder="请输入知识点名称"
              required
            />
          </div>

          <div class="editor-group">
            <span class="editor-label">卡片颜色</span>
            <div class="color-picker-row">
              <button
                v-for="preset in CARD_COLOR_PRESETS"
                :key="preset.hex"
                type="button"
                class="color-swatch"
                :class="{ active: createForm.color === preset.hex }"
                :style="{ backgroundColor: preset.hex }"
                :title="preset.label"
                :aria-label="preset.label"
                @click="createForm.color = preset.hex"
              />
              <label class="custom-color-wrap" title="自定义颜色">
                <input v-model="createForm.color" type="color" class="native-color-input" />
              </label>
            </div>
          </div>

          <div class="editor-group">
            <label class="editor-label" for="create-kp-desc">知识点介绍</label>
            <textarea
              id="create-kp-desc"
              v-model="createForm.description"
              rows="3"
              class="editor-textarea"
              placeholder="选填：输入该知识点的介绍…"
            />
          </div>

          <div class="editor-group">
            <span class="editor-label">对应教材位置（选填）</span>
            <select v-model="createForm.refFile" class="editor-select compact">
              <option value="">暂不绑定教材文件</option>
              <option v-for="fname in availableTextbookNames" :key="fname" :value="fname">
                {{ fname }}
              </option>
            </select>
            <div v-if="createForm.refFile" class="add-rel-sub">
              <label class="tb-page-field">
                <span>第</span>
                <input
                  v-model.number="createForm.refPage"
                  type="number"
                  min="1"
                  class="editor-input compact tb-page-input"
                />
                <span>页</span>
              </label>
              <input
                v-model="createForm.refLabel"
                type="text"
                class="editor-input compact"
                placeholder="章节备注（选填）"
              />
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="kg-btn" @click="showCreateModal = false">取消</button>
            <button type="submit" class="kg-btn primary">创建</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 右侧详情/编辑侧栏 -->
    <aside class="kg-inspector" aria-label="知识点详情与前后关系面板">
      <div v-if="!selectedNode" class="inspector-empty">
        请点击左侧图谱中的任意知识点
      </div>

      <!-- 教师端：可交互编辑模式 -->
      <div v-else-if="isTeacher" class="inspector-body">
        <div class="editor-group">
          <label class="editor-label" for="kp-edit-name">知识点名称</label>
          <input
            id="kp-edit-name"
            v-model="editForm.name"
            type="text"
            class="editor-input"
            placeholder="输入知识点名称"
            @input="onLiveNodeInput"
            @change="saveCurrentNode"
          />
        </div>

        <div class="editor-group">
          <span class="editor-label">卡片颜色</span>
          <div class="color-picker-row">
            <button
              v-for="preset in CARD_COLOR_PRESETS"
              :key="preset.hex"
              type="button"
              class="color-swatch"
              :class="{ active: editForm.color === preset.hex }"
              :style="{ backgroundColor: preset.hex }"
              :title="preset.label"
              :aria-label="preset.label"
              @click="selectEditColor(preset.hex)"
            />
            <label class="custom-color-wrap" title="自定义颜色">
              <input
                v-model="editForm.color"
                type="color"
                class="native-color-input"
                @input="onLiveNodeInput"
                @change="saveCurrentNode"
              />
            </label>
          </div>
        </div>

        <div class="editor-group">
          <label class="editor-label" for="kp-edit-desc">知识点介绍</label>
          <textarea
            id="kp-edit-desc"
            v-model="editForm.description"
            rows="4"
            class="editor-textarea"
            placeholder="输入该知识点的概念说明或要求…"
            @input="onLiveNodeInput"
            @change="saveCurrentNode"
          />
        </div>

        <div class="editor-actions-row">
          <button
            type="button"
            class="save-node-btn"
            :disabled="saving"
            @click="saveCurrentNode"
          >
            <Check :size="14" color="#ffffff" :stroke-width="2" />
            <span>{{ saving ? '保存中…' : '保存修改' }}</span>
          </button>

          <button
            type="button"
            class="del-node-btn"
            title="删除此知识点节点"
            @click="deleteSelectedNode"
          >
            <Trash2 :size="14" color="#ffffff" />
          </button>
        </div>

        <div class="divider" />

        <!-- 对应教材位置：点击一键跳转右侧阅读器对应页码，教师可自定义增删改文件与页码 -->
        <section class="relation-section">
          <h3 class="rel-heading book-tone">
            <BookOpen :size="15" color="#93c5fd" />
            <span>对应教材位置（{{ selectedTextbookRefs.length }}）</span>
          </h3>

          <div v-if="selectedTextbookRefs.length" class="rel-list">
            <div
              v-for="(refItem, rIdx) in selectedTextbookRefs"
              :key="`${refItem.name}-${refItem.page}-${rIdx}`"
              class="rel-edit-card tb-ref-edit-card"
            >
              <div class="rel-card-top">
                <button
                  type="button"
                  class="tb-jump-header-btn"
                  :title="`点击打开 ${refItem.name} 第 ${refItem.page} 页`"
                  @click="jumpToTextbookLocation(refItem)"
                >
                  <BookOpen :size="13" color="#93c5fd" />
                  <span class="tb-jump-text">{{ refItem.name }} · 第 {{ refItem.page }} 页</span>
                  <ExternalLink :size="12" color="#93c5fd" class="tb-jump-ext" />
                </button>
                <button
                  type="button"
                  class="rel-remove-btn"
                  title="移除此教材位置"
                  @click="removeTextbookLocation(rIdx)"
                >
                  <Trash2 :size="12" color="#ffffff" />
                </button>
              </div>

              <div class="tb-config-row">
                <select
                  :value="refItem.name"
                  class="editor-select compact tb-file-select"
                  aria-label="选择教材文件"
                  @change="updateTextbookLocation(rIdx, { name: $event.target.value })"
                >
                  <option
                    v-for="fname in textbookOptionsWithCurrent(refItem.name)"
                    :key="fname"
                    :value="fname"
                  >
                    {{ fname }}
                  </option>
                </select>

                <label class="tb-page-field">
                  <span>第</span>
                  <input
                    :value="refItem.page"
                    type="number"
                    min="1"
                    class="editor-input compact tb-page-input"
                    aria-label="教材页码"
                    @change="updateTextbookLocation(rIdx, { page: $event.target.value })"
                  />
                  <span>页</span>
                </label>
              </div>

              <input
                :value="refItem.label"
                type="text"
                class="rel-note-input"
                placeholder="章节或位置说明（选填，如 3.1 列代数式）"
                @change="updateTextbookLocation(rIdx, { label: $event.target.value })"
              />
            </div>
          </div>
          <p v-else class="rel-empty">暂未配置教材位置，可在下方选择文件与页码添加</p>

          <div class="add-rel-box">
            <select v-model="newRefFile" class="editor-select compact">
              <option value="">+ 添加对应教材位置…</option>
              <option v-for="fname in availableTextbookNames" :key="fname" :value="fname">
                {{ fname }}
              </option>
            </select>
            <div v-if="newRefFile" class="add-rel-sub">
              <label class="tb-page-field">
                <span>第</span>
                <input
                  v-model.number="newRefPage"
                  type="number"
                  min="1"
                  class="editor-input compact tb-page-input"
                  placeholder="页码"
                />
                <span>页</span>
              </label>
              <input
                v-model="newRefLabel"
                type="text"
                class="editor-input compact"
                placeholder="章节说明（选填）"
              />
              <button type="button" class="mini-add-btn" @click="addTextbookLocation">
                添加
              </button>
            </div>
          </div>
        </section>

        <div class="divider" />

        <!-- 编辑前置关系 -->
        <section class="relation-section">
          <h3 class="rel-heading prev-tone">
            <ArrowUpLeft :size="15" color="#ffffff" />
            <span>前置关系（{{ incomingRelations.length }}）</span>
          </h3>

          <div v-if="incomingRelations.length" class="rel-list">
            <div v-for="rel in incomingRelations" :key="rel.id" class="rel-edit-card">
              <div class="rel-card-top">
                <button
                  type="button"
                  class="rel-jump-btn"
                  @click="selectNodeById(rel.otherId, { panTo: true })"
                >
                  <span class="rel-name">{{ rel.otherName }}</span>
                </button>
                <button
                  type="button"
                  class="rel-remove-btn"
                  title="移除此关系"
                  @click="removeEdge(rel.source, rel.target)"
                >
                  <Trash2 :size="12" color="#ffffff" />
                </button>
              </div>
              <input
                :value="rel.relation"
                type="text"
                class="rel-note-input"
                placeholder="关系说明"
                @change="saveEdgeRelationNote(rel, $event.target.value)"
              />
            </div>
          </div>
          <p v-else class="rel-empty">暂无前置知识点</p>

          <div v-if="candidatePrevNodes.length" class="add-rel-box">
            <select v-model="newPrevTargetId" class="editor-select compact">
              <option value="">+ 添加前置知识点…</option>
              <option v-for="n in candidatePrevNodes" :key="n.id" :value="n.id">
                {{ n.name }}
              </option>
            </select>
            <div v-if="newPrevTargetId" class="add-rel-sub">
              <input
                v-model="newPrevRelation"
                type="text"
                class="editor-input compact"
                placeholder="关系说明（选填）"
              />
              <button type="button" class="mini-add-btn" @click="addPrerequisiteEdge">
                添加
              </button>
            </div>
          </div>
        </section>

        <!-- 编辑后续关系 -->
        <section class="relation-section">
          <h3 class="rel-heading next-tone">
            <ArrowDownRight :size="15" color="#ffffff" />
            <span>后续关系（{{ outgoingRelations.length }}）</span>
          </h3>

          <div v-if="outgoingRelations.length" class="rel-list">
            <div v-for="rel in outgoingRelations" :key="rel.id" class="rel-edit-card">
              <div class="rel-card-top">
                <button
                  type="button"
                  class="rel-jump-btn"
                  @click="selectNodeById(rel.otherId, { panTo: true })"
                >
                  <span class="rel-name">{{ rel.otherName }}</span>
                </button>
                <button
                  type="button"
                  class="rel-remove-btn"
                  title="移除此关系"
                  @click="removeEdge(rel.source, rel.target)"
                >
                  <Trash2 :size="12" color="#ffffff" />
                </button>
              </div>
              <input
                :value="rel.relation"
                type="text"
                class="rel-note-input"
                placeholder="关系说明"
                @change="saveEdgeRelationNote(rel, $event.target.value)"
              />
            </div>
          </div>
          <p v-else class="rel-empty">暂无后续知识点</p>

          <div v-if="candidateNextNodes.length" class="add-rel-box">
            <select v-model="newNextTargetId" class="editor-select compact">
              <option value="">+ 添加后续知识点…</option>
              <option v-for="n in candidateNextNodes" :key="n.id" :value="n.id">
                {{ n.name }}
              </option>
            </select>
            <div v-if="newNextTargetId" class="add-rel-sub">
              <input
                v-model="newNextRelation"
                type="text"
                class="editor-input compact"
                placeholder="关系说明（选填）"
              />
              <button type="button" class="mini-add-btn" @click="addSuccessorEdge">
                添加
              </button>
            </div>
          </div>
        </section>
      </div>

      <!-- 学生端：交互式查看详情与前后关系跳转 -->
      <div v-else class="inspector-body">
        <h2 class="student-kp-title">{{ selectedNode.name }}</h2>

        <section class="student-desc-box">
          <h3>介绍</h3>
          <p>{{ selectedNode.description || '暂无详细介绍' }}</p>
        </section>

        <section class="relation-section">
          <h3 class="rel-heading book-tone">
            <BookOpen :size="15" color="#93c5fd" />
            <span>对应教材位置（{{ selectedTextbookRefs.length }}）</span>
          </h3>

          <div v-if="selectedTextbookRefs.length" class="rel-list">
            <button
              v-for="(refItem, rIdx) in selectedTextbookRefs"
              :key="`${refItem.name}-${refItem.page}-${rIdx}`"
              type="button"
              class="student-tb-card"
              :title="`点击在右侧阅读器打开 ${refItem.name} 第 ${refItem.page} 页`"
              @click="jumpToTextbookLocation(refItem)"
            >
              <div class="s-tb-top">
                <span class="s-tb-file">
                  <BookOpen :size="13" color="#93c5fd" />
                  <strong>{{ refItem.name }}</strong>
                </span>
                <span class="s-tb-page-pill">第 {{ refItem.page }} 页</span>
              </div>
              <p v-if="refItem.label" class="s-rel-note">{{ refItem.label }}</p>
            </button>
          </div>
          <p v-else class="rel-empty">暂未配置对应教材位置</p>
        </section>

        <section class="relation-section">
          <h3 class="rel-heading prev-tone">
            <ArrowUpLeft :size="15" color="#ffffff" />
            <span>前置知识（{{ incomingRelations.length }}）</span>
          </h3>

          <div v-if="incomingRelations.length" class="rel-list">
            <button
              v-for="rel in incomingRelations"
              :key="rel.id"
              type="button"
              class="student-rel-card is-prev"
              @click="selectNodeById(rel.otherId, { panTo: true })"
            >
              <div class="s-rel-title">
                <strong>{{ rel.otherName }}</strong>
              </div>
              <p v-if="rel.relation" class="s-rel-note">{{ rel.relation }}</p>
            </button>
          </div>
          <p v-else class="rel-empty">暂无前置知识点</p>
        </section>

        <section class="relation-section">
          <h3 class="rel-heading next-tone">
            <ArrowDownRight :size="15" color="#ffffff" />
            <span>后续知识（{{ outgoingRelations.length }}）</span>
          </h3>

          <div v-if="outgoingRelations.length" class="rel-list">
            <button
              v-for="rel in outgoingRelations"
              :key="rel.id"
              type="button"
              class="student-rel-card is-next"
              @click="selectNodeById(rel.otherId, { panTo: true })"
            >
              <div class="s-rel-title">
                <strong>{{ rel.otherName }}</strong>
              </div>
              <p v-if="rel.relation" class="s-rel-note">{{ rel.relation }}</p>
            </button>
          </div>
          <p v-else class="rel-empty">暂无后续知识点</p>
        </section>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.kg-workspace {
  flex: 1;
  min-height: 0;
  display: flex;
  background: #171717;
  overflow: hidden;
}

.kg-stage {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: #161616;
  background-image: radial-gradient(#292929 1px, transparent 1px);
  background-size: 22px 22px;
}

.kg-toolbar {
  min-height: 46px;
  padding: 8px 16px;
  background: rgba(24, 24, 24, 0.92);
  border-bottom: 1px solid #292929;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  flex-shrink: 0;
  z-index: 2;
}

.kg-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}

.save-toast {
  color: #4ade80;
  font-size: 12px;
  margin-left: 4px;
}

.kg-btn {
  width: auto;
  height: 30px;
  padding: 0 11px;
  border: 1px solid #363636;
  border-radius: 7px;
  background: #252525;
  color: #f0f0f0;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}

.kg-btn:hover {
  background: #303030;
  border-color: #4a4a4a;
}

.kg-btn.primary {
  background: #1d4ed8;
  border-color: #2563eb;
}

.kg-btn.primary:hover {
  background: #2563eb;
}

.kg-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.export-menu-wrap {
  position: relative;
  display: inline-flex;
}

.export-chevron {
  transition: transform 0.16s ease;
}

.export-chevron.open {
  transform: rotate(180deg);
}

.export-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 228px;
  padding: 6px;
  border-radius: 10px;
  background: #202024;
  border: 1px solid #383840;
  box-shadow: 0 16px 38px rgba(0, 0, 0, 0.62);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 30;
}

.export-option {
  width: 100%;
  height: auto;
  padding: 8px 10px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #f4f4f5;
  text-align: left;
  letter-spacing: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: background-color 0.14s ease;
}

.export-option:hover {
  background: #2d2d34;
}

.export-opt-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.export-opt-text strong {
  font-size: 12.5px;
  font-weight: 600;
  color: #f8fafc;
}

.export-opt-text span {
  font-size: 11px;
  color: #9ca3af;
}

.cy-canvas {
  flex: 1;
  width: 100%;
  min-height: 0;
}

/* 创建知识点弹窗 */
.create-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 20;
}

.create-modal {
  width: 100%;
  max-width: 360px;
  padding: 20px 20px 18px;
  border-radius: 14px;
  background: #202022;
  border: 1px solid #353538;
  box-shadow: 0 20px 56px rgba(0, 0, 0, 0.72);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-header h3 {
  margin: 0;
  color: #f4f4f5;
  font-size: 15px;
  font-weight: 600;
}

.modal-close {
  width: 26px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.75;
  cursor: pointer;
}

.modal-close:hover {
  background: #303034;
  opacity: 1;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 2px;
}

/* 卡片颜色选择器 */
.color-picker-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.color-swatch {
  width: 24px;
  height: 24px;
  padding: 0;
  border-radius: 999px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.14s ease, border-color 0.14s ease;
}

.color-swatch:hover {
  transform: scale(1.1);
}

.color-swatch.active {
  border-color: #ffffff;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.22);
}

.custom-color-wrap {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  border: 1.5px dashed #71717a;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.native-color-input {
  width: 34px;
  height: 34px;
  margin: -5px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

/* 右侧检查器与编辑器 */
.kg-inspector {
  width: clamp(292px, 31%, 352px);
  height: 100%;
  flex-shrink: 0;
  background: #1d1d1d;
  border-left: 1px solid #2c2c2c;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.inspector-empty {
  flex: 1;
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #828282;
  font-size: 13px;
}

.inspector-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 18px 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: thin;
  scrollbar-color: #363636 transparent;
}

.editor-group {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.editor-label {
  color: #a8a8a8;
  font-size: 12px;
  font-weight: 500;
}

.editor-input,
.editor-select,
.editor-textarea {
  width: 100%;
  margin: 0;
  border: 1px solid #333333;
  border-radius: 8px;
  background: #141414;
  color: #efefef;
  font: inherit;
  font-size: 13.5px;
  outline: none;
  transition: border-color 0.16s ease;
}

.editor-input,
.editor-select {
  height: 36px;
  padding: 0 11px;
}

.editor-input.compact,
.editor-select.compact {
  height: 32px;
  font-size: 12px;
}

.editor-textarea {
  padding: 9px 11px;
  line-height: 1.55;
  resize: vertical;
}

.editor-input:focus,
.editor-select:focus,
.editor-textarea:focus {
  border-color: #3b82f6;
}

.editor-actions-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.save-node-btn {
  flex: 1;
  height: 34px;
  padding: 0 12px;
  border: 1px solid #2e59a8;
  border-radius: 8px;
  background: #1e3a6e;
  color: #ffffff;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.03em;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
}

.save-node-btn:hover:not(:disabled) {
  background: #254a8c;
}

.del-node-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid #422828;
  border-radius: 8px;
  background: #281919;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.del-node-btn:hover {
  background: #5c2424;
  border-color: #823535;
}

.divider {
  height: 1px;
  background: #2b2b2b;
  margin: 2px 0;
}

.relation-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rel-heading {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.rel-heading.prev-tone {
  color: #7dd3fc;
}

.rel-heading.next-tone {
  color: #6ee7b7;
}

.rel-heading.book-tone {
  color: #93c5fd;
}

.tb-ref-edit-card {
  border-color: rgba(59, 130, 246, 0.28);
}

.tb-jump-header-btn {
  flex: 1;
  min-width: 0;
  width: auto;
  height: auto;
  padding: 2px 4px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #bfdbfe;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  cursor: pointer;
}

.tb-jump-header-btn:hover {
  background: rgba(59, 130, 246, 0.14);
  color: #eff6ff;
}

.tb-jump-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tb-jump-ext {
  flex-shrink: 0;
  opacity: 0.8;
}

.tb-config-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tb-file-select {
  flex: 1;
  min-width: 0;
}

.tb-page-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #a8a8a8;
  font-size: 12px;
  flex-shrink: 0;
}

.tb-page-input {
  width: 58px;
  padding: 0 6px;
  text-align: center;
}

.student-tb-card {
  width: 100%;
  height: auto;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(23, 37, 64, 0.42);
  border: 1px solid rgba(59, 130, 246, 0.34);
  color: #eff6ff;
  text-align: left;
  letter-spacing: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.14s ease;
}

.student-tb-card:hover {
  background: rgba(30, 58, 110, 0.56);
  border-color: #60a5fa;
  transform: translateY(-1px);
}

.s-tb-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.s-tb-file {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
}

.s-tb-file strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.s-tb-page-pill {
  padding: 1.5px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.22);
  border: 1px solid rgba(96, 165, 250, 0.45);
  color: #93c5fd;
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.rel-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rel-edit-card {
  padding: 9px 10px;
  border-radius: 9px;
  background: #151515;
  border: 1px solid #2d2d2d;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.rel-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.rel-jump-btn {
  width: auto;
  height: auto;
  padding: 0;
  border: 0;
  background: transparent;
  color: #ededed;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  cursor: pointer;
}

.rel-jump-btn:hover .rel-name {
  text-decoration: underline;
}

.rel-remove-btn {
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.65;
  cursor: pointer;
  flex-shrink: 0;
}

.rel-remove-btn:hover {
  background: #542323;
  opacity: 1;
}

.rel-note-input {
  width: 100%;
  height: 28px;
  margin: 0;
  padding: 0 8px;
  border: 1px solid #282828;
  border-radius: 6px;
  background: #1c1c1c;
  color: #bdbdbd;
  font-size: 11.5px;
  outline: none;
}

.rel-note-input:focus {
  border-color: #3b82f6;
  color: #efefef;
}

.rel-empty {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #161616;
  color: #787878;
  font-size: 12px;
}

.add-rel-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 2px;
}

.add-rel-sub {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-add-btn {
  width: auto;
  height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 7px;
  background: #2563eb;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  flex-shrink: 0;
  cursor: pointer;
}

.mini-add-btn:hover {
  background: #3b82f6;
}

/* 学生端只读探索卡片 */
.student-kp-title {
  margin: 0;
  color: #f5f5f5;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.4;
}

.student-desc-box {
  padding: 13px 14px;
  border-radius: 10px;
  background: #151515;
  border: 1px solid #2b2b2b;
}

.student-desc-box h3 {
  margin: 0 0 6px;
  color: #9e9e9e;
  font-size: 12px;
  font-weight: 600;
}

.student-desc-box p {
  margin: 0;
  color: #e4e4e7;
  font-size: 13.5px;
  line-height: 1.65;
}

.student-rel-card {
  width: 100%;
  height: auto;
  padding: 11px 12px;
  border-radius: 10px;
  background: #151515;
  border: 1px solid #2d2d2d;
  color: #efefef;
  text-align: left;
  letter-spacing: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease;
}

.student-rel-card.is-prev:hover {
  background: #16222c;
  border-color: #38bdf8;
}

.student-rel-card.is-next:hover {
  background: #142620;
  border-color: #34d399;
}

.s-rel-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
}

.s-rel-note {
  margin: 0;
  color: #9ca3af;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .kg-workspace {
    flex-direction: column;
  }

  .kg-inspector {
    width: 100%;
    height: 46%;
    border-left: 0;
    border-top: 1px solid #2c2c2c;
  }
}
</style>
