import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getKnowledgeGraphAPI,
  resetKnowledgeGraphAPI,
  saveKnowledgeGraphAPI,
} from '@/apis/agent'
import {
  cloneDefaultGraph,
  normalizeGraphNode,
} from '@/utils/defaultKnowledgeGraph'

const LOCAL_STORAGE_KEY = 'zjhx-knowledge-graph-v2'

function readLocalGraph() {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed?.nodes) && Array.isArray(parsed?.edges)) {
      return parsed
    }
  } catch {
    // 忽略本地解析错误
  }
  return null
}

function writeLocalGraph(graph) {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(graph))
  } catch {
    // 忽略配额限制
  }
}

export const useKnowledgeGraphStore = defineStore('knowledgeGraph', () => {
  const nodes = ref([])
  const edges = ref([])
  const loading = ref(false)
  const saving = ref(false)
  const saveMessage = ref('')

  function applyGraph(data, { backfillDefaults = true } = {}) {
    nodes.value = Array.isArray(data?.nodes)
      ? data.nodes.map((n) => normalizeGraphNode(n, { backfillDefaults }))
      : []
    edges.value = Array.isArray(data?.edges) ? data.edges.map((e) => ({ ...e })) : []
  }

  async function fetchGraph() {
    loading.value = true
    try {
      const res = await getKnowledgeGraphAPI()
      if (Array.isArray(res?.data?.nodes)) {
        applyGraph(res.data, { backfillDefaults: true })
        writeLocalGraph({ nodes: nodes.value, edges: edges.value })
        return
      }
      const local = readLocalGraph() || cloneDefaultGraph()
      applyGraph(local, { backfillDefaults: true })
    } catch {
      const local = readLocalGraph() || cloneDefaultGraph()
      applyGraph(local, { backfillDefaults: true })
    } finally {
      loading.value = false
    }
  }

  async function persistGraph(nextGraph, tip = '已保存图谱更改') {
    const payload = nextGraph || { nodes: nodes.value, edges: edges.value }
    applyGraph(payload, { backfillDefaults: false })
    writeLocalGraph(payload)

    saving.value = true
    try {
      await saveKnowledgeGraphAPI(payload)
      saveMessage.value = tip
    } catch {
      saveMessage.value = `${tip}（本地已生效）`
    } finally {
      saving.value = false
    }
  }

  async function resetToDefault() {
    saving.value = true
    try {
      const res = await resetKnowledgeGraphAPI()
      const fresh = res?.data?.nodes ? res.data : cloneDefaultGraph()
      applyGraph(fresh)
      writeLocalGraph(fresh)
      saveMessage.value = '已恢复初始知识图谱'
    } catch {
      const fresh = cloneDefaultGraph()
      applyGraph(fresh)
      writeLocalGraph(fresh)
      saveMessage.value = '已恢复初始知识图谱'
    } finally {
      saving.value = false
    }
  }

  return {
    nodes,
    edges,
    loading,
    saving,
    saveMessage,
    fetchGraph,
    persistGraph,
    resetToDefault,
  }
})
