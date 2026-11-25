<script setup>
import { storeToRefs } from 'pinia'
import { BookOpen, ExternalLink, FileText, PanelRightClose, X } from 'lucide-vue-next'
import { formatFileSize, useTextbookStore } from '@/stores/textbookStore'

const props = defineProps({
  isTeacher: {
    type: Boolean,
    default: false,
  },
})

const textbookStore = useTextbookStore()
const { openTabs, activeTabName, activeTab, backendOnline } = storeToRefs(textbookStore)
</script>

<template>
  <aside class="pdf-reader-drawer" aria-label="教材 PDF 阅读器侧边栏">
    <!-- 顶部仿浏览器多标签页栏 -->
    <div class="reader-tabstrip">
      <div class="tabs-scroll" role="tablist" aria-label="已打开的教材标签">
        <div
          v-for="tab in openTabs"
          :key="tab.name"
          role="tab"
          tabindex="0"
          class="reader-tab"
          :class="{ active: activeTabName === tab.name }"
          :aria-selected="activeTabName === tab.name"
          :title="tab.name"
          @click="textbookStore.activateTab(tab.name)"
          @keydown.enter.prevent="textbookStore.activateTab(tab.name)"
        >
          <FileText :size="13" color="#ffffff" class="tab-icon" />
          <span class="tab-title">{{ tab.title }}</span>
          <button
            type="button"
            class="tab-close"
            :aria-label="`关闭 ${tab.title}`"
            @click.stop="textbookStore.closeTab(tab.name)"
          >
            <X :size="12" color="#ffffff" />
          </button>
        </div>
      </div>

      <button
        type="button"
        class="collapse-btn"
        title="收起阅读器侧边栏"
        aria-label="收起阅读器侧边栏"
        @click="textbookStore.drawerOpen = false"
      >
        <PanelRightClose :size="15" color="#ffffff" />
      </button>
    </div>

    <!-- 阅读器次级状态栏 -->
    <div v-if="activeTab" class="reader-subbar">
      <div class="doc-info">
        <BookOpen :size="13" color="#ffffff" class="sub-icon" />
        <span class="doc-filename">{{ activeTab.name }}</span>
        <span v-if="activeTab.page" class="doc-page-badge">第 {{ activeTab.page }} 页</span>
        <span v-if="activeTab.size" class="doc-filesize">{{ formatFileSize(activeTab.size) }}</span>
      </div>

      <a
        v-if="!activeTab.offlineFallback || backendOnline"
        class="open-ext-link"
        :href="textbookStore.resolvePreviewUrl(activeTab.url, activeTab.page)"
        target="_blank"
        rel="noopener noreferrer"
        title="在新浏览器窗口打开"
      >
        <ExternalLink :size="13" color="#ffffff" />
      </a>
    </div>

    <!-- PDF 阅读器内容主体 -->
    <div class="reader-body">
      <div v-if="!activeTab" class="reader-empty">
        <BookOpen :size="26" color="#ffffff" />
        <p>双击左侧教材文件夹中的任意文件即可在此打开阅读</p>
      </div>

      <div
        v-else-if="activeTab.offlineFallback && !backendOnline"
        class="reader-empty"
      >
        <BookOpen :size="28" color="#ffffff" />
        <h3>{{ activeTab.name }}</h3>
        <p>
          <template v-if="props.isTeacher">
            当前尚未启动 FastAPI 后端，启动后端后双击即可直接渲染此预设教材；你也可以在左侧点击「添加文件」放入任意本地 PDF 立即阅读。
          </template>
          <template v-else>
            当前尚未启动 FastAPI 后端，启动后端后双击即可直接阅读此教材。
          </template>
        </p>
      </div>

      <iframe
        v-else
        :key="`${activeTab.name}-${activeTab.page || 1}-${activeTab.jumpSeq || 0}`"
        class="pdf-frame"
        :src="textbookStore.resolvePreviewUrl(activeTab.url, activeTab.page)"
        :title="activeTab.name"
      />
    </div>
  </aside>
</template>

<style scoped>
.pdf-reader-drawer {
  width: clamp(380px, 46vw, 680px);
  height: 100%;
  flex-shrink: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #181818;
  border-left: 1px solid #2b2b2b;
  color: #e6e6e6;
}

.reader-tabstrip {
  height: 42px;
  padding: 6px 8px 0;
  background: #111111;
  border-bottom: 1px solid #262626;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  flex-shrink: 0;
}

.tabs-scroll {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: flex-end;
  gap: 3px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tabs-scroll::-webkit-scrollbar {
  display: none;
}

.reader-tab {
  max-width: 185px;
  min-width: 96px;
  height: 34px;
  padding: 0 8px 0 11px;
  border-radius: 9px 9px 0 0;
  background: #171717;
  border: 1px solid transparent;
  border-bottom: 0;
  color: #9a9a9a;
  font-size: 12.5px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.reader-tab:hover {
  background: #1e1e1e;
  color: #e6e6e6;
}

.reader-tab.active {
  background: #222222;
  border-color: #2e2e2e;
  color: #ffffff;
}

.tab-icon {
  flex-shrink: 0;
  opacity: 0.86;
}

.tab-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-close {
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: 0.65;
  cursor: pointer;
}

.tab-close:hover {
  background: rgba(255, 255, 255, 0.14);
  opacity: 1;
}

.collapse-btn {
  width: 28px;
  height: 28px;
  margin-bottom: 5px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: 0.82;
  cursor: pointer;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  opacity: 1;
}

.reader-subbar {
  height: 36px;
  padding: 0 12px;
  background: #222222;
  border-bottom: 1px solid #2d2d2d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-shrink: 0;
}

.doc-info {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 7px;
}

.sub-icon {
  flex-shrink: 0;
  opacity: 0.8;
}

.doc-filename {
  color: #dddddd;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-filesize {
  color: #828282;
  font-size: 11.5px;
  flex-shrink: 0;
}

.doc-page-badge {
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(10, 132, 255, 0.18);
  border: 1px solid rgba(10, 132, 255, 0.35);
  color: #9ecbff;
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.open-ext-link {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.8;
  flex-shrink: 0;
}

.open-ext-link:hover {
  background: rgba(255, 255, 255, 0.1);
  opacity: 1;
}

.reader-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
}

.pdf-frame {
  width: 100%;
  height: 100%;
  flex: 1;
  border: 0;
  background: #202020;
}

.reader-empty {
  flex: 1;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 10px;
  color: #969696;
}

.reader-empty h3 {
  margin: 4px 0 0;
  color: #ededed;
  font-size: 15px;
}

.reader-empty p {
  margin: 0;
  max-width: 310px;
  font-size: 13px;
  line-height: 1.65;
}

@media (max-width: 960px) {
  .pdf-reader-drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(92vw, 560px);
    z-index: 40;
    box-shadow: -16px 0 48px rgba(0, 0, 0, 0.68);
  }
}
</style>
