<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { FolderOpen, Plus, RefreshCw, Search, Trash2, Upload } from 'lucide-vue-next'
import { formatFileSize, useTextbookStore } from '@/stores/textbookStore'

const props = defineProps({
  isTeacher: {
    type: Boolean,
    default: false,
  },
})

const textbookStore = useTextbookStore()
const { textbooks, activeTabName, drawerOpen, loading, uploading, notice, noticeType } =
  storeToRefs(textbookStore)

const selectedName = ref('')
const searchQuery = ref('')
const isDraggingOver = ref(false)
const fileInputRef = ref(null)

const filteredBooks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return textbooks.value
  return textbooks.value.filter((item) => item.name.toLowerCase().includes(q))
})

function shortBadgeText(title) {
  const match = String(title || '').match(/^[A-Za-z0-9_-]{1,6}/)
  return match ? match[0].toUpperCase() : String(title || '').slice(0, 3)
}

function selectBook(book) {
  selectedName.value = book.name
}

function clearSelection() {
  selectedName.value = ''
}

function openBook(book) {
  selectedName.value = book.name
  textbookStore.openBookInReader(book)
}

function triggerFileDialog() {
  if (!props.isTeacher) return
  fileInputRef.value?.click()
}

async function onFileInputChange(event) {
  if (!props.isTeacher) {
    event.target.value = ''
    return
  }
  const files = event.target.files
  if (files?.length) {
    await textbookStore.addFiles(files)
  }
  event.target.value = ''
}

async function deleteSelected() {
  if (!props.isTeacher || !selectedName.value) return
  const target = selectedName.value
  selectedName.value = ''
  await textbookStore.removeFiles(target)
}

async function deleteSingle(bookName) {
  if (!props.isTeacher) return
  if (selectedName.value === bookName) {
    selectedName.value = ''
  }
  await textbookStore.removeFiles(bookName)
}

function onCanvasKeydown(event) {
  if (!selectedName.value) return
  if (props.isTeacher && (event.key === 'Delete' || event.key === 'Backspace')) {
    event.preventDefault()
    deleteSelected()
  } else if (event.key === 'Enter') {
    const found = textbooks.value.find((b) => b.name === selectedName.value)
    if (found) openBook(found)
  }
}

function onDragOver(event) {
  if (!props.isTeacher) return
  event.preventDefault()
  isDraggingOver.value = true
}

function onDragLeave(event) {
  if (!props.isTeacher) return
  if (event.currentTarget === event.target) {
    isDraggingOver.value = false
  }
}

async function onDrop(event) {
  if (!props.isTeacher) return
  event.preventDefault()
  isDraggingOver.value = false
  const files = event.dataTransfer?.files
  if (files?.length) {
    await textbookStore.addFiles(files)
  }
}

onMounted(() => {
  textbookStore.clearNotice()
  textbookStore.fetchTextbooks({ force: true })
})
</script>

