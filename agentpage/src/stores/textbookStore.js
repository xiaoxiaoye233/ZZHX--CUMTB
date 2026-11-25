import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { deleteTextbookAPI, getTextbooksAPI, uploadTextbookAPI } from '@/apis/agent'

const baseURL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

// 后端未启动时的内置教材快照（对应 agent/knowledge_base/textbook 目录）
const INITIAL_FALLBACK_FILES = [
  { name: 'B01_相关资料切片.pdf', size: 2286475, updated_at: '2026-11-17 11:23' },
  { name: 'B02_相关资料切片.pdf', size: 2600857, updated_at: '2026-11-17 11:23' },
  { name: 'B03_相关资料切片.pdf', size: 4312729, updated_at: '2026-11-17 11:23' },
  { name: 'B04_相关资料切片.pdf', size: 4867154, updated_at: '2026-11-17 11:23' },
  { name: 'B05_相关资料切片.pdf', size: 4251754, updated_at: '2026-11-17 11:23' },
  { name: 'B06_相关资料切片.pdf', size: 9586562, updated_at: '2026-11-17 11:23' },
  { name: 'B07_相关资料切片.pdf', size: 3253392, updated_at: '2026-11-17 11:23' },
  { name: 'B08_相关资料切片.pdf', size: 4125728, updated_at: '2026-11-17 11:23' },
].map((item) => ({
  ...item,
  title: item.name.replace(/\.[^.]+$/, ''),
  ext: 'PDF',
  url: `/api/agent/textbooks/${encodeURIComponent(item.name)}`,
  offlineFallback: true,
}))

function decorateBook(raw) {
  const name = String(raw.name || '')
  const extMatch = name.match(/\.([^.]+)$/)
  const ext = extMatch ? extMatch[1].toUpperCase() : 'PDF'
  return {
    ...raw,
    name,
    title: raw.title || name.replace(/\.[^.]+$/, ''),
    ext,
    size: Number(raw.size || 0),
    updated_at: raw.updated_at || '',
  }
}

