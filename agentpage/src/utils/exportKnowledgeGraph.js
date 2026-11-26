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

function derivePalette(node) {
  const fallback = THEME_DEFAULT_COLORS[node?.theme] || '#3b82f6'
  const border = normalizeHex(node?.color, fallback)
  const r = Number.parseInt(border.slice(1, 3), 16)
  const g = Number.parseInt(border.slice(3, 5), 16)
  const b = Number.parseInt(border.slice(5, 7), 16)
  const bgR = Math.round(r * 0.28 + 18 * 0.72)
  const bgG = Math.round(g * 0.28 + 20 * 0.72)
  const bgB = Math.round(b * 0.28 + 24 * 0.72)
  return {
    bg: `rgb(${bgR}, ${bgG}, ${bgB})`,
    border,
  }
}

function escapeXml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

function sanitizeGraph(nodes = [], edges = []) {
  const cleanNodes = (Array.isArray(nodes) ? nodes : []).map((n, idx) => {
    const palette = derivePalette(n)
    const refs = Array.isArray(n?.textbook_refs)
      ? n.textbook_refs
          .filter((r) => r && String(r.name || '').trim())
          .map((r) => ({
            name: String(r.name).trim(),
            page: Math.max(1, Number.parseInt(r.page, 10) || 1),
            label: String(r.label || '').trim(),
          }))
      : []
    return {
      id: String(n?.id || `node-${idx + 1}`).trim(),
      name: String(n?.name || '未命名知识点').trim() || '未命名知识点',
      theme: String(n?.theme || '').trim(),
      description: String(n?.description || '').trim(),
      textbook_refs: refs,
      color: palette.border,
      bg: palette.bg,
      x: Number.isFinite(Number(n?.x)) ? Number(n.x) : 220 + (idx % 4) * 300,
      y: Number.isFinite(Number(n?.y)) ? Number(n.y) : 160 + Math.floor(idx / 4) * 160,
    }
  })

  const validIds = new Set(cleanNodes.map((n) => n.id))
  const cleanEdges = (Array.isArray(edges) ? edges : [])
    .filter((e) => validIds.has(String(e?.source || '')) && validIds.has(String(e?.target || '')))
    .map((e, idx) => ({
      id: String(e?.id || `${e.source}->${e.target}-${idx}`),
      source: String(e.source),
      target: String(e.target),
      relation: String(e?.relation || '').trim(),
    }))

  return { nodes: cleanNodes, edges: cleanEdges }
}

function formatTimestampForFilename(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1500)
}