<template>
  <div
    class="finder-container"
    :class="{ 'is-dragging': props.isTeacher && isDraggingOver }"
    tabindex="0"
    aria-label="教材文件夹大图视图"
    @click="clearSelection"
    @keydown="onCanvasKeydown"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <!-- 顶部仿 macOS Finder 工具栏 -->
    <div class="finder-toolbar" @click.stop>
      <div class="finder-path">
        <FolderOpen :size="16" color="#ffffff" :stroke-width="1.85" />
        <span class="folder-title">教材文件夹</span>
        <span class="folder-count">{{ filteredBooks.length }} 项</span>
        <span v-if="!props.isTeacher" class="folder-readonly">只读</span>
        <span class="folder-tip">
          {{ props.isTeacher ? '双击文件在右侧阅读器打开，支持上传与删除' : '双击文件在右侧阅读器打开' }}
        </span>
      </div>

      <div class="finder-actions">
        <div class="finder-search">
          <Search :size="14" color="#ffffff" class="search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索文件"
            aria-label="搜索教材文件"
          />
        </div>

        <button
          v-if="props.isTeacher"
          type="button"
          class="finder-btn"
          :disabled="uploading"
          @click="triggerFileDialog"
        >
          <Plus :size="15" color="#ffffff" :stroke-width="2" />
          <span>{{ uploading ? '添加中…' : '添加文件' }}</span>
        </button>

        <button
          v-if="props.isTeacher"
          type="button"
          class="finder-btn danger"
          :disabled="!selectedName"
          title="删除当前选中的文件（也可按 Delete 键）"
          @click="deleteSelected"
        >
          <Trash2 :size="14" color="#ffffff" :stroke-width="1.9" />
          <span>删除</span>
        </button>

        <button
          type="button"
          class="finder-icon-btn"
          title="刷新文件夹"
          aria-label="刷新文件夹"
          @click="textbookStore.fetchTextbooks({ force: true })"
        >
          <RefreshCw :size="14" color="#ffffff" :stroke-width="1.9" />
        </button>

        <input
          v-if="props.isTeacher"
          ref="fileInputRef"
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          multiple
          hidden
          @change="onFileInputChange"
        />
      </div>
    </div>

    <div
      v-if="notice"
      class="finder-notice"
      :class="{ 'is-error': noticeType === 'error' }"
      role="status"
      @click.stop
    >
      {{ notice }}
    </div>

    <!-- 主体：仿 macOS 文件夹大图图标网格 -->
    <div class="finder-canvas">
      <div v-if="loading && !textbooks.length" class="finder-empty">
        正在读取教材文件夹…
      </div>

      <div
        v-else-if="!filteredBooks.length && (!props.isTeacher || searchQuery.trim())"
        class="finder-empty"
      >
        {{ searchQuery.trim() ? '未找到匹配的教材文件' : '暂无可阅读的教材文件' }}
      </div>

      <div v-else class="finder-grid" role="list">
        <div
          v-for="book in filteredBooks"
          :key="book.name"
          role="listitem"
          class="finder-item"
          :class="{
            selected: selectedName === book.name,
            opened: drawerOpen && activeTabName === book.name,
          }"
          :title="`双击打开 ${book.name}`"
          @click.stop="selectBook(book)"
          @dblclick.stop="openBook(book)"
        >
          <!-- 悬停快捷删除角标（仅教师端显示） -->
          <button
            v-if="props.isTeacher"
            type="button"
            class="item-quick-del"
            :aria-label="`删除 ${book.name}`"
            title="删除此文件"
            @click.stop="deleteSingle(book.name)"
          >
            <Trash2 :size="12" color="#ffffff" />
          </button>

          <!-- 仿 macOS QuickLook 文档缩略大图 -->
          <div class="thumb-frame">
            <div class="doc-sheet">
              <span class="doc-corner" aria-hidden="true" />
              <div class="doc-mini-header">
                <span class="doc-code">{{ shortBadgeText(book.title) }}</span>
              </div>
              <div class="doc-lines" aria-hidden="true">
                <span class="line w-90" />
                <span class="line w-75" />
                <span class="line w-85" />
                <span class="line w-60" />
              </div>
              <div class="doc-title-snippet">{{ book.title }}</div>
              <span class="doc-ext-badge" :class="{ 'is-txt': book.ext === 'TXT' }">
                {{ book.ext || 'PDF' }}
              </span>
            </div>
          </div>

          <!-- 文件名与大小（选中态仿 macOS 蓝底胶囊） -->
          <div class="item-caption">
            <span class="item-name">{{ book.name }}</span>
            <span class="item-size">{{ formatFileSize(book.size) }}</span>
          </div>
        </div>

        <!-- 末尾快捷添加文件大图占位格（仅教师端显示） -->
        <button
          v-if="props.isTeacher"
          type="button"
          class="finder-add-tile"
          title="点击或拖拽文件到此添加教材"
          @click.stop="triggerFileDialog"
        >
          <div class="add-thumb">
            <Upload :size="24" color="#ffffff" :stroke-width="1.75" />
          </div>
          <span class="add-label">添加文件</span>
        </button>
      </div>
    </div>

    <!-- 底部仿 macOS Finder 状态栏 -->
    <footer class="finder-statusbar" @click.stop>
      <span>共 {{ textbooks.length }} 个文件</span>
      <span v-if="selectedName">
        {{
          props.isTeacher
            ? `已选中：${selectedName}（双击打开阅读，按 Delete 删除）`
            : `已选中：${selectedName}（双击或按 Enter 在右侧阅读器打开）`
        }}
      </span>
      <span v-else>
        {{
          props.isTeacher
            ? '支持拖拽 PDF / TXT 文件到窗口内直接添加'
            : '只读模式 · 双击任意教材在右侧阅读器打开'
        }}
      </span>
    </footer>
  </div>