export function formatFileSize(bytes) {
  const n = Number(bytes || 0)
  if (!n || n <= 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export const useTextbookStore = defineStore('textbook', () => {
  const textbooks = ref([])
  const openTabs = ref([])
  const activeTabName = ref('')
  const drawerOpen = ref(false)
  const loading = ref(false)
  const uploading = ref(false)
  const backendOnline = ref(true)
  const loadedOnce = ref(false)
  const notice = ref('')
  const noticeType = ref('info')
  const offlineRemovedSet = ref(new Set())
  let jumpCounter = 0

  function setNotice(message, type = 'info') {
    notice.value = message
    noticeType.value = type
  }

  function clearNotice() {
    notice.value = ''
    noticeType.value = 'info'
  }

  const activeTab = computed(
    () => openTabs.value.find((tab) => tab.name === activeTabName.value) || null,
  )

  function resolvePreviewUrl(url, page = null) {
    if (!url) return ''
    const base =
      url.startsWith('blob:') || url.startsWith('http://') || url.startsWith('https://')
        ? url
        : `${baseURL}${url}`
    const cleanBase = base.split('#')[0]
    const pageNum = Number.parseInt(page, 10)
    if (Number.isFinite(pageNum) && pageNum > 0 && !cleanBase.toLowerCase().endsWith('.txt')) {
      return `${cleanBase}#page=${pageNum}`
    }
    return cleanBase
  }

  async function fetchTextbooks({ force = false } = {}) {
    if (loading.value) return
    if (loadedOnce.value && !force) return

    loading.value = true
    try {
      const res = await getTextbooksAPI()
      const list = Array.isArray(res?.data) ? res.data : []
      backendOnline.value = true
      textbooks.value = list.map((item) => decorateBook({ ...item, offlineFallback: false }))
      // 同步已打开标签的最新元数据，保留当前定位的页码与翻页序号
      openTabs.value = openTabs.value
        .map((tab) => {
          const found = textbooks.value.find((b) => b.name === tab.name)
          if (found) {
            return { ...found, page: tab.page ?? null, jumpSeq: tab.jumpSeq ?? 0 }
          }
          return tab.isLocalBlob ? tab : null
        })
        .filter(Boolean)
      if (activeTabName.value && !openTabs.value.some((t) => t.name === activeTabName.value)) {
        activeTabName.value = openTabs.value[0]?.name || ''
      }
    } catch {
      backendOnline.value = false
      const localItems = textbooks.value.filter((item) => item.isLocalBlob)
      const preset = INITIAL_FALLBACK_FILES.filter(
        (item) => !offlineRemovedSet.value.has(item.name) && !localItems.some((l) => l.name === item.name),
      )
      textbooks.value = [...localItems, ...preset]
    } finally {
      loadedOnce.value = true
      loading.value = false
    }
  }

  // 双击某个教材：打开右侧阅读器侧边栏并在浏览器式标签页中展示它
  function openBookInReader(book) {
    if (!book?.name) return
    const existing = openTabs.value.find((tab) => tab.name === book.name)
    if (!existing) {
      openTabs.value.push({ ...book, page: book.page ?? null, jumpSeq: jumpCounter })
    } else {
      Object.assign(existing, book)
    }
    activeTabName.value = book.name
    drawerOpen.value = true
  }

  // 对话命中教材知识点或教材题目时：自动展开右侧阅读器并精准翻到对应页码
  function openTextbookAtPage(refInfo) {
    if (!refInfo?.name) return
    if (!loadedOnce.value && !loading.value) {
      fetchTextbooks()
    }

    const pageNum = Math.max(1, Number.parseInt(refInfo.page, 10) || 1)
    jumpCounter += 1

    const matched =
      textbooks.value.find((b) => b.name === refInfo.name) ||
      INITIAL_FALLBACK_FILES.find((b) => b.name === refInfo.name)
    const book = matched
      ? { ...matched, offlineFallback: matched.offlineFallback && !backendOnline.value }
      : decorateBook({
          name: refInfo.name,
          title: refInfo.title,
          url: refInfo.url || `/api/agent/textbooks/${encodeURIComponent(refInfo.name)}`,
          offlineFallback: false,
        })

    const existing = openTabs.value.find((tab) => tab.name === book.name)
    if (!existing) {
      openTabs.value.push({ ...book, page: pageNum, jumpSeq: jumpCounter })
    } else {
      Object.assign(existing, book, { page: pageNum, jumpSeq: jumpCounter })
    }
    activeTabName.value = book.name
    drawerOpen.value = true
  }

  function activateTab(tabName) {
    if (!tabName) return
    activeTabName.value = tabName
  }

  function closeTab(tabName) {
    const idx = openTabs.value.findIndex((tab) => tab.name === tabName)
    if (idx === -1) return
    openTabs.value.splice(idx, 1)

    if (activeTabName.value === tabName) {
      if (openTabs.value.length > 0) {
        const nextIdx = Math.min(idx, openTabs.value.length - 1)
        activeTabName.value = openTabs.value[nextIdx].name
      } else {
        activeTabName.value = ''
        drawerOpen.value = false
      }
    }
  }

  function toggleDrawer() {
    if (drawerOpen.value) {
      drawerOpen.value = false
      return
    }
    drawerOpen.value = true
    if (!openTabs.value.length && textbooks.value.length) {
      openBookInReader(textbooks.value[0])
    }
  }

  async function addFiles(fileList) {
    const files = Array.from(fileList || [])
    if (!files.length) return

    uploading.value = true
    clearNotice()
    let addedCount = 0
    let lastError = ''

    for (const file of files) {
      const lower = file.name.toLowerCase()
      if (!lower.endsWith('.pdf') && !lower.endsWith('.txt')) {
        lastError = '仅支持添加 PDF 或 TXT 格式文件'
        continue
      }

      try {
        const res = await uploadTextbookAPI(file)
        const saved = res?.data
        backendOnline.value = true
        if (saved?.name) {
          const book = decorateBook({ ...saved, offlineFallback: false })
          const idx = textbooks.value.findIndex((b) => b.name === book.name)
          if (idx >= 0) {
            textbooks.value.splice(idx, 1, book)
          } else {
            textbooks.value.unshift(book)
          }
          const tabIdx = openTabs.value.findIndex((t) => t.name === book.name)
          if (tabIdx >= 0) openTabs.value.splice(tabIdx, 1, { ...book })
          addedCount += 1
        }
      } catch (err) {
        // 后端明确返回 HTTP 错误（如 401/403 权限不足、400 文件非法）时，绝不伪造本地上传成功
        if (err?.status) {
          backendOnline.value = true
          lastError =
            err.message ||
            (err.status === 401 || err.status === 403
              ? '仅教师可添加教材文件'
              : `添加「${file.name}」失败`)
          continue
        }

        // 仅在后端离线/网络不可达时使用浏览器本地 Blob 兜底预览
        backendOnline.value = false
        const blobUrl = URL.createObjectURL(file)
        offlineRemovedSet.value.delete(file.name)
        const localBook = decorateBook({
          name: file.name,
          size: file.size,
          updated_at: '刚刚添加',
          url: blobUrl,
          isLocalBlob: true,
          offlineFallback: false,
        })
        const idx = textbooks.value.findIndex((b) => b.name === localBook.name)
        if (idx >= 0) {
          if (textbooks.value[idx].isLocalBlob && textbooks.value[idx].url) {
            URL.revokeObjectURL(textbooks.value[idx].url)
          }
          textbooks.value.splice(idx, 1, localBook)
        } else {
          textbooks.value.unshift(localBook)
        }
        const tabIdx = openTabs.value.findIndex((t) => t.name === localBook.name)
        if (tabIdx >= 0) openTabs.value.splice(tabIdx, 1, { ...localBook })
        addedCount += 1
      }
    }

    if (addedCount > 0 && lastError) {
      setNotice(`成功添加 ${addedCount} 个文件；部分失败：${lastError}`, 'error')
    } else if (addedCount > 0) {
      setNotice(`成功添加 ${addedCount} 个文件`, 'info')
    } else if (lastError) {
      setNotice(lastError, 'error')
    }
    uploading.value = false
  }

  async function removeFiles(names) {
    const targets = Array.isArray(names) ? names.filter(Boolean) : [names].filter(Boolean)
    if (!targets.length) return

    clearNotice()
    const removedNames = []
    let lastError = ''

    for (const name of targets) {
      const targetBook = textbooks.value.find((b) => b.name === name)
      if (!targetBook) continue

      if (!targetBook.isLocalBlob && !targetBook.offlineFallback && backendOnline.value) {
        try {
          await deleteTextbookAPI(name)
        } catch (err) {
          lastError =
            err?.message ||
            (err?.status === 401 || err?.status === 403
              ? '仅教师可删除教材文件'
              : `删除「${name}」失败`)
          continue
        }
      } else if (targetBook.offlineFallback && backendOnline.value) {
        try {
          await deleteTextbookAPI(name)
        } catch (err) {
          if (err?.status === 401 || err?.status === 403) {
            lastError = err.message || '仅教师可删除教材文件'
            continue
          }
          // 离线兜底项在非权限错误时直接本地移除
        }
      }

      if (targetBook.isLocalBlob && targetBook.url) {
        URL.revokeObjectURL(targetBook.url)
      }
      offlineRemovedSet.value.add(name)
      textbooks.value = textbooks.value.filter((b) => b.name !== name)
      closeTab(name)
      removedNames.push(name)
    }

    if (removedNames.length > 0 && lastError) {
      setNotice(`已删除 ${removedNames.length} 个文件；部分失败：${lastError}`, 'error')
    } else if (removedNames.length > 1) {
      setNotice(`已删除 ${removedNames.length} 个文件`, 'info')
    } else if (removedNames.length === 1) {
      setNotice(`已删除「${removedNames[0]}」`, 'info')
    } else if (lastError) {
      setNotice(lastError, 'error')
    }
  }

  return {
    textbooks,
    openTabs,
    activeTabName,
    activeTab,
    drawerOpen,
    loading,
    uploading,
    backendOnline,
    notice,
    noticeType,
    clearNotice,
    resolvePreviewUrl,
    fetchTextbooks,
    openBookInReader,
    openTextbookAtPage,
    activateTab,
    closeTab,
    toggleDrawer,
    addFiles,
    removeFiles,
  }
})