// ==================== 1. 生成独立可交互离线 HTML ====================
export function buildKnowledgeGraphHtml({ nodes = [], edges = [], roleLabel = '' } = {}) {
  const graph = sanitizeGraph(nodes, edges)
  const exportedAt = new Date().toLocaleString('zh-CN', { hour12: false })
  const safeJson = JSON.stringify({
    nodes: graph.nodes,
    edges: graph.edges,
    roleLabel: roleLabel || '智教慧学',
    exportedAt,
  }).replaceAll('<', '\\u003c')

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>智教慧学 · 知识图谱</title>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #141416;
      color: #f4f4f5;
      font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", "PingFang SC", sans-serif;
    }
    .app {
      display: flex;
      flex-direction: column;
      width: 100%;
      height: 100%;
    }
    .topbar {
      height: 52px;
      padding: 0 18px;
      background: #1d1d20;
      border-bottom: 1px solid #2d2d32;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-shrink: 0;
      z-index: 10;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }
    .brand h1 {
      margin: 0;
      font-size: 15.5px;
      font-weight: 700;
      color: #ffffff;
      white-space: nowrap;
    }
    .badge {
      padding: 2px 9px;
      border-radius: 999px;
      background: #27272c;
      border: 1px solid #383842;
      color: #a1a1aa;
      font-size: 12px;
      white-space: nowrap;
    }
    .controls {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .search-input {
      width: 190px;
      height: 31px;
      padding: 0 10px;
      border: 1px solid #36363d;
      border-radius: 7px;
      background: #141416;
      color: #f4f4f5;
      font-size: 12.5px;
      outline: none;
    }
    .search-input:focus { border-color: #3b82f6; }
    .btn {
      height: 31px;
      padding: 0 12px;
      border: 1px solid #383840;
      border-radius: 7px;
      background: #26262b;
      color: #f4f4f5;
      font-size: 12.5px;
      font-weight: 500;
      cursor: pointer;
    }
    .btn:hover { background: #32323a; border-color: #4b4b57; }
    .main {
      flex: 1;
      min-height: 0;
      display: flex;
    }
    .viewport {
      flex: 1;
      min-width: 0;
      position: relative;
      overflow: hidden;
      cursor: grab;
      user-select: none;
      background-color: #161618;
      background-image: radial-gradient(#2a2a2f 1px, transparent 1px);
      background-size: 22px 22px;
    }
    .viewport.panning { cursor: grabbing; }
    .world {
      position: absolute;
      left: 0;
      top: 0;
      transform-origin: 0 0;
      will-change: transform;
    }
    .edges-svg {
      position: absolute;
      left: 0;
      top: 0;
      width: 1px;
      height: 1px;
      overflow: visible;
      pointer-events: none;
    }
    .edge-path {
      fill: none;
      stroke: #52525b;
      stroke-width: 2.4;
      transition: opacity 0.16s ease, stroke 0.16s ease, stroke-width 0.16s ease;
    }
    .edge-path.is-prev { stroke: #38bdf8; stroke-width: 3.1; }
    .edge-path.is-next { stroke: #34d399; stroke-width: 3.1; }
    .edge-path.is-dimmed { opacity: 0.2; }
    .node-card {
      position: absolute;
      width: 236px;
      min-height: 84px;
      padding: 12px 14px;
      border-radius: 12px;
      border: 2.5px solid #3b82f6;
      color: #f8fafc;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 5px;
      text-align: center;
      cursor: pointer;
      box-shadow: 0 10px 26px rgba(0, 0, 0, 0.36);
      transition: opacity 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
    }
    .node-card .theme-pill {
      font-size: 10.5px;
      color: rgba(255, 255, 255, 0.72);
      background: rgba(0, 0, 0, 0.28);
      padding: 1px 7px;
      border-radius: 999px;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .node-card .node-title {
      font-size: 15px;
      font-weight: 600;
      line-height: 1.35;
      word-break: break-word;
    }
    .node-card.is-selected {
      border-width: 3.5px;
      border-color: #ffffff !important;
      box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.16), 0 14px 30px rgba(0, 0, 0, 0.5);
    }
    .node-card.is-prev { border-color: #38bdf8 !important; border-width: 3px; }
    .node-card.is-next { border-color: #34d399 !important; border-width: 3px; }
    .node-card.is-dimmed { opacity: 0.22; }
    .legend {
      position: absolute;
      left: 14px;
      bottom: 14px;
      padding: 7px 12px;
      border-radius: 8px;
      background: rgba(24, 24, 28, 0.88);
      border: 1px solid #2e2e36;
      color: #a1a1aa;
      font-size: 12px;
      display: flex;
      gap: 14px;
      pointer-events: none;
    }
    .dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      margin-right: 5px;
    }
    .inspector {
      width: 350px;
      flex-shrink: 0;
      background: #1c1c1f;
      border-left: 1px solid #2c2c32;
      padding: 20px 18px 28px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 15px;
    }
    .ins-theme {
      display: inline-block;
      align-self: flex-start;
      padding: 2px 9px;
      border-radius: 6px;
      background: #27272d;
      color: #cbd5e1;
      font-size: 11.5px;
    }
    .ins-title { margin: 0; font-size: 17px; font-weight: 700; line-height: 1.4; }
    .desc-box {
      padding: 12px 14px;
      border-radius: 10px;
      background: #141417;
      border: 1px solid #2a2a30;
    }
    .desc-box h3 { margin: 0 0 6px; font-size: 12px; color: #9ca3af; }
    .desc-box p { margin: 0; font-size: 13.5px; line-height: 1.65; color: #e4e4e7; }
    .rel-block h3 { margin: 0 0 8px; font-size: 13px; }
    .rel-prev-h { color: #7dd3fc; }
    .rel-next-h { color: #6ee7b7; }
    .rel-card {
      width: 100%;
      margin-bottom: 8px;
      padding: 10px 12px;
      border-radius: 9px;
      background: #141417;
      border: 1px solid #2c2c34;
      color: #f4f4f5;
      text-align: left;
      cursor: pointer;
    }
    .rel-card:hover { border-color: #52525b; background: #19191e; }
    .rel-card strong { display: block; font-size: 13.5px; margin-bottom: 4px; }
    .rel-card span { display: block; font-size: 12px; color: #9ca3af; line-height: 1.45; }
    .empty-tip { margin: 0; padding: 8px 10px; border-radius: 8px; background: #151518; color: #71717a; font-size: 12px; }
    @media (max-width: 860px) {
      .main { flex-direction: column; }
      .inspector { width: 100%; height: 44%; border-left: 0; border-top: 1px solid #2c2c32; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <h1>智教慧学 · 知识图谱</h1>
        <span id="statsBadge" class="badge"></span>
      </div>
      <div class="controls">
        <input id="searchInput" class="search-input" type="search" placeholder="搜索知识点名称…" />
        <button id="layoutBtn" class="btn" type="button">自动排版</button>
        <button id="fitBtn" class="btn" type="button">居中适配</button>
      </div>
    </header>

    <div class="main">
      <div id="viewport" class="viewport">
        <div id="world" class="world">
          <svg id="edgesSvg" class="edges-svg">
            <defs>
              <marker id="arrow-default" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
                <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#71717a" />
              </marker>
              <marker id="arrow-prev" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
                <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#38bdf8" />
              </marker>
              <marker id="arrow-next" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
                <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#34d399" />
              </marker>
            </defs>
            <g id="edgesGroup"></g>
          </svg>
          <div id="nodesLayer"></div>
        </div>
        <div class="legend">
          <span><i class="dot" style="background:#ffffff"></i>当前选中</span>
          <span><i class="dot" style="background:#38bdf8"></i>前置知识</span>
          <span><i class="dot" style="background:#34d399"></i>后续知识</span>
          <span>滚轮缩放 · 拖拽平移或移动卡片</span>
        </div>
      </div>

      <aside id="inspector" class="inspector"></aside>
    </div>
  </div>

  <script>
    const DATA = ${safeJson};
    const CARD_W = 236;
    const CARD_H = 84;
    const nodes = DATA.nodes.map(n => ({ ...n }));
    const edges = DATA.edges.map(e => ({ ...e }));
    const nodeById = new Map(nodes.map(n => [n.id, n]));

    document.getElementById('statsBadge').textContent =
      nodes.length + ' 个知识点 · ' + edges.length + ' 条关联 · 导出于 ' + DATA.exportedAt;

    const viewport = document.getElementById('viewport');
    const world = document.getElementById('world');
    const nodesLayer = document.getElementById('nodesLayer');
    const edgesGroup = document.getElementById('edgesGroup');
    const inspector = document.getElementById('inspector');
    const searchInput = document.getElementById('searchInput');

    let panX = 0, panY = 0, scale = 1;
    let selectedId = nodes[0] ? nodes[0].id : '';
    let searchKeyword = '';

    const cardEls = new Map();
    const edgeEls = [];

    function applyTransform() {
      world.style.transform = 'translate(' + panX + 'px,' + panY + 'px) scale(' + scale + ')';
    }

    function boundaryPoint(cx, cy, tx, ty) {
      const dx = tx - cx;
      const dy = ty - cy;
      if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) return { x: cx, y: cy };
      const hw = CARD_W / 2 + 3;
      const hh = CARD_H / 2 + 3;
      const t = Math.min(hw / (Math.abs(dx) || 0.0001), hh / (Math.abs(dy) || 0.0001));
      return { x: cx + dx * t, y: cy + dy * t };
    }

    function updateEdgesGeometry() {
      for (const item of edgeEls) {
        const s = nodeById.get(item.edge.source);
        const t = nodeById.get(item.edge.target);
        if (!s || !t) continue;
        const p1 = boundaryPoint(s.x, s.y, t.x, t.y);
        const p2 = boundaryPoint(t.x, t.y, s.x, s.y);
        const bend = Math.max(45, Math.abs(p2.x - p1.x) * 0.42);
        const c1x = p1.x + (p2.x >= p1.x ? bend : -bend);
        const c2x = p2.x - (p2.x >= p1.x ? bend : -bend);
        item.path.setAttribute('d', 'M ' + p1.x + ' ' + p1.y + ' C ' + c1x + ' ' + p1.y + ', ' + c2x + ' ' + p2.y + ', ' + p2.x + ' ' + p2.y);
      }
    }

    function renderInspector() {
      inspector.textContent = '';
      const node = nodeById.get(selectedId);
      if (!node) {
        const empty = document.createElement('p');
        empty.className = 'empty-tip';
        empty.textContent = '点击左侧图谱中的任意知识点查看详情与前后置联系。';
        inspector.appendChild(empty);
        return;
      }

      if (node.theme) {
        const themeEl = document.createElement('span');
        themeEl.className = 'ins-theme';
        themeEl.textContent = node.theme;
        inspector.appendChild(themeEl);
      }

      const titleEl = document.createElement('h2');
      titleEl.className = 'ins-title';
      titleEl.textContent = node.name;
      inspector.appendChild(titleEl);

      const descBox = document.createElement('div');
      descBox.className = 'desc-box';
      const descH = document.createElement('h3');
      descH.textContent = '知识点介绍';
      const descP = document.createElement('p');
      descP.textContent = node.description || '暂无详细介绍';
      descBox.append(descH, descP);
      inspector.appendChild(descBox);

      if (Array.isArray(node.textbook_refs) && node.textbook_refs.length) {
        const tbSec = document.createElement('div');
        tbSec.className = 'rel-block';
        const tbH = document.createElement('h3');
        tbH.style.color = '#93c5fd';
        tbH.textContent = '对应教材位置（' + node.textbook_refs.length + '）';
        tbSec.appendChild(tbH);
        for (const r of node.textbook_refs) {
          const item = document.createElement('div');
          item.className = 'rel-card';
          item.style.cursor = 'default';
          const st = document.createElement('strong');
          st.textContent = r.name + ' · 第 ' + r.page + ' 页';
          item.appendChild(st);
          if (r.label) {
            const sp = document.createElement('span');
            sp.textContent = r.label;
            item.appendChild(sp);
          }
          tbSec.appendChild(item);
        }
        inspector.appendChild(tbSec);
      }

      const prevEdges = edges.filter(e => e.target === node.id);
      const nextEdges = edges.filter(e => e.source === node.id);

      function buildRelSection(headingText, cls, list, getOtherId) {
        const sec = document.createElement('div');
        sec.className = 'rel-block';
        const h = document.createElement('h3');
        h.className = cls;
        h.textContent = headingText + '（' + list.length + '）';
        sec.appendChild(h);
        if (!list.length) {
          const p = document.createElement('p');
          p.className = 'empty-tip';
          p.textContent = '暂无关联知识点';
          sec.appendChild(p);
        } else {
          for (const rel of list) {
            const other = nodeById.get(getOtherId(rel));
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'rel-card';
            const st = document.createElement('strong');
            st.textContent = other ? other.name : getOtherId(rel);
            btn.appendChild(st);
            if (rel.relation) {
              const sp = document.createElement('span');
              sp.textContent = rel.relation;
              btn.appendChild(sp);
            }
            btn.addEventListener('click', () => selectNode(getOtherId(rel), true));
            sec.appendChild(btn);
          }
        }
        return sec;
      }

      inspector.appendChild(buildRelSection('前置知识', 'rel-prev-h', prevEdges, e => e.source));
      inspector.appendChild(buildRelSection('后续知识', 'rel-next-h', nextEdges, e => e.target));
    }

    function updateHighlight() {
      const prevSet = new Set();
      const nextSet = new Set();
      if (selectedId) {
        for (const e of edges) {
          if (e.target === selectedId) prevSet.add(e.source);
          if (e.source === selectedId) nextSet.add(e.target);
        }
      }
      const kw = searchKeyword.trim().toLowerCase();

      for (const n of nodes) {
        const el = cardEls.get(n.id);
        if (!el) continue;
        el.classList.remove('is-selected', 'is-prev', 'is-next', 'is-dimmed');
        const matchesKw = !kw || n.name.toLowerCase().includes(kw) || (n.theme || '').toLowerCase().includes(kw);
        if (!matchesKw) {
          el.classList.add('is-dimmed');
          continue;
        }
        if (selectedId) {
          if (n.id === selectedId) el.classList.add('is-selected');
          else if (prevSet.has(n.id)) el.classList.add('is-prev');
          else if (nextSet.has(n.id)) el.classList.add('is-next');
          else if (!kw) el.classList.add('is-dimmed');
        }
      }

      for (const item of edgeEls) {
        const e = item.edge;
        item.path.classList.remove('is-prev', 'is-next', 'is-dimmed');
        if (selectedId) {
          if (e.target === selectedId) {
            item.path.classList.add('is-prev');
            item.path.setAttribute('marker-end', 'url(#arrow-prev)');
          } else if (e.source === selectedId) {
            item.path.classList.add('is-next');
            item.path.setAttribute('marker-end', 'url(#arrow-next)');
          } else {
            item.path.classList.add('is-dimmed');
            item.path.setAttribute('marker-end', 'url(#arrow-default)');
          }
        } else {
          item.path.setAttribute('marker-end', 'url(#arrow-default)');
        }
      }
    }

    function selectNode(id, centerOnNode) {
      selectedId = id;
      updateHighlight();
      renderInspector();
      const target = nodeById.get(id);
      if (centerOnNode && target) {
        const rect = viewport.getBoundingClientRect();
        panX = rect.width / 2 - target.x * scale;
        panY = rect.height / 2 - target.y * scale;
        applyTransform();
      }
    }

    function fitView() {
      if (!nodes.length) return;
      const rect = viewport.getBoundingClientRect();
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const n of nodes) {
        minX = Math.min(minX, n.x - CARD_W / 2);
        maxX = Math.max(maxX, n.x + CARD_W / 2);
        minY = Math.min(minY, n.y - CARD_H / 2);
        maxY = Math.max(maxY, n.y + CARD_H / 2);
      }
      const pad = 56;
      const gw = Math.max(1, maxX - minX);
      const gh = Math.max(1, maxY - minY);
      scale = Math.min(1.35, Math.max(0.32, Math.min((rect.width - pad * 2) / gw, (rect.height - pad * 2) / gh)));
      panX = (rect.width - gw * scale) / 2 - minX * scale;
      panY = (rect.height - gh * scale) / 2 - minY * scale;
      applyTransform();
    }

    function autoLayout() {
      const inDeg = new Map(nodes.map(n => [n.id, 0]));
      const outMap = new Map(nodes.map(n => [n.id, []]));
      for (const e of edges) {
        inDeg.set(e.target, (inDeg.get(e.target) || 0) + 1);
        outMap.get(e.source).push(e.target);
      }
      const layer = new Map();
      const queue = [];
      for (const n of nodes) {
        if ((inDeg.get(n.id) || 0) === 0) {
          layer.set(n.id, 0);
          queue.push(n.id);
        }
      }
      while (queue.length) {
        const cur = queue.shift();
        const curL = layer.get(cur) || 0;
        for (const nxt of outMap.get(cur) || []) {
          layer.set(nxt, Math.max(layer.get(nxt) || 0, curL + 1));
          inDeg.set(nxt, inDeg.get(nxt) - 1);
          if (inDeg.get(nxt) === 0) queue.push(nxt);
        }
      }
      const groups = new Map();
      for (const n of nodes) {
        const l = layer.get(n.id) || 0;
        if (!groups.has(l)) groups.set(l, []);
        groups.get(l).push(n);
      }
      for (const [l, list] of groups.entries()) {
        list.forEach((n, idx) => {
          n.x = 180 + l * 320;
          n.y = 140 + (idx - (list.length - 1) / 2) * 148 + 220;
          const el = cardEls.get(n.id);
          if (el) {
            el.style.left = (n.x - CARD_W / 2) + 'px';
            el.style.top = (n.y - CARD_H / 2) + 'px';
          }
        });
      }
      updateEdgesGeometry();
      fitView();
    }

    function mountGraph() {
      for (const e of edges) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', 'edge-path');
        path.setAttribute('marker-end', 'url(#arrow-default)');
        edgesGroup.appendChild(path);
        edgeEls.push({ edge: e, path });
      }

      for (const n of nodes) {
        const card = document.createElement('div');
        card.className = 'node-card';
        card.style.left = (n.x - CARD_W / 2) + 'px';
        card.style.top = (n.y - CARD_H / 2) + 'px';
        card.style.backgroundColor = n.bg;
        card.style.borderColor = n.color;

        if (n.theme) {
          const tp = document.createElement('span');
          tp.className = 'theme-pill';
          tp.textContent = n.theme;
          card.appendChild(tp);
        }
        const title = document.createElement('div');
        title.className = 'node-title';
        title.textContent = n.name;
        card.appendChild(title);

        let draggingNode = false;
        let moved = false;
        let startX = 0, startY = 0, origX = 0, origY = 0;

        card.addEventListener('pointerdown', (ev) => {
          ev.stopPropagation();
          draggingNode = true;
          moved = false;
          startX = ev.clientX;
          startY = ev.clientY;
          origX = n.x;
          origY = n.y;
          card.setPointerCapture(ev.pointerId);
        });
        card.addEventListener('pointermove', (ev) => {
          if (!draggingNode) return;
          const dx = (ev.clientX - startX) / scale;
          const dy = (ev.clientY - startY) / scale;
          if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
          n.x = origX + dx;
          n.y = origY + dy;
          card.style.left = (n.x - CARD_W / 2) + 'px';
          card.style.top = (n.y - CARD_H / 2) + 'px';
          updateEdgesGeometry();
        });
        card.addEventListener('pointerup', (ev) => {
          if (!draggingNode) return;
          draggingNode = false;
          card.releasePointerCapture(ev.pointerId);
          if (!moved) selectNode(n.id, false);
        });

        nodesLayer.appendChild(card);
        cardEls.set(n.id, card);
      }

      updateEdgesGeometry();
      fitView();
      updateHighlight();
      renderInspector();
    }

    let panning = false, pStartX = 0, pStartY = 0, pOrigX = 0, pOrigY = 0, panMoved = false;
    viewport.addEventListener('pointerdown', (ev) => {
      panning = true;
      panMoved = false;
      pStartX = ev.clientX;
      pStartY = ev.clientY;
      pOrigX = panX;
      pOrigY = panY;
      viewport.classList.add('panning');
      viewport.setPointerCapture(ev.pointerId);
    });
    viewport.addEventListener('pointermove', (ev) => {
      if (!panning) return;
      const dx = ev.clientX - pStartX;
      const dy = ev.clientY - pStartY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) panMoved = true;
      panX = pOrigX + dx;
      panY = pOrigY + dy;
      applyTransform();
    });
    viewport.addEventListener('pointerup', (ev) => {
      if (!panning) return;
      panning = false;
      viewport.classList.remove('panning');
      viewport.releasePointerCapture(ev.pointerId);
      if (!panMoved) {
        selectedId = '';
        updateHighlight();
        renderInspector();
      }
    });

    viewport.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      const factor = ev.deltaY < 0 ? 1.1 : 0.9;
      const nextScale = Math.min(2.6, Math.max(0.28, scale * factor));
      panX = mx - ((mx - panX) / scale) * nextScale;
      panY = my - ((my - panY) / scale) * nextScale;
      scale = nextScale;
      applyTransform();
    }, { passive: false });

    searchInput.addEventListener('input', () => {
      searchKeyword = searchInput.value;
      updateHighlight();
    });
    document.getElementById('fitBtn').addEventListener('click', fitView);
    document.getElementById('layoutBtn').addEventListener('click', autoLayout);
    window.addEventListener('resize', fitView);

    mountGraph();
  </script>
</body>
</html>`
}

// ==================== 2. 生成标准双兼容 .xmind (ZIP) 思维导图 ====================
const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let c = i
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    }
    table[i] = c >>> 0
  }
  return table
})()

function crc32(bytes) {
  let crc = 0xffffffff
  for (let i = 0; i < bytes.length; i += 1) {
    crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8)
  }
  return (crc ^ 0xffffffff) >>> 0
}

export function createZipArchive(fileMap) {
  const encoder = new TextEncoder()
  const now = new Date()
  const dosTime =
    ((now.getHours() & 0x1f) << 11) |
    ((now.getMinutes() & 0x3f) << 5) |
    ((now.getSeconds() >> 1) & 0x1f)
  const dosDate =
    ((Math.max(1980, now.getFullYear()) - 1980) << 9) |
    (((now.getMonth() + 1) & 0x0f) << 5) |
    (now.getDate() & 0x1f)

  const localParts = []
  const centralParts = []
  let offset = 0
  let count = 0

  for (const [path, content] of Object.entries(fileMap)) {
    const nameBytes = encoder.encode(path)
    const dataBytes = typeof content === 'string' ? encoder.encode(content) : content
    const crc = crc32(dataBytes)
    const size = dataBytes.byteLength

    const localHeader = new Uint8Array(30 + nameBytes.byteLength)
    const lv = new DataView(localHeader.buffer)
    lv.setUint32(0, 0x04034b50, true)
    lv.setUint16(4, 20, true)
    lv.setUint16(6, 0x0800, true) // UTF-8 路径编码标记
    lv.setUint16(8, 0, true) // STORE
    lv.setUint16(10, dosTime, true)
    lv.setUint16(12, dosDate, true)
    lv.setUint32(14, crc, true)
    lv.setUint32(18, size, true)
    lv.setUint32(22, size, true)
    lv.setUint16(26, nameBytes.byteLength, true)
    lv.setUint16(28, 0, true)
    localHeader.set(nameBytes, 30)

    const centralHeader = new Uint8Array(46 + nameBytes.byteLength)
    const cv = new DataView(centralHeader.buffer)
    cv.setUint32(0, 0x02014b50, true)
    cv.setUint16(4, 20, true)
    cv.setUint16(6, 20, true)
    cv.setUint16(8, 0x0800, true)
    cv.setUint16(10, 0, true)
    cv.setUint16(12, dosTime, true)
    cv.setUint16(14, dosDate, true)
    cv.setUint32(16, crc, true)
    cv.setUint32(20, size, true)
    cv.setUint32(24, size, true)
    cv.setUint16(28, nameBytes.byteLength, true)
    cv.setUint16(30, 0, true)
    cv.setUint16(32, 0, true)
    cv.setUint16(34, 0, true)
    cv.setUint16(36, 0, true)
    cv.setUint32(38, 0, true)
    cv.setUint32(42, offset, true)
    centralHeader.set(nameBytes, 46)

    localParts.push(localHeader, dataBytes)
    centralParts.push(centralHeader)
    offset += localHeader.byteLength + size
    count += 1
  }

  const centralSize = centralParts.reduce((sum, arr) => sum + arr.byteLength, 0)
  const eocd = new Uint8Array(22)
  const ev = new DataView(eocd.buffer)
  ev.setUint32(0, 0x06054b50, true)
  ev.setUint16(4, 0, true)
  ev.setUint16(6, 0, true)
  ev.setUint16(8, count, true)
  ev.setUint16(10, count, true)
  ev.setUint32(12, centralSize, true)
  ev.setUint32(16, offset, true)
  ev.setUint16(20, 0, true)

  const totalBytes = offset + centralSize + eocd.byteLength
  const out = new Uint8Array(totalBytes)
  let pos = 0
  for (const part of [...localParts, ...centralParts, eocd]) {
    out.set(part, pos)
    pos += part.byteLength
  }
  return out
}

export function buildKnowledgeGraphXmindBytes({ nodes = [], edges = [] } = {}) {
  const graph = sanitizeGraph(nodes, edges)
  const nodeById = new Map(graph.nodes.map((n) => [n.id, n]))
  const ts = Date.now()

  // 将知识点按所属主题分组（无主题的归入「自定义拓展知识点」）
  const themeGroups = new Map()
  for (const node of graph.nodes) {
    const groupKey = node.theme || '拓展与自定义知识点'
    if (!themeGroups.has(groupKey)) themeGroups.set(groupKey, [])
    themeGroups.get(groupKey).push(node)
  }

  const topicIdByNodeId = new Map()
  graph.nodes.forEach((n, i) => {
    topicIdByNodeId.set(n.id, `kp-topic-${i + 1}-${n.id.replace(/[^a-zA-Z0-9_-]/g, '_')}`)
  })

  const attachedThemesJson = []
  const attachedThemesXml = []
  let themeIdx = 0

  for (const [themeName, memberNodes] of themeGroups.entries()) {
    themeIdx += 1
    const themeTopicId = `theme-topic-${themeIdx}`
    const kpTopicsJson = []
    const kpTopicsXml = []

    for (const node of memberNodes) {
      const topicId = topicIdByNodeId.get(node.id)
      const prevEdges = graph.edges.filter((e) => e.target === node.id)
      const nextEdges = graph.edges.filter((e) => e.source === node.id)

      const noteLines = []
      if (node.description) noteLines.push(`【知识点介绍】\n${node.description}`)
      if (node.textbook_refs?.length) {
        noteLines.push(
          `【对应教材位置】\n${node.textbook_refs
            .map((r) => `• ${r.name} 第 ${r.page} 页${r.label ? `（${r.label}）` : ''}`)
            .join('\n')}`,
        )
      }
      if (prevEdges.length) {
        noteLines.push(
          `【前置知识】\n${prevEdges
            .map((e) => {
              const srcName = nodeById.get(e.source)?.name || e.source
              return e.relation ? `• ${srcName}：${e.relation}` : `• ${srcName}`
            })
            .join('\n')}`,
        )
      }
      if (nextEdges.length) {
        noteLines.push(
          `【后续知识】\n${nextEdges
            .map((e) => {
              const dstName = nodeById.get(e.target)?.name || e.target
              return e.relation ? `• ${dstName}：${e.relation}` : `• ${dstName}`
            })
            .join('\n')}`,
        )
      }
      const noteText = noteLines.join('\n\n')

      const detailChildrenJson = []
      const detailChildrenXml = []
      if (node.description) {
        const descId = `${topicId}-desc`
        detailChildrenJson.push({
          id: descId,
          class: 'topic',
          title: `要点：${node.description}`,
        })
        detailChildrenXml.push(
          `<topic id="${escapeXml(descId)}" timestamp="${ts}"><title>${escapeXml(`要点：${node.description}`)}</title></topic>`,
        )
      }
      if (prevEdges.length) {
        const prevSummary = prevEdges
          .map((e) => nodeById.get(e.source)?.name || e.source)
          .join('、')
        const prevId = `${topicId}-prev`
        detailChildrenJson.push({
          id: prevId,
          class: 'topic',
          title: `前置基础：${prevSummary}`,
        })
        detailChildrenXml.push(
          `<topic id="${escapeXml(prevId)}" timestamp="${ts}"><title>${escapeXml(`前置基础：${prevSummary}`)}</title></topic>`,
        )
      }
      if (nextEdges.length) {
        const nextSummary = nextEdges
          .map((e) => nodeById.get(e.target)?.name || e.target)
          .join('、')
        const nextId = `${topicId}-next`
        detailChildrenJson.push({
          id: nextId,
          class: 'topic',
          title: `后续衔接：${nextSummary}`,
        })
        detailChildrenXml.push(
          `<topic id="${escapeXml(nextId)}" timestamp="${ts}"><title>${escapeXml(`后续衔接：${nextSummary}`)}</title></topic>`,
        )
      }

      const kpJson = {
        id: topicId,
        class: 'topic',
        title: node.name,
        branch: 'folded',
      }
      if (noteText) {
        kpJson.notes = { plain: { content: noteText } }
      }
      if (detailChildrenJson.length) {
        kpJson.children = { attached: detailChildrenJson }
      }
      kpTopicsJson.push(kpJson)

      const notesXml = noteText
        ? `<notes><plain>${escapeXml(noteText)}</plain></notes>`
        : ''
      const childrenXml = detailChildrenXml.length
        ? `<children><topics type="attached">${detailChildrenXml.join('')}</topics></children>`
        : ''
      kpTopicsXml.push(
        `<topic id="${escapeXml(topicId)}" branch="folded" timestamp="${ts}"><title>${escapeXml(node.name)}</title>${notesXml}${childrenXml}</topic>`,
      )
    }

    attachedThemesJson.push({
      id: themeTopicId,
      class: 'topic',
      title: themeName,
      children: { attached: kpTopicsJson },
    })
    attachedThemesXml.push(
      `<topic id="${escapeXml(themeTopicId)}" timestamp="${ts}"><title>${escapeXml(themeName)}</title><children><topics type="attached">${kpTopicsXml.join('')}</topics></children></topic>`,
    )
  }

  const relationshipsJson = graph.edges.map((e, idx) => ({
    id: `rel-${idx + 1}`,
    class: 'relationship',
    end1Id: topicIdByNodeId.get(e.source),
    end2Id: topicIdByNodeId.get(e.target),
    title: e.relation || '前置支撑',
  }))

  const relationshipsXml = graph.edges
    .map(
      (e, idx) =>
        `<relationship id="rel-${idx + 1}" end1="${escapeXml(topicIdByNodeId.get(e.source))}" end2="${escapeXml(topicIdByNodeId.get(e.target))}" timestamp="${ts}"><title>${escapeXml(e.relation || '前置支撑')}</title></relationship>`,
    )
    .join('')

  const contentJson = JSON.stringify(
    [
      {
        id: 'zjhx-kg-sheet-1',
        class: 'sheet',
        title: '知识图谱',
        rootTopic: {
          id: 'zjhx-kg-root',
          class: 'topic',
          title: '智教慧学 · 知识图谱',
          structureClass: 'org.xmind.ui.logic.right',
          children: {
            attached: attachedThemesJson,
          },
        },
        relationships: relationshipsJson,
      },
    ],
    null,
    2,
  )

  const metadataJson = JSON.stringify(
    {
      creator: {
        name: 'ZJHX Knowledge Graph Exporter',
        version: '1.0.0',
      },
      dataStructureVersion: '2',
      layoutEngineVersion: '3',
    },
    null,
    2,
  )

  const manifestJson = JSON.stringify(
    {
      'file-entries': {
        'content.json': {},
        'metadata.json': {},
        'content.xml': {},
        'META-INF/manifest.xml': {},
      },
    },
    null,
    2,
  )

  const contentXml =
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' +
    '<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" xmlns:fo="http://www.w3.org/1999/XSL/Format" version="2.0">' +
    `<sheet id="zjhx-kg-sheet-1" timestamp="${ts}">` +
    '<title>知识图谱</title>' +
    `<topic id="zjhx-kg-root" structure-class="org.xmind.ui.logic.right" timestamp="${ts}">` +
    '<title>智教慧学 · 知识图谱</title>' +
    (attachedThemesXml.length
      ? `<children><topics type="attached">${attachedThemesXml.join('')}</topics></children>`
      : '') +
    '</topic>' +
    (relationshipsXml ? `<relationships>${relationshipsXml}</relationships>` : '') +
    '</sheet>' +
    '</xmap-content>'

  const manifestXml =
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' +
    '<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">' +
    '<file-entry full-path="content.json" media-type="application/json"/>' +
    '<file-entry full-path="metadata.json" media-type="application/json"/>' +
    '<file-entry full-path="content.xml" media-type="text/xml"/>' +
    '<file-entry full-path="META-INF/" media-type=""/>' +
    '<file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>' +
    '</manifest>'

  return createZipArchive({
    'content.json': contentJson,
    'metadata.json': metadataJson,
    'manifest.json': manifestJson,
    'content.xml': contentXml,
    'META-INF/manifest.xml': manifestXml,
  })
}

export function exportKnowledgeGraphAsHtml({ nodes, edges, isTeacher }) {
  const html = buildKnowledgeGraphHtml({
    nodes,
    edges,
    roleLabel: isTeacher ? '教师端' : '学生端',
  })
  const filename = `知识图谱_${formatTimestampForFilename()}.html`
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  triggerBlobDownload(blob, filename)
  return filename
}

export function exportKnowledgeGraphAsXmind({ nodes, edges }) {
  const zipBytes = buildKnowledgeGraphXmindBytes({ nodes, edges })
  const filename = `知识图谱_${formatTimestampForFilename()}.xmind`
  const blob = new Blob([zipBytes], { type: 'application/vnd.xmind.workbook' })
  triggerBlobDownload(blob, filename)
  return filename
}