</template>

<style scoped>
.finder-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
  outline: none;
  user-select: none;
  position: relative;
}

.finder-container.is-dragging::after {
  content: '松开鼠标以添加教材文件';
  position: absolute;
  inset: 12px;
  border: 2px dashed #0a84ff;
  border-radius: 14px;
  background: rgba(10, 132, 255, 0.12);
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 10;
}

.finder-toolbar {
  min-height: 50px;
  padding: 8px 18px;
  background: #232323;
  border-bottom: 1px solid #2e2e2e;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  flex-shrink: 0;
}

.finder-path {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.folder-title {
  color: #f2f2f2;
  font-size: 13.5px;
  font-weight: 600;
}

.folder-count {
  padding: 1px 8px;
  border-radius: 999px;
  background: #303030;
  color: #b8b8b8;
  font-size: 11.5px;
}

.folder-readonly {
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(10, 132, 255, 0.14);
  border: 1px solid rgba(10, 132, 255, 0.28);
  color: #9ecbff;
  font-size: 11px;
  font-weight: 500;
}

.folder-tip {
  color: #7d7d7d;
  font-size: 12px;
  margin-left: 4px;
}

.finder-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.finder-search {
  width: 176px;
  height: 30px;
  padding: 0 10px;
  border-radius: 7px;
  background: #181818;
  border: 1px solid #343434;
  display: flex;
  align-items: center;
  gap: 6px;
}

.finder-search:focus-within {
  border-color: #0a84ff;
}

.search-icon {
  opacity: 0.65;
  flex-shrink: 0;
}

.finder-search input {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: #ededed;
  font-size: 12.5px;
}

.finder-search input::placeholder {
  color: #727272;
}

.finder-btn {
  width: auto;
  height: 30px;
  padding: 0 12px;
  border: 1px solid #3a3a3a;
  border-radius: 7px;
  background: #2c2c2c;
  color: #ffffff;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}

.finder-btn:hover:not(:disabled) {
  background: #383838;
  border-color: #4d4d4d;
}

.finder-btn.danger:hover:not(:disabled) {
  background: #5c2323;
  border-color: #843535;
}

.finder-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.finder-icon-btn {
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

.finder-icon-btn:hover {
  background: #353535;
  opacity: 1;
}

.finder-notice {
  padding: 7px 18px;
  background: #1d2a3a;
  border-bottom: 1px solid #2a3e57;
  color: #cfe4ff;
  font-size: 12px;
  flex-shrink: 0;
}

.finder-notice.is-error {
  background: #331d1f;
  border-bottom-color: #5a2b30;
  color: #ffc9cd;
}

/* 仿 macOS 文件夹大图画布 */
.finder-canvas {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 26px 24px 32px;
  scrollbar-width: thin;
  scrollbar-color: #383838 transparent;
}

.finder-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #808080;
  font-size: 13.5px;
}

.finder-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(136px, 1fr));
  gap: 24px 16px;
  align-items: start;
}

.finder-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  border-radius: 10px;
  cursor: default;
}

