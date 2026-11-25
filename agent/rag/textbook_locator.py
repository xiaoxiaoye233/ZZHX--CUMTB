"""教材页码精准定位模块：
只要用户提及“在哪 / 哪里 / 哪一页”等位置词，或提及任何具体数学知识点、教材章节、题目，
甚至间接询问“最差的是哪个知识点，对应习题在哪一页”，均结合本轮提问、检索结果与助手回答，
精准定位到最相关的教材文件与页码（1-based），供前端自动展开阅读器并翻页。
"""
from __future__ import annotations

from contextvars import ContextVar
import csv
import json
from pathlib import Path
import re
import sqlite3
from threading import Lock
import unicodedata
from urllib.parse import quote

from agent.config.settings import AGENT_ROOT, CHROMA_PERSIST_DIR, TEXTBOOK_PDF_DIR

DATASET_DIR = AGENT_ROOT.parent / "数据层" / "dataset"
KNOWLEDGE_GRAPH_FILE = AGENT_ROOT.parent / "project" / ".knowledge-graph.json"

_TURN_REFS: ContextVar[list[dict] | None] = ContextVar("textbook_turn_refs", default=None)
_INDEX_LOCK = Lock()
_CACHED_CHROMA_MTIME: float = -1.0
_CACHED_CHROMA_PAGES: list[dict] = []
_CACHED_EXTRA_FILES: dict[str, tuple[float, list[dict]]] = {}
_CACHED_QUESTION_MAP: dict[str, dict] | None = None
_CACHED_INDICATORS: list[dict] | None = None

# 教材核心概念词表（覆盖全部章节与课标知识点表述，按长度优先）
_MATH_DOMAIN_TERMS = (
    "根据实际限制列不等式并解释取值范围",
    "根据实际限制列不等式并解释范围",
    "运用不等式性质求解，负数乘除时正确改变方向",
    "运用不等式性质求解一元一次不等式",
    "求两个一元一次不等式解集的交集",
    "列方程或方程组解决简单实际问题并检验",
    "列方程或方程组解决实际问题",
    "运用等式性质解一元一次方程",
    "用消元法解二元一次方程组",
    "识别同类项、去括号并化简",
    "表示数量关系并代入求值",
    "用整式解释具体问题",
    "实际问题与二元一次方程组",
    "实际问题与一元一次方程",
    "列代数式表示数量关系",
    "数据的收集、整理与描述",
    "一元一次不等式组",
    "三元一次方程组",
    "二元一次方程组",
    "不等式与不等式组",
    "相交线与平行线",
    "一元一次不等式",
    "一元一次方程",
    "二元一次方程",
    "几何图形初步",
    "有理数的加法与减法",
    "有理数的乘法与除法",
    "有理数的运算",
    "有理数的加法",
    "有理数的减法",
    "有理数的乘法",
    "有理数的除法",
    "平行线的性质",
    "平行线的判定",
    "不等式的性质",
    "不等式的解集",
    "代数式的值",
    "整式的加减",
    "合并同类项",
    "算术平方根",
    "代入消元法",
    "加减消元法",
    "立体图形",
    "平面图形",
    "科学记数法",
    "等式的性质",
    "全面调查",
    "抽样调查",
    "样本容量",
    "同旁内角",
    "角平分线",
    "平行公理",
    "平方根",
    "立方根",
    "无理数",
    "有理数",
    "相反数",
    "绝对值",
    "近似数",
    "代数式",
    "列代数式",
    "单项式",
    "多项式",
    "同类项",
    "去括号",
    "去分母",
    "代入法",
    "加减法",
    "不等式",
    "相交线",
    "平行线",
    "邻补角",
    "对顶角",
    "同位角",
    "内错角",
    "展开图",
    "扇形图",
    "条形图",
    "折线图",
    "直方图",
    "趋势图",
    "实数",
    "数轴",
    "整式",
    "方程",
    "消元",
    "移项",
    "解集",
    "直线",
    "射线",
    "线段",
    "中点",
    "余角",
    "补角",
    "垂线",
    "命题",
    "定理",
    "平移",
    "频数",
)

