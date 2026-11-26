import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

GRAPH_FILE = Path(__file__).resolve().parents[1] / ".knowledge-graph.json"
_GRAPH_LOCK = Lock()

DEFAULT_KNOWLEDGE_GRAPH = {
    "nodes": [
        {
            "id": "T01I1",
            "name": "表示数量关系并代入求值",
            "theme": "代数式与整式运算",
            "description": "能分析具体问题中的简单数量关系并用代数式表示；会把具体数值代入代数式进行准确计算（教材范围：七年级上册 P68–109）。",
            "textbook_refs": [
                {
                    "name": "B05_相关资料切片.pdf",
                    "page": 2,
                    "label": "3.1 列代数式表示数量关系",
                },
                {
                    "name": "B05_相关资料切片.pdf",
                    "page": 12,
                    "label": "3.2 代数式的值",
                },
            ],
            "x": 130,
            "y": 280,
        },
        {
            "id": "T01I2",
            "name": "识别同类项、去括号并化简",
            "theme": "代数式与整式运算",
            "description": "理解整式的概念，掌握合并同类项和去括号法则（注意括号前为负号时各项变号），能进行整式加减化简运算。",
            "textbook_refs": [
                {
                    "name": "B05_相关资料切片.pdf",
                    "page": 28,
                    "label": "4.2 整式的加法与减法 · 合并同类项",
                },
                {
                    "name": "B05_相关资料切片.pdf",
                    "page": 32,
                    "label": "去括号法则与整式化简",
                },
            ],
            "x": 430,
            "y": 160,
        },
        {
            "id": "T01I3",
            "name": "用整式解释具体问题",
            "theme": "代数式与整式运算",
            "description": "借助现实情境理解字母表示数的意义，能够先对整式进行化简合并，再结合实际情境解释代数式所表达的数量规律。",
            "textbook_refs": [
                {
                    "name": "B05_相关资料切片.pdf",
                    "page": 22,
                    "label": "4.1 整式 · 单项式与多项式",
                },
                {
                    "name": "B05_相关资料切片.pdf",
                    "page": 25,
                    "label": "用多项式表示并解释实际问题",
                },
            ],
            "x": 430,
            "y": 400,
        },
        {
            "id": "T02I1",
            "name": "运用等式性质解一元一次方程",
            "theme": "方程与方程组",
            "description": "掌握等式的基本性质，熟练完成去分母、去括号、移项、合并同类项与系数化为 1，准确求解一元一次方程。",
            "textbook_refs": [
                {
                    "name": "B06_相关资料切片.pdf",
                    "page": 7,
                    "label": "5.1.2 等式的性质",
                },
                {
                    "name": "B06_相关资料切片.pdf",
                    "page": 11,
                    "label": "5.2 解一元一次方程",
                },
            ],
            "x": 740,
            "y": 280,
        },
        {
            "id": "T02I2",
            "name": "用消元法解二元一次方程组",
            "theme": "方程与方程组",
            "description": "理解消元思想，灵活运用代入消元法或加减消元法将二元一次方程组转化为一元一次方程求解。",
            "textbook_refs": [
                {
                    "name": "B06_相关资料切片.pdf",
                    "page": 44,
                    "label": "10.2 代入消元法解二元一次方程组",
                },
                {
                    "name": "B06_相关资料切片.pdf",
                    "page": 48,
                    "label": "10.2.2 加减消元法",
                },
            ],
            "x": 1060,
            "y": 95,
        },
        {
            "id": "T02I3",
            "name": "列方程或方程组解决实际问题",
            "theme": "方程与方程组",
            "description": "能根据现实问题中的等量关系建立方程或方程组模型，求解后能结合实际意义检验解的合理性。",
            "textbook_refs": [
                {
                    "name": "B06_相关资料切片.pdf",
                    "page": 24,
                    "label": "5.3 实际问题与一元一次方程",
                },
                {
                    "name": "B06_相关资料切片.pdf",
                    "page": 54,
                    "label": "10.3 实际问题与二元一次方程组",
                },
            ],
            "x": 1060,
            "y": 265,
        },
        {
            "id": "T03I1",
            "name": "运用不等式性质求解一元一次不等式",
            "theme": "不等式与不等式组",
            "description": "探索并掌握不等式的基本性质，解数字系数的一元一次不等式并在数轴上表示解集，特别注意乘除负数时不等号方向改变。",
            "textbook_refs": [
                {
                    "name": "B02_相关资料切片.pdf",
                    "page": 5,
                    "label": "11.1.2 不等式的性质（负数乘除变号）",
                },
                {
                    "name": "B02_相关资料切片.pdf",
                    "page": 12,
                    "label": "11.2 一元一次不等式的解法",
                },
            ],
            "x": 1060,
            "y": 440,
        },
        {
            "id": "T03I2",
            "name": "求两个一元一次不等式解集的交集",
            "theme": "不等式与不等式组",
            "description": "分别求出不等式组中各个不等式的解集，借助数轴确定公共部分（交集），准确处理端点空心与实心。",
            "textbook_refs": [
                {
                    "name": "B02_相关资料切片.pdf",
                    "page": 19,
                    "label": "11.3 一元一次不等式组与公共解集",
                },
            ],
            "x": 1380,
            "y": 355,
        },
        {
            "id": "T03I3",
            "name": "根据实际限制列不等式并解释范围",
            "theme": "不等式与不等式组",
            "description": "抓住实际情境中的“至少”“不超过”等关键词列出不等式，求解后结合整数约束或实际限制解释取值范围。",
            "textbook_refs": [
                {
                    "name": "B02_相关资料切片.pdf",
                    "page": 14,
                    "label": "11.2 列一元一次不等式解决实际问题",
                },
            ],
            "x": 1380,
            "y": 530,
        },
    ],
    "edges": [
        {
            "id": "T01I1->T01I2",
            "source": "T01I1",
            "target": "T01I2",
            "relation": "合并同类项与去括号需先认识代数式中的项与系数。",
        },
        {
            "id": "T01I1->T01I3",
            "source": "T01I1",
            "target": "T01I3",
            "relation": "先会把数量关系写成代数式，才能进一步用整式解释规律。",
        },
        {
            "id": "T01I2->T01I3",
            "source": "T01I2",
            "target": "T01I3",
            "relation": "用整式解释问题通常需要先去括号、合并同类项化简。",
        },
        {
            "id": "T01I2->T02I1",
            "source": "T01I2",
            "target": "T02I1",
            "relation": "解一元一次方程的移项与合并同类项直接建立在整式加减之上。",
        },
        {
            "id": "T02I1->T02I2",
            "source": "T02I1",
            "target": "T02I2",
            "relation": "二元一次方程组消元后仍需按一元一次方程步骤求解。",
        },
        {
            "id": "T02I1->T02I3",
            "source": "T02I1",
            "target": "T02I3",
            "relation": "应用题建模列出方程后，依赖方程求解基本功得出结果。",
        },
        {
            "id": "T02I1->T03I1",
            "source": "T02I1",
            "target": "T03I1",
            "relation": "解不等式步骤与解一元一次方程对应，核心差异在负数乘除变号。",
        },
        {
            "id": "T03I1->T03I2",
            "source": "T03I1",
            "target": "T03I2",
            "relation": "求不等式组交集的前提是能正确解出每一个单独的不等式。",
        },
        {
            "id": "T03I1->T03I3",
            "source": "T03I1",
            "target": "T03I3",
            "relation": "列出实际问题不等式后，需正确求解才能给出取值范围。",
        },
    ],
}