.item-quick-del {
  position: absolute;
  top: 8px;
  right: 14px;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  background: rgba(24, 24, 24, 0.82);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  cursor: pointer;
  z-index: 2;
  transition: opacity 0.15s ease, background-color 0.15s ease;
}

.finder-item:hover .item-quick-del {
  opacity: 0.88;
}

.item-quick-del:hover {
  background: #b43434;
  opacity: 1 !important;
}

.thumb-frame {
  width: 118px;
  height: 142px;
  padding: 8px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.14s ease, transform 0.14s ease;
}

.finder-item:hover .thumb-frame {
  background: rgba(255, 255, 255, 0.05);
}

.finder-item.selected .thumb-frame {
  background: rgba(255, 255, 255, 0.13);
}

.finder-item.opened .doc-sheet {
  box-shadow:
    0 0 0 2px #0a84ff,
    0 10px 24px rgba(0, 0, 0, 0.55);
}

/* 仿 macOS 文档纸张缩略大图 */
.doc-sheet {
  position: relative;
  width: 96px;
  height: 124px;
  padding: 12px 10px 10px;
  border-radius: 6px;
  background: linear-gradient(180deg, #fafafa 0%, #ededf0 100%);
  box-shadow:
    0 8px 20px rgba(0, 0, 0, 0.48),
    0 1px 2px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
}

.doc-corner {
  position: absolute;
  top: 0;
  right: 0;
  width: 18px;
  height: 18px;
  background: linear-gradient(225deg, #1e1e1e 50%, #d4d4d8 50%);
  border-bottom-left-radius: 4px;
  box-shadow: -1px 1px 2px rgba(0, 0, 0, 0.12);
}

.doc-mini-header {
  display: flex;
  align-items: center;
}

.doc-code {
  font-size: 11px;
  font-weight: 800;
  color: #27272a;
  letter-spacing: 0.03em;
}

.doc-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 4px 0;
}

.line {
  display: block;
  height: 3px;
  border-radius: 2px;
  background: #d4d4d8;
}

.line.w-90 { width: 88%; }
.line.w-85 { width: 82%; }
.line.w-75 { width: 70%; }
.line.w-60 { width: 55%; }

.doc-title-snippet {
  font-size: 9.5px;
  line-height: 1.3;
  color: #52525b;
  font-weight: 600;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

.doc-ext-badge {
  align-self: flex-start;
  padding: 1.5px 6px;
  border-radius: 3px;
  background: #dc2626;
  color: #ffffff;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.doc-ext-badge.is-txt {
  background: #3b82f6;
}

.item-caption {
  width: 100%;
  max-width: 132px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.item-name {
  max-width: 100%;
  padding: 2px 6px;
  border-radius: 5px;
  color: #e6e6e6;
  font-size: 12px;
  line-height: 1.35;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

.finder-item.selected .item-name {
  background: #0a84ff;
  color: #ffffff;
  font-weight: 500;
}

.item-size {
  color: #7c7c7c;
  font-size: 11px;
}

/* 末尾快捷添加卡片 */
.finder-add-tile {
  width: 100%;
  height: auto;
  padding: 6px 4px;
  border: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  letter-spacing: 0;
}

.add-thumb {
  width: 96px;
  height: 124px;
  margin: 9px 0;
  border: 1.5px dashed #3b3b3b;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.68;
  transition: border-color 0.16s ease, background-color 0.16s ease, opacity 0.16s ease;
}

.finder-add-tile:hover .add-thumb {
  border-color: #6b6b6b;
  background: rgba(255, 255, 255, 0.05);
  opacity: 1;
}

.add-label {
  color: #8f8f8f;
  font-size: 12px;
  font-weight: 500;
}

/* 底部仿 Finder 状态栏 */
.finder-statusbar {
  height: 28px;
  padding: 0 18px;
  background: #1a1a1a;
  border-top: 1px solid #292929;
  color: #7d7d7d;
  font-size: 11.5px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .folder-tip {
    display: none;
  }

  .finder-grid {
    grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
  }
}
</style>