# 课标指标表述 -> 人教版教材原文高频术语桥接（解决指标名与教材章节名措辞差异）
_CONCEPT_SYNONYM_BRIDGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "根据实际限制列不等式",
        ("11.2 一元一次不等式", "不等关系", "不超过", "不能超过", "不小于"),
    ),
    (
        "解释取值范围",
        ("11.2 一元一次不等式", "不超过", "不能超过", "正整数"),
    ),
    (
        "求两个一元一次不等式解集的交集",
        ("11.3 一元一次不等式组", "不等式组的解集", "公共部分", "解下列不等式组"),
    ),
    (
        "不等式解集的交集",
        ("11.3 一元一次不等式组", "不等式组的解集", "公共部分"),
    ),
    (
        "负数乘除时正确改变方向",
        ("不等式的性质", "方向改变", "两边乘", "除以"),
    ),
    (
        "运用不等式性质求解",
        ("不等式的性质", "利用不等式的性质解下列不等式"),
    ),
    (
        "表示数量关系并代入求值",
        ("3.2 代数式的值", "3.1 列代数式表示数量关系", "求代数式"),
    ),
    (
        "代入求值",
        ("3.2 代数式的值", "求代数式"),
    ),
    (
        "识别同类项、去括号并化简",
        ("第四章 整式的加减", "4.2 整式的加法与减法", "同类项", "合并同类项", "去括号"),
    ),
    (
        "用整式解释具体问题",
        ("4.1 整式", "单项式", "多项式", "第三章 代数式"),
    ),
    (
        "运用等式性质解一元一次方程",
        ("5.2 解一元一次方程", "等式的性质", "移项", "去分母"),
    ),
    (
        "用消元法解二元一次方程组",
        ("10.2 消元", "解二元一次方程组", "代入消元法", "加减消元法"),
    ),
    (
        "列方程或方程组解决",
        ("5.3 实际问题与一元一次方程", "10.3 实际问题与二元一次方程组", "列方程"),
    ),
    (
        "有理数的加减",
        ("第二章 有理数的运算", "有理数的加法与减法", "有理数的加法"),
    ),
)

# 位置词与知识点询问触发词（只要出现即可触发教材页定位）
_LOCATION_OR_KP_TRIGGERS = (
    "在哪",
    "哪里",
    "哪儿",
    "哪页",
    "哪一页",
    "第几页",
    "教材",
    "课本",
    "书上",
    "书中",
    "哪一章",
    "哪章",
    "哪一节",
    "章节",
    "翻到",
    "定位",
    "出处",
    "知识点",
    "哪个知识点",
    "什么知识点",
    "哪些知识点",
    "例题",
    "练习题",
    "习题",
    "复习题",
    "课后题",
    "探究",
    "思考",
    "定义",
    "概念",
    "公式",
    "定理",
    "法则",
    "性质",
    "怎么解",
    "怎么做",
    "怎么算",
    "如何解",
    "这道题",
    "那道题",
)

_EXERCISE_INTENT_WORDS = ("习题", "练习", "练习题", "课后题", "复习题", "复习巩固", "对应题", "对应的题")

_STOP_PHRASES = (
    "这两个班",
    "两个班",
    "所有班级",
    "全部班级",
    "全年级",
    "总体情况",
    "整体情况",
    "总体做",
    "总体",
    "整体",
    "做的最差",
    "做得最差",
    "最差的",
    "最弱的",
    "最差",
    "最弱",
    "最薄弱",
    "薄弱",
    "最好",
    "哪个知识点",
    "什么知识点",
    "哪些知识点",
    "知识点",
    "对应的习题",
    "对应的题",
    "对应习题",
    "对应的",
    "对应",
    "在教材哪一页",
    "在教材哪页",
    "在教材哪里",
    "在教材在哪",
    "教材哪一页",
    "教材里",
    "教材中",
    "教材",
    "课本里",
    "课本",
    "书上",
    "在哪一页",
    "在哪页",
    "第几页",
    "在哪里",
    "在哪儿",
    "在哪",
    "哪里",
    "哪儿",
    "请问",
    "老师",
    "同学",
    "帮我",
    "给我",
    "可以",
    "能不能",
    "一下",
    "讲讲",
    "讲解",
    "介绍",
    "告诉",
    "相关的",
    "相关",
    "有关",
    "关于",
    "的习题",
    "习题",
    "练习题",
    "练习",
    "的题",
    "题目",
    "例题",
    "是什么",
    "什么是",
    "怎么",
    "如何",
    "为什么",
    "平均分",
    "得分率",
    "班级",
    "学生",
    "情况",
    "数据",
    "分析",
    "两个",
    "如果",
    "问题",
)