_DEFAULT_REFS_BY_ID = {
    n["id"]: n["textbook_refs"]
    for n in DEFAULT_KNOWLEDGE_GRAPH["nodes"]
    if n.get("id") and n.get("textbook_refs")
}


def _normalize_textbook_refs(raw_refs) -> list[dict]:
    if not isinstance(raw_refs, list):
        return []
    cleaned: list[dict] = []
    for item in raw_refs:
        if not isinstance(item, dict):
            continue
        name = Path(str(item.get("name") or "").strip()).name
        if not name:
            continue
        try:
            page = max(1, int(item.get("page") or 1))
        except (TypeError, ValueError):
            page = 1
        label = str(item.get("label") or "").strip()
        cleaned.append({"name": name, "page": page, "label": label})
    return cleaned


def _normalize_graph_nodes(nodes: list, *, backfill_missing_defaults: bool) -> list[dict]:
    normalized: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        item = dict(node)
        nid = str(item.get("id") or "").strip()
        if "textbook_refs" in item:
            item["textbook_refs"] = _normalize_textbook_refs(item.get("textbook_refs"))
        elif backfill_missing_defaults and nid in _DEFAULT_REFS_BY_ID:
            item["textbook_refs"] = json.loads(
                json.dumps(_DEFAULT_REFS_BY_ID[nid], ensure_ascii=False)
            )
        else:
            item["textbook_refs"] = []
        normalized.append(item)
    return normalized


def load_knowledge_graph() -> dict:
    with _GRAPH_LOCK:
        if GRAPH_FILE.is_file():
            try:
                data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
                if (
                    isinstance(data, dict)
                    and isinstance(data.get("nodes"), list)
                    and isinstance(data.get("edges"), list)
                ):
                    return {
                        "nodes": _normalize_graph_nodes(
                            data["nodes"], backfill_missing_defaults=True
                        ),
                        "edges": data["edges"],
                    }
            except (OSError, ValueError):
                pass
        return json.loads(json.dumps(DEFAULT_KNOWLEDGE_GRAPH, ensure_ascii=False))


def save_knowledge_graph(payload: dict) -> dict:
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    edges = payload.get("edges") if isinstance(payload, dict) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("知识图谱数据格式错误，需包含 nodes 和 edges 列表")

    clean_data = {
        "nodes": _normalize_graph_nodes(nodes, backfill_missing_defaults=False),
        "edges": edges,
    }
    with _GRAPH_LOCK:
        GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with NamedTemporaryFile(
                "w",
                dir=GRAPH_FILE.parent,
                prefix=".knowledge-graph-",
                suffix=".tmp",
                encoding="utf-8",
                delete=False,
            ) as tmp:
                json.dump(clean_data, tmp, ensure_ascii=False, indent=2)
                temp_path = Path(tmp.name)
            temp_path.replace(GRAPH_FILE)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    return clean_data


def reset_knowledge_graph() -> dict:
    with _GRAPH_LOCK:
        GRAPH_FILE.unlink(missing_ok=True)
    return json.loads(json.dumps(DEFAULT_KNOWLEDGE_GRAPH, ensure_ascii=False))