_PURE_SCORE_PATTERNS = re.compile(
    r"^(?:我的|本人|这两个班|两个班|全年级|DC\d+|查一下|看看)?(?:总分|成绩|分数|得分率|排名|班级均分|平均分|有哪些错题|错题有哪些)[是多少吗？?！!。.\s]*$",
    re.IGNORECASE,
)


def _norm_text(raw: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(raw or ""))
    return re.sub(r"\s+", "", normalized).lower()


def _load_dynamic_indicator_names() -> list[str]:
    """动态加载指标字典和知识图谱中的全部知识点名称（支持后续新增知识点）。"""
    global _CACHED_INDICATORS
    names: list[str] = []

    if _CACHED_INDICATORS is None:
        loaded: list[dict] = []
        ind_csv = DATASET_DIR / "00_字典" / "指标字典.csv"
        if ind_csv.is_file():
            try:
                with ind_csv.open("r", encoding="utf-8-sig", newline="") as f:
                    loaded = list(csv.DictReader(f))
            except OSError:
                loaded = []
        _CACHED_INDICATORS = loaded

    for row in _CACHED_INDICATORS:
        for key in ("指标名称", "主题名称"):
            val = (row.get(key) or "").strip()
            if val and val not in names:
                names.append(val)

    if KNOWLEDGE_GRAPH_FILE.is_file():
        try:
            g_data = json.loads(KNOWLEDGE_GRAPH_FILE.read_text(encoding="utf-8"))
            for node in g_data.get("nodes") or []:
                if isinstance(node, dict):
                    nname = str(node.get("name") or "").strip()
                    if nname and nname not in names:
                        names.append(nname)
        except (OSError, ValueError):
            pass

    names.sort(key=len, reverse=True)
    return names


def _load_question_lookup() -> dict[str, dict]:
    global _CACHED_QUESTION_MAP
    if _CACHED_QUESTION_MAP is not None:
        return _CACHED_QUESTION_MAP

    q_map: dict[str, dict] = {}
    q_csv = DATASET_DIR / "00_字典" / "题目字典.csv"
    if q_csv.is_file():
        try:
            with q_csv.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    qid = (row.get("材料编号") or "").strip().upper()
                    if qid:
                        q_map[qid] = {
                            "theme_name": (row.get("主题名称") or "").strip(),
                            "indicator_name": (row.get("指标名称") or "").strip(),
                            "stem": "",
                        }
        except OSError:
            pass

    q_json = DATASET_DIR / "06_题目内容.json"
    if q_json.is_file():
        try:
            items = json.loads(q_json.read_text(encoding="utf-8"))
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    qid = str(item.get("material_id") or "").strip().upper()
                    if not qid:
                        continue
                    q_map.setdefault(qid, {"theme_name": "", "indicator_name": "", "stem": ""})
                    q_map[qid]["stem"] = str(item.get("stem") or "").strip()
        except (OSError, ValueError):
            pass

    _CACHED_QUESTION_MAP = q_map
    return q_map


def _is_exercise_page(raw_text: str) -> bool:
    norm = unicodedata.normalize("NFKC", raw_text or "")
    if any(tag in norm for tag in ("练习", "习题", "复习巩固", "综合运用", "拓广探索")):
        return True
    # 人教版切片中练习/习题页常带有题号序列 1. ... 2. ... 或 (1) ... (2) ...
    numbered = len(re.findall(r"(?:^|\s)[1-9]\.\s*[\u4e00-\u9fffA-Za-z(]", norm))
    return numbered >= 2


def _load_pages_from_chroma_sqlite(chroma_sqlite: Path) -> list[dict]:
    page_texts: dict[tuple[str, int], list[str]] = {}
    conn = sqlite3.connect(str(chroma_sqlite))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              m_file.string_value AS source_file,
              COALESCE(m_page.int_value, 0) AS page_idx,
              m_doc.string_value AS doc_text
            FROM embedding_metadata m_cat
            JOIN embedding_metadata m_file
              ON m_cat.id = m_file.id AND m_file.key = 'source_file'
            JOIN embedding_metadata m_doc
              ON m_cat.id = m_doc.id AND m_doc.key = 'chroma:document'
            LEFT JOIN embedding_metadata m_page
              ON m_cat.id = m_page.id AND m_page.key = 'page'
            WHERE m_cat.key = 'category' AND m_cat.string_value = 'textbook'
            """
        )
        for source_file, page_idx, doc_text in cur.fetchall():
            if not source_file or not doc_text:
                continue
            key = (str(source_file), int(page_idx) + 1)
            page_texts.setdefault(key, []).append(str(doc_text))
    finally:
        conn.close()

    results = []
    for (source_file, page_no), chunks in page_texts.items():
        joined = "\n".join(chunks)
        results.append(
            {
                "source_file": source_file,
                "page": page_no,
                "raw_text": joined,
                "norm_text": _norm_text(joined),
                "is_exercise": _is_exercise_page(joined),
            }
        )
    return results


def _extract_single_file_pages(file_path: Path) -> list[dict]:
    suffix = file_path.suffix.lower()
    out: list[dict] = []
    if suffix == ".txt":
        try:
            txt = file_path.read_text(encoding="utf-8", errors="ignore")
            out.append(
                {
                    "source_file": file_path.name,
                    "page": 1,
                    "raw_text": txt,
                    "norm_text": _norm_text(txt),
                    "is_exercise": _is_exercise_page(txt),
                }
            )
        except OSError:
            pass
        return out

    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium

            doc = pdfium.PdfDocument(str(file_path))
            try:
                for idx in range(len(doc)):
                    raw = doc[idx].get_textpage().get_text_range() or ""
                    if raw.strip():
                        out.append(
                            {
                                "source_file": file_path.name,
                                "page": idx + 1,
                                "raw_text": raw,
                                "norm_text": _norm_text(raw),
                                "is_exercise": _is_exercise_page(raw),
                            }
                        )
            finally:
                doc.close()
        except Exception:
            pass
    return out


def get_textbook_page_index() -> list[dict]:
    """加载教材每页文本索引（优先秒读 chroma.sqlite3，并自动补充新上传教材文件）。"""
    global _CACHED_CHROMA_MTIME, _CACHED_CHROMA_PAGES

    with _INDEX_LOCK:
        existing_files: dict[str, Path] = {}
        if TEXTBOOK_PDF_DIR.is_dir():
            for fp in sorted(TEXTBOOK_PDF_DIR.iterdir()):
                if (
                    fp.is_file()
                    and not fp.name.startswith(".")
                    and not fp.name.startswith("请把")
                    and fp.suffix.lower() in (".pdf", ".txt")
                ):
                    existing_files[fp.name] = fp

        chroma_sqlite = CHROMA_PERSIST_DIR / "chroma.sqlite3"
        if chroma_sqlite.is_file():
            mtime = chroma_sqlite.stat().st_mtime
            if mtime != _CACHED_CHROMA_MTIME:
                try:
                    _CACHED_CHROMA_PAGES = _load_pages_from_chroma_sqlite(chroma_sqlite)
                    _CACHED_CHROMA_MTIME = mtime
                except sqlite3.Error:
                    _CACHED_CHROMA_PAGES = []

        pages = [
            p
            for p in _CACHED_CHROMA_PAGES
            if not existing_files or p["source_file"] in existing_files
        ]
        indexed_names = {p["source_file"] for p in pages}

        for fname, fp in existing_files.items():
            if fname in indexed_names:
                continue
            f_mtime = fp.stat().st_mtime
            cached = _CACHED_EXTRA_FILES.get(fname)
            if cached is None or cached[0] != f_mtime:
                _CACHED_EXTRA_FILES[fname] = (f_mtime, _extract_single_file_pages(fp))
            pages.extend(_CACHED_EXTRA_FILES[fname][1])

        return pages


def _expand_synonyms(text: str) -> list[str]:
    norm = unicodedata.normalize("NFKC", str(text or ""))
    bridged: list[str] = []
    for trigger, expansions in _CONCEPT_SYNONYM_BRIDGES:
        if trigger in norm:
            for item in expansions:
                if item not in bridged:
                    bridged.append(item)
    return bridged


def _extract_domain_concepts_in_order(text: str) -> list[str]:
    """按在文本中首次出现的先后顺序，提取知识点名称与数学核心术语。"""
    norm = unicodedata.normalize("NFKC", str(text or ""))
    if not norm:
        return []

    candidates = list(_MATH_DOMAIN_TERMS)
    for dyn_name in _load_dynamic_indicator_names():
        if dyn_name not in candidates:
            candidates.append(dyn_name)

    found_with_pos: list[tuple[int, int, str]] = []
    for term in candidates:
        pos = norm.find(term)
        if pos >= 0:
            found_with_pos.append((pos, -len(term), term))

    found_with_pos.sort()
    ordered: list[str] = []
    for _, _, term in found_with_pos:
        if term not in ordered:
            ordered.append(term)
    return ordered


def _extract_query_terms(query: str, *, allow_free_chunks: bool = True) -> list[str]:
    norm_q = unicodedata.normalize("NFKC", str(query or "")).strip()
    if not norm_q:
        return []

    terms: list[str] = []

    # 1. 提取明确的知识点与数学专业术语（优先放入教材同义词桥接章节，再放原始概念）
    concepts = _extract_domain_concepts_in_order(norm_q)
    for bridged in _expand_synonyms(norm_q):
        if bridged not in terms:
            terms.append(bridged)
    for concept in concepts:
        if concept not in terms:
            terms.append(concept)

    if not allow_free_chunks:
        return terms

    # 2. 去掉已识别的专业概念与口语停用词后，提取剩余的具体题干短语（如“两支登山队”“天问一号”）
    cleaned = norm_q
    for concept in concepts:
        cleaned = cleaned.replace(concept, " ")
    for stop in _STOP_PHRASES:
        cleaned = cleaned.replace(stop, " ")

    for raw_chunk in re.findall(r"[\u4e00-\u9fff]{2,16}", cleaned):
        chunk = raw_chunk.strip("的了呢吗呀啊吧哦嘛在有是和与及或把被让对从向到中上下里内去用并")
        if len(chunk) < 2 or chunk in _STOP_PHRASES:
            continue
        if chunk not in terms:
            terms.append(chunk)
        if len(chunk) >= 4:
            for width in (4, 3):
                if len(chunk) < width:
                    continue
                for idx in range(0, len(chunk) - width + 1):
                    sub = chunk[idx : idx + width]
                    if sub not in _STOP_PHRASES and sub not in terms:
                        terms.append(sub)

    for expr in re.findall(r"[0-9a-zA-Z+\-*/=<>≥≤²³()]{3,16}", cleaned):
        low = expr.lower()
        if not re.fullmatch(r"(?:q\d+|dc\d+|d\d+|b\d+)", low) and low not in terms:
            terms.append(low)

    return terms


def _expand_question_references(query: str) -> tuple[str, bool]:
    """若提问中包含题号（如 Q005、Q38），自动拼入该题的题干与所属知识点名称。"""
    qids = [m.upper() for m in re.findall(r"\b[Qq]\d{1,4}\b", str(query or ""))]
    if not qids:
        return query, False

    q_lookup = _load_question_lookup()
    extra_parts: list[str] = []
    matched_any = False
    for qid in qids:
        candidates = [qid]
        num_part = re.findall(r"\d+", qid)
        if num_part:
            candidates.append(f"Q{int(num_part[0]):03d}")
        for cand in candidates:
            info = q_lookup.get(cand)
            if info:
                matched_any = True
                extra_parts.extend(
                    part
                    for part in (info.get("indicator_name"), info.get("theme_name"), info.get("stem"))
                    if part
                )
                break

    if not extra_parts:
        return query, False
    return f"{query} {' '.join(extra_parts)}", matched_any


_DOMAIN_SET = set(_MATH_DOMAIN_TERMS) | {
    item for _, exps in _CONCEPT_SYNONYM_BRIDGES for item in exps
}


def _is_summary_overview_page(raw_text: str) -> bool:
    norm = unicodedata.normalize("NFKC", raw_text or "")
    return any(
        marker in norm
        for marker in ("在本章中,我们学习了", "在本章中，我们学习了", "请你带着下面的问题", "本章我们通过")
    )


def score_page_against_query(
    entry: dict,
    terms: list[str],
    *,
    prefer_exercise: bool = False,
) -> float:
    page_norm_text = entry.get("norm_text") or ""
    if not page_norm_text or not terms:
        return 0.0

    score = 0.0
    matched_distinct = 0
    for rank_idx, term in enumerate(terms):
        t_norm = _norm_text(term)
        if len(t_norm) < 2:
            continue
        cnt = page_norm_text.count(t_norm)
        if cnt <= 0:
            continue
        matched_distinct += 1
        is_domain = term in _DOMAIN_SET
        # 排在前面的核心知识点权重更高
        order_boost = 1.35 if rank_idx < 3 else 1.0
        weight = (len(t_norm) ** 1.75) * (1.8 if is_domain else 1.0) * order_boost
        score += weight * min(cnt, 5)

    if matched_distinct >= 2:
        score *= 1.3
    if _is_summary_overview_page(entry.get("raw_text") or ""):
        score *= 0.45
    if prefer_exercise and score > 0 and entry.get("is_exercise"):
        score *= 1.45
    return score


def build_textbook_ref_dict(source_file: str, page: int) -> dict | None:
    fname = Path(str(source_file or "")).name.strip()
    if not fname:
        return None
    if TEXTBOOK_PDF_DIR.is_dir() and not (TEXTBOOK_PDF_DIR / fname).is_file():
        return None
    page_no = max(1, int(page or 1))
    return {
        "name": fname,
        "title": Path(fname).stem,
        "page": page_no,
        "url": f"/api/agent/textbooks/{quote(fname)}",
    }


def _wants_exercise_page(text: str) -> bool:
    norm = unicodedata.normalize("NFKC", str(text or ""))
    return any(w in norm for w in _EXERCISE_INTENT_WORDS)


def search_local_textbook_pages(
    query: str,
    top_k: int = 4,
    *,
    prefer_exercise: bool | None = None,
    allow_free_chunks: bool = True,
) -> list[dict]:
    expanded_query, _ = _expand_question_references(query)
    terms = _extract_query_terms(expanded_query, allow_free_chunks=allow_free_chunks)
    if not terms:
        return []

    want_ex = _wants_exercise_page(query) if prefer_exercise is None else prefer_exercise
    scored: list[tuple[float, dict]] = []
    for entry in get_textbook_page_index():
        sc = score_page_against_query(entry, terms, prefer_exercise=want_ex)
        if sc > 0:
            scored.append((sc, entry))

    # 如果用户问“对应习题在哪一页”，但该节练习页紧挨在正文讲解页之后（同文件后 1~2 页内有练习页），做邻近习题页加权
    if want_ex and scored:
        best_file = max(scored, key=lambda x: x[0])[1]["source_file"]
        top_topic_pages = [
            item[1]["page"]
            for item in sorted(scored, key=lambda x: -x[0])[:3]
            if item[1]["source_file"] == best_file
        ]
        boosted: list[tuple[float, dict]] = []
        for sc, entry in scored:
            if (
                entry["source_file"] == best_file
                and entry.get("is_exercise")
                and any(0 <= entry["page"] - tp <= 3 for tp in top_topic_pages)
            ):
                sc *= 1.55
            boosted.append((sc, entry))
        scored = boosted

    scored.sort(key=lambda item: (-item[0], item[1]["source_file"], item[1]["page"]))
    return [{**item[1], "lexical_score": item[0]} for item in scored[:top_k]]


def rerank_textbook_docs(query: str, docs: list) -> list:
    """结合语义召回顺序、同义词桥接与习题偏好重排，精准命中正文详解页或对应习题页。"""
    if not docs:
        return docs
    expanded_query, _ = _expand_question_references(query)
    terms = _extract_query_terms(expanded_query)
    if not terms:
        return docs

    want_ex = _wants_exercise_page(query)
    scored_docs = []
    for rank_idx, doc in enumerate(docs):
        semantic_base = max(0.0, 16.0 - rank_idx * 2.5)
        raw = doc.page_content or ""
        entry = {
            "norm_text": _norm_text(raw),
            "is_exercise": _is_exercise_page(raw),
        }
        lex = score_page_against_query(entry, terms, prefer_exercise=want_ex)
        scored_docs.append((semantic_base + lex, rank_idx, doc))

    scored_docs.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored_docs]


def begin_textbook_turn() -> None:
    _TURN_REFS.set([])


def record_textbook_tool_hit(query: str, source_file: str, page_one_based: int) -> None:
    bucket = _TURN_REFS.get()
    if bucket is None:
        return
    ref = build_textbook_ref_dict(source_file, page_one_based)
    if ref is not None:
        bucket.append({**ref, "query": query})


def finish_textbook_turn() -> list[dict]:
    bucket = _TURN_REFS.get() or []
    _TURN_REFS.set(None)
    return bucket


def is_textbook_or_question_query(user_message: str) -> bool:
    clean = unicodedata.normalize("NFKC", str(user_message or "")).strip()
    if len(clean) < 2:
        return False
    if _PURE_SCORE_PATTERNS.match(clean):
        return False

    _, has_qid = _expand_question_references(clean)
    if has_qid:
        return True
    if any(word in clean for word in _LOCATION_OR_KP_TRIGGERS):
        return True
    if _extract_domain_concepts_in_order(clean):
        return True
    return False


def resolve_best_textbook_ref(
    user_message: str,
    tool_refs: list[dict] | None = None,
    assistant_reply: str | None = None,
) -> dict | None:
    """综合用户提问、Agent 工具检索与助手回复中的知识点，精准定位最相关的教材文件与页码。"""
    clean_msg = str(user_message or "").strip()
    if not clean_msg or _PURE_SCORE_PATTERNS.match(clean_msg):
        return None

    want_ex = _wants_exercise_page(clean_msg)
    user_concepts = _extract_domain_concepts_in_order(clean_msg)
    _, has_qid = _expand_question_references(clean_msg)

    # 1. 若用户提问中已经直接包含明确知识点、数学概念、题号或具体教材原题词句
    if user_concepts or has_qid:
        direct_hits = search_local_textbook_pages(clean_msg, top_k=3, prefer_exercise=want_ex)
        if direct_hits and direct_hits[0]["lexical_score"] >= 8.0:
            return build_textbook_ref_dict(direct_hits[0]["source_file"], direct_hits[0]["page"])
    else:
        # 检查是否直接粘贴了教材原题句子（如“甲乙两支登山队”）
        phrase_hits = search_local_textbook_pages(clean_msg, top_k=2, prefer_exercise=want_ex)
        if phrase_hits and phrase_hits[0]["lexical_score"] >= 22.0:
            return build_textbook_ref_dict(phrase_hits[0]["source_file"], phrase_hits[0]["page"])

    # 2. 若本轮 Agent 主动调用了 search_textbook_knowledge（含间接提问查出知识点后再搜教材）
    if tool_refs:
        # 用工具检索词 + 用户是否要习题页，在本地页索引做一次精细校准（如定位到同节习题页）
        tool_queries = " ".join(r.get("query") or "" for r in tool_refs if r.get("query"))
        if tool_queries:
            calibrated = search_local_textbook_pages(
                tool_queries, top_k=2, prefer_exercise=want_ex
            )
            if calibrated and calibrated[0]["lexical_score"] >= 14.0:
                ref = build_textbook_ref_dict(calibrated[0]["source_file"], calibrated[0]["page"])
                if ref:
                    return ref
        primary = tool_refs[0]
        return {
            "name": primary["name"],
            "title": primary["title"],
            "page": primary["page"],
            "url": primary["url"],
        }

    # 3. 间接提问场景（例如用户问“最差的是哪个知识点，在哪一页”，知识点名称出现在助手回复中！）
    if not is_textbook_or_question_query(clean_msg):
        return None

    if assistant_reply:
        reply_concepts = _extract_domain_concepts_in_order(assistant_reply)
        if reply_concepts:
            # 取助手回答中最先点出的核心知识点（如“根据实际限制列不等式并解释取值范围”），避免被后续陪衬词干扰
            primary_concepts = " ".join(reply_concepts[:2])
            reply_hits = search_local_textbook_pages(
                primary_concepts,
                top_k=3,
                prefer_exercise=want_ex,
                allow_free_chunks=False,
            )
            if reply_hits and reply_hits[0]["lexical_score"] >= 8.0:
                return build_textbook_ref_dict(reply_hits[0]["source_file"], reply_hits[0]["page"])

    return None
