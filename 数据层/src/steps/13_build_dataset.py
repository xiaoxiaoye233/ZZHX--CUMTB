# -*- coding: utf-8 -*-
"""第 13 步：把五张原始表整合成一份干净数据集。

产出（全部落在 dataset/，仓库根下）：
    00_字典/            指标字典、题目字典、考试字典
    01_按学生/Dxx/       Dxx.json（四块：student + 三块表）+ Dxx_速览.csv（指标汇总）
    02_按班级/           班级总表、班级_指标汇总、班级_主题汇总
    03_按主题/           T01 / T02 / T03 各一张（40 人）
    04_质量与剔除/       质量检查清单、被剔除记录、多版本明细、判分存疑
    index.json           40 人索引 + 路径
    校验报告.md          本次生成的体检数字
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC / "lib"))

import dataset as DS  # noqa: E402
import versioning as VS  # noqa: E402
from tools import load_facts  # noqa: E402

DATA_DIR = ROOT / "赛题数据" / "赛题资料包" / "4_赛题数据" / "模拟学情数据"
OUT = ROOT / "dataset"

CHECK: list[tuple[str, bool, str]] = []


def _arg(name: str) -> str | None:
    argv = sys.argv[1:]
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return None


def _cli_src() -> Path | None:
    """`--src <目录>`：默认读赛题数据；上传流程指到 data/uploads/<批号>/_merged。"""
    value = _arg("--src")
    return Path(value).resolve() if value else None


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_ref(name: str, ok: bool, detail: str = "") -> None:
    """只对赛题那份模拟数据成立的数字。换一批真实数据时这一组整段跳过。"""
    check(name, ok, detail, group="参考数字")


def check(name: str, ok: bool, detail: str = "", group: str = "结构") -> None:
    """记一条断言。group 只是分类标签，条数由报告统计，别在文档里手写。"""
    CHECK.append((name, bool(ok), detail, group))


# 手写的、不该被脚本覆盖的产物（截图与两份说明文档）
KEEP_IN_DATASET = ("05_出处截图", "数据字典.md", "口径说明.md")


# --------------------------------------------------------------------------
# 表头
# --------------------------------------------------------------------------
H_IND_DICT = [
    ("indicator_id", "指标编号"), ("indicator_name", "指标名称"), ("theme_id", "主题编号"),
    ("theme_name", "主题名称"), ("curriculum_scope", "课标范围"), ("textbook_scope", "教材范围"),
    ("questions_in_bank", "全库题数"), ("question_ids", "题号列表"),
]
H_Q_DICT = [
    ("material_id", "材料编号"), ("theme_id", "主题"), ("indicator_id", "指标"),
    ("question_type", "题型"), ("full_score", "满分"), ("rubric_point_count", "评分点数"),
]
H_Q_DICT_FULL = [
    ("material_id", "材料编号"), ("material_type", "材料类型"), ("theme_id", "主题"), ("theme_name", "主题名称"),
    ("indicator_id", "指标"), ("indicator_name", "指标名称"), ("question_type", "题型"),
    ("full_score", "满分"), ("rubric_points", "评分点"), ("reference_answer", "参考答案"),
    ("source_file", "来源文件"),
]
H_Q_CONTENT = [
    ("material_id", "材料编号"), ("question_type", "题型"), ("stem", "题干"),
    ("options", "选项"), ("reference_answer", "参考答案"), ("explanation", "解析"),
    ("source_file", "来源文件"),
]
H_EXAM_DICT = [
    ("exam_id", "考试编号"), ("exam_date", "考试日期"), ("taught_themes", "已教主题"),
    ("questions_available", "可用题数"), ("note", "说明"),
]
H_REC = [
    ("record_id", "记录编号"), ("exam_id", "考试"), ("question_id", "题目"), ("theme_id", "主题"),
    ("indicator_id", "指标"), ("full_score", "满分"), ("score", "得分"),
    ("score_rate", "得分率"), ("rubric_scores", "评分点得分"), ("counted_in_denominator", "计入分母"),
    ("grading_flag", "判分标记"),
]
H_IND = [
    ("row_type", "行类型"), ("theme_id", "主题编号"), ("theme_name", "主题名称"), ("indicator_id", "指标编号"),
    ("indicator_name", "指标名称"), ("questions_in_bank", "全库题数"), ("questions_available", "他能考到"),
    ("distinct_attempted", "做过不同题目"), ("evidence_threshold", "判定线"), ("coverage_rate", "覆盖率"), ("score", "得分"),
    ("full_score", "满分"), ("score_rate", "得分率"), ("conclusion_level", "档位"),
    ("reason", "档位说明"), ("curriculum_scope", "课标范围"),
    ("textbook_scope", "教材范围"), ("supplementary_question_ids", "可补练习题"),
]
H_EXAM = [
    ("exam_id", "考试"), ("exam_date", "日期"), ("theme_id", "主题"), ("indicator_id", "指标"),
    ("indicator_name", "指标名称"), ("participated", "参加了"), ("questions_in_exam", "本场题数"),
    ("distinct_attempted", "本场做过"), ("score", "得分"), ("full_score", "满分"),
    ("score_rate", "得分率"), ("teaching_status", "本场教学状态"), ("note", "说明"),
]
H_CLASS_OVERVIEW = [
    ("student_id", "学生"), ("class_id", "班级"), ("record_count", "记录数"),
    ("distinct_question_count", "不同题目"), ("available_question_count", "他能考到"),
    ("score", "得分"), ("full_score", "满分"), ("score_rate", "得分率"),
    ("t01_score_rate", "T01 得分率"), ("t02_score_rate", "T02 得分率"), ("t03_score_rate", "T03 得分率"),
]
H_CLASS_IND = [
    ("group", "群体"), ("student_count", "人数"), ("theme_id", "主题"), ("indicator_id", "指标"),
    ("indicator_name", "指标名称"), ("questions_available_total", "可考题数合计"),
    ("distinct_attempted_total", "做过题数合计"), ("score", "得分"), ("full_score", "满分"),
    ("score_rate", "得分率"), ("students_with_records", "有记录人数"),
]
H_CLASS_THEME = [
    ("group", "群体"), ("student_count", "人数"), ("theme_id", "主题"), ("theme_name", "主题名称"),
    ("distinct_attempted_total", "做过题数合计"), ("score", "得分"), ("full_score", "满分"),
    ("score_rate", "得分率"), ("students_with_records", "有记录人数"),
]
H_THEME_STUDENT = [
    ("student_id", "学生"), ("class_id", "班级"), ("questions_available", "本主题可考"),
    ("distinct_attempted", "做过"), ("score", "得分"), ("full_score", "满分"), ("score_rate", "得分率"),
    ("i1_score_rate", "指标一得分率"), ("i2_score_rate", "指标二得分率"), ("i3_score_rate", "指标三得分率"),
]
H_QUALITY = [
    ("issue_code", "问题代码"), ("severity", "严重程度"), ("record_count", "记录数"),
    ("sample_record_ids", "样例记录"), ("description", "说明"), ("handling", "处置"),
    ("affects_denominator", "影响分母"),
]
H_EXCLUDED = [
    ("record_id", "记录编号"), ("student_id", "学生"), ("question_id", "题目"), ("exam_id", "考试"),
    ("revision_version", "修订版本"), ("scoring_status", "评分状态"), ("score", "得分"),
    ("full_score", "满分"), ("exclusion_reason", "剔除原因"),
]
H_MULTI = [
    ("event_id", "作答事件"), ("student_id", "学生"), ("question_id", "题目"),
    ("revision_version", "修订版本"), ("scoring_status", "评分状态"), ("score", "得分"), ("is_final", "是否采用"),
]
H_SUSPECT = [
    ("record_id", "记录编号"), ("student_id", "学生"), ("question_id", "题目"),
    ("grading_flag", "判分标记"), ("note", "说明"),
]
H_CITATION = [
    ("group", "小节"), ("theme_id", "主题"), ("section_heading", "课标小节"), ("item_label", "条目"),
    ("text", "课标原文"), ("used_by_indicators", "用于指标"), ("file_page", "文件页"), ("body_page", "正文页"),
]
H_MANIFEST = [("path", "文件"), ("bytes", "字节"), ("sha256", "sha256")]



def _with_names(rows: list[dict], ind_dict: list[dict]) -> list[dict]:
    """CSV 专用：把 JSON 里省掉的指标名、主题名补回来（JSON 去字典查即可）。"""
    ind_name = {r["indicator_id"]: r["indicator_name"] for r in ind_dict}
    theme_name = {r["theme_id"]: r["theme_name"] for r in ind_dict}
    out = []
    for r in rows:
        row = dict(r)
        iid, tid = row.get("indicator_id"), row.get("theme_id")
        row["indicator_name"] = ind_name.get(iid) or theme_name.get(tid)
        row["theme_name"] = theme_name.get(tid)
        out.append(row)
    return out


def _count(quality: dict, code: str) -> int:
    """质量清单里某类问题的记录数；这类问题一条都没有时返回 0（不抛 StopIteration）。"""
    for row in quality["质量检查清单"]:
        if row["issue_code"] == code:
            return row["record_count"]
    return 0


def _recover(target: Path) -> None:
    """上一次换盘被掐断的恢复：target 不见了但 target.old 还在，就改回来。"""
    old = target.with_name(target.name + ".old")
    if not target.exists() and old.exists():
        old.rename(target)
        print(f"[恢复] {target.name} 不见了，已用 {old.name} 换回去")
    elif target.exists() and old.exists():
        shutil.rmtree(old, ignore_errors=True)


def _swap(stage: Path, target: Path) -> None:
    """把暂存目录换成正式目录，只用两次改名。

    不能"先删 target 再逐个 move"——被 kill 在中间就只剩半份。这里：
        target → target.old（一次改名，内容完整）
        stage  → target     （再一次改名）
    两次之间只有毫秒级窗口，任何时刻磁盘上都有一整套完整文件；
    真被掐在中间，下次启动 `_recover()` 会把它改回来。
    """
    old = target.with_name(target.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if target.exists():
        target.rename(old)
    stage.rename(target)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)


def main() -> int:
    global OUT
    data_dir = _cli_src() or DATA_DIR
    if not data_dir.is_dir():
        print(f"[错误] 数据源不存在：{data_dir}")
        return 2
    out_override = _arg("--out")
    target = Path(out_override).resolve() if out_override else (ROOT / "dataset")
    write_ledger = "--no-ledger" not in sys.argv
    if not write_ledger and out_override is None:
        print(
            "[错误] --no-ledger 只能和 --out 一起用。"
            "否则 dataset/ 会被改写而台账停在上一次，下次 latest_build 会拿旧台账当基准。"
        )
        return 2
    store = load_facts(data_dir)

    # 先全部写进暂存目录，断言全过才换上去（半成品不落进 dataset/）
    _recover(target)
    staging = target.parent / f"_{target.name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    OUT = staging

    # ---- 字典 ----
    ind_dict = DS.build_indicator_dict(store)
    q_dict = DS.build_question_dict(store)
    q_dict_full = DS.build_question_dict_full(store)
    q_content = DS.build_question_content(store)
    exam_dict = DS.build_exam_dict(store)
    DS.write_csv(OUT / "00_字典" / "指标字典.csv", ind_dict, H_IND_DICT)
    DS.write_json(OUT / "00_字典" / "指标字典.json", ind_dict)
    DS.write_csv(OUT / "00_字典" / "题目字典.csv", q_dict_full, H_Q_DICT_FULL)
    DS.write_json(OUT / "00_字典" / "题目字典.json", q_dict)
    DS.write_json(OUT / "06_题目内容.json", q_content)
    DS.write_csv(OUT / "00_字典" / "考试字典.csv", exam_dict, H_EXAM_DICT)
    DS.write_json(OUT / "00_字典" / "考试字典.json", exam_dict)

    # ---- 课标原文（数据集里只写编号，原文单独可查）----
    ctext = DS.build_citation_text(store)
    DS.write_json(OUT / "00_字典" / "课标原文.json", ctext)
    DS.write_csv(OUT / "00_字典" / "课标原文.csv", ctext["原文条目"], H_CITATION)

    # ---- 个人 ----
    index_rows = []
    record_total = 0
    level_counts = {"证据充足": 0, "证据偏少": 0, "证据不足": 0}
    for sid in sorted(store.student_facts):
        pkg = DS.build_student_package(store, sid)
        for row in pkg["indicator_summary"]:
            if row["row_type"] == "indicator":
                level_counts[row["conclusion_level"]] += 1
        DS.write_json(OUT / "01_按学生" / sid / f"{sid}.json", pkg)
        DS.write_csv(
            OUT / "01_按学生" / sid / f"{sid}_速览.csv",
            _with_names(pkg["indicator_summary"], ind_dict),
            H_IND,
        )
        record_total += len(pkg["question_records"])
        s = pkg["student"]
        index_rows.append(
            {
                "student_id": s["student_id"], "class_id": s["class_id"],
                "record_count": s["record_count"], "distinct_question_count": s["distinct_question_count"],
                "score_total": s["score_total"], "full_score_total": s["full_score_total"],
                "score_rate": s["score_rate"],
                "path": f"01_按学生/{sid}/{sid}.json",
            }
        )

    # ---- 班级 ----
    class_overview = DS.build_class_overview(store)
    class_ind = DS.build_class_indicator_table(store)
    class_theme = DS.build_class_theme_table(store)
    DS.write_csv(OUT / "02_按班级" / "班级总表.csv", class_overview, H_CLASS_OVERVIEW)
    DS.write_json(OUT / "02_按班级" / "班级总表.json", class_overview)
    DS.write_csv(OUT / "02_按班级" / "班级_指标汇总.csv", class_ind, H_CLASS_IND)
    DS.write_json(OUT / "02_按班级" / "班级_指标汇总.json", class_ind)
    DS.write_csv(OUT / "02_按班级" / "班级_主题汇总.csv", class_theme, H_CLASS_THEME)
    DS.write_json(OUT / "02_按班级" / "班级_主题汇总.json", class_theme)

    # ---- 按主题 ----
    theme_tables = {}
    for theme in DS.THEME_ORDER:
        name = store.catalogs.theme_names[theme]
        rows = DS.build_theme_student_table(store, theme)
        theme_tables[theme] = rows
        base = OUT / "03_按主题" / f"{theme}_{name}"
        DS.write_csv(base.with_suffix(".csv"), rows, H_THEME_STUDENT)
        DS.write_json(base.with_suffix(".json"), rows)

    # ---- 质量与剔除 ----
    quality = DS.build_quality_tables(store)
    DS.write_csv(OUT / "04_质量与剔除" / "质量检查清单.csv", quality["质量检查清单"], H_QUALITY)
    DS.write_json(OUT / "04_质量与剔除" / "质量检查清单.json", quality["质量检查清单"])
    DS.write_csv(OUT / "04_质量与剔除" / "被剔除记录.csv", quality["被剔除记录"], H_EXCLUDED)
    DS.write_json(OUT / "04_质量与剔除" / "被剔除记录.json", quality["被剔除记录"])
    DS.write_csv(OUT / "04_质量与剔除" / "多版本明细.csv", quality["多版本明细"], H_MULTI)
    DS.write_json(OUT / "04_质量与剔除" / "多版本明细.json", quality["多版本明细"])
    DS.write_csv(OUT / "04_质量与剔除" / "判分存疑.csv", quality["判分存疑"], H_SUSPECT)
    DS.write_json(OUT / "04_质量与剔除" / "判分存疑.json", quality["判分存疑"])

    # ---- 基准数字（31 条：改代码后跑一次，看这几条有没有变） ----
    def _sum(rows, key):
        return sum(r[key] for r in rows if r.get(key) is not None)

    cls_totals = {
        c: (
            _sum([r for r in class_overview if r["class_id"] == c], "score"),
            _sum([r for r in class_overview if r["class_id"] == c], "full_score"),
        )
        for c in ("DC01", "DC02")
    }
    theme_rate = {(r["group"], r["theme_id"]): r["score_rate"] for r in class_theme}
    d14 = DS.build_student_package(store, "D14")
    gpkg = DS.build_student_package(store, "D17")
    gpkg_ind = {r["indicator_id"]: r for r in gpkg["indicator_summary"] if r["row_type"] == "indicator"}

    baseline = [
        ("raw_record_count", 806, len(store.datasets.records), "条", "作答记录原始行数", "赛题数据/作答记录.csv"),
        ("used_record_count", 788, record_total, "条", "进统计的记录", "index.json / record_count"),
        ("excluded_record_count", 18, len(quality["被剔除记录"]), "条", "被剔除记录", "04_质量与剔除/被剔除记录"),
        ("multi_version_groups", 7, _count(quality, "multi_version"), "组", "同一作答的多个修订版本组数", "质量检查清单 multi_version"),
        ("multi_version_rows", 14, len(quality["多版本明细"]), "行", "多出来的旧版本条目", "04_质量与剔除/多版本明细"),
        ("pending_score_records", 4, _count(quality, "pending_score"), "条", "待评分", "质量检查清单 pending_score"),
        ("blank_attempt_records", 5, _count(quality, "blank_attempt"), "条", "未作答", "质量检查清单 blank_attempt"),
        ("score_over_full_records", 2, _count(quality, "score_over_full"), "条", "得分超满分", "质量检查清单 score_over_full"),
        ("cross_node_duplicate_pairs", 37, _count(quality, "cross_node_duplicate"), "对", "同一道题两场都做过", "质量检查清单 cross_node_duplicate"),
        ("grading_suspect_records", 9, len(quality["判分存疑"]), "条", "判分存疑（只标不改）", "04_质量与剔除/判分存疑"),
        ("total_score", 745, _sum(class_overview, "score"), "分", "全班得分", "02_按班级/班级总表 求和"),
        ("total_full_score", 1306, _sum(class_overview, "full_score"), "分", "全班满分", "02_按班级/班级总表 求和"),
        ("overall_score_rate", 0.5704, round(_sum(class_overview, "score") / _sum(class_overview, "full_score"), 4), "比率", "745÷1306", "口径说明"),
        ("DC01_score_rate", 0.5871, round(cls_totals["DC01"][0] / cls_totals["DC01"][1], 4), "比率", "418÷712", "班级总表 DC01 求和"),
        ("DC02_score_rate", 0.5505, round(cls_totals["DC02"][0] / cls_totals["DC02"][1], 4), "比率", "327÷594", "班级总表 DC02 求和"),
        ("T02_gap_DC02_vs_DC01", 0.1323, round(theme_rate[("DC01", "T02")] - theme_rate[("DC02", "T02")], 4), "比率", "T02 上 DC01 比 DC02 高 13.23 个百分点", "班级_主题汇总"),
        ("grade_T01_score_rate", 0.5771, theme_rate[("全年级", "T01")], "比率", "全年级 T01", "班级_主题汇总"),
        ("student_count", 40, len(index_rows), "人", "40 人", "index.json"),
        ("class_count", 2, len({r["class_id"] for r in class_overview}), "个", "DC01 / DC02", "班级总表"),
        ("question_count", 54, len(q_dict), "道", "Q001–Q054", "题目字典"),
        ("exam_count", 2, len(exam_dict), "场", "N01 / N02", "考试字典"),
        ("indicator_count", 9, len(ind_dict), "个", "3 主题 × 3 指标", "指标字典"),
        ("questions_per_indicator", "6,10,2,8,6,4,7,7,4", ",".join(str(r["questions_in_bank"]) for r in ind_dict), "道", "九个指标各自题库题量", "指标字典 questions_in_bank"),
        ("D17_record_count", 4, len(gpkg["question_records"]), "条", "D17 记录最少", "01_按学生/D17"),
        ("D17_T01I1_coverage", 0.3333, gpkg_ind["T01I1"]["coverage_rate"], "比率", "2÷6", "01_按学生/D17"),
        ("D14_score_rate", 0.9783, d14["student"]["score_rate"], "比率", "表现最好的代表学生", "01_按学生/D14"),
        ("level_证据充足", 132, level_counts["证据充足"], "格", "九个指标里有足够证据、可以下判断的（40 人 × 9 格）", "指标行 conclusion_level 计数"),
        ("level_证据偏少", 159, level_counts["证据偏少"], "格", "有一点证据、只能看出方向", "指标行 conclusion_level 计数"),
        ("level_证据不足", 69, level_counts["证据不足"], "格", "一道没做或没教到，不下判断", "指标行 conclusion_level 计数"),
        ("D17_T01I1_level", "证据偏少", gpkg_ind["T01I1"]["conclusion_level"], "档", "D17 只做过 2 道、判定线 3 道", "01_按学生/D17 T01I1"),
        ("D17_T01I1_threshold", 3, gpkg_ind["T01I1"]["evidence_threshold"], "道", "T01I1 的判定线：可考 6 道，min(3,6) 但下限 2，取 3", "01_按学生/D17 T01I1 evidence_threshold"),
    ]
    baseline_rows = []
    for name, expected, actual, unit, desc, source in baseline:
        baseline_rows.append(
            {"name": name, "expected": expected, "actual": actual, "unit": unit, "description": desc, "source": source}
        )
    baseline_payload = {
        "说明": "这份文件把整个数据集里最关键的 31 个数字钉住。改完代码跑一次 13_build_dataset.py，"
        "拿这一份对一遍：全对上，说明数据没被改坏；有不上的，说明口径被动过，先查清再往下走。",
        "怎么用": "跑一次 13_build_dataset.py，看校验报告里「基准 」开头的断言；"
        "或在本文件上逐条看 expected 与 actual。",
        "rule_set": "R1–R13",
        "数字": baseline_rows,
    }
    DS.write_json(OUT / "04_质量与剔除" / "基准数字.json", baseline_payload)

    # ---- 索引 ----
    now = datetime.now()
    build_id = now.strftime("%Y%m%d-%H%M%S")
    index = {
        "schema_version": "1.2",
        "build_id": build_id,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "quality": {
            "raw_records": len(store.datasets.records),
            "used_records": record_total,
            "excluded_records": len(quality["被剔除记录"]),
            "pending_score": _count(quality, "pending_score"),
            "blank_attempt": _count(quality, "blank_attempt"),
            "grading_suspect": len(quality["判分存疑"]),
            "note": "判分存疑只标注不改分；剔除记录逐条可查 04_质量与剔除/。",
        },
        "rule_set": [f"R{i}" for i in range(1, 14)],
        "student_count": len(index_rows),
        "record_count": record_total,
        "exam_count": len(exam_dict),
        "exams": [e["exam_id"] for e in exam_dict],
        "columns_note": "空值一律 null：null = 没考到/没出题/没数据；0.0 = 考了但没得分。",
        "students": index_rows,
    }
    DS.write_json(OUT / "index.json", index)

    # ---------------- 体检 ----------------
    # 分两层：
    #   ① 通用结构检查：换一批数据也必须成立（跨表自洽、字段齐全、不带 NaN）
    #   ② 参考数据基准：数字钉在赛题那份数据上，只有数据源就是它时才断言
    d17 = DS.build_student_package(store, "D17")
    d17_ind = {r["indicator_id"]: r for r in d17["indicator_summary"] if r["row_type"] == "indicator"}
    d03 = DS.build_student_package(store, "D03")
    whole = next(r for r in class_overview if r["student_id"])
    full_row = next(r for r in class_theme if r["group"] == "全年级" and r["theme_id"] == "T01")
    n_ind, n_theme = len(ind_dict), len(theme_tables)
    n_group = len({r["group"] for r in class_theme})
    student_ids = [r["student_id"] for r in index_rows]
    packages = {sid: DS.build_student_package(store, sid) for sid in student_ids}
    n_suspect = sum(1 for _, r in store.grading_flags.iterrows() if str(r["判分可靠性"]) != "正常")

    check("每个学生的 JSON 都是四块", all(len(packages[sid]) == 4 for sid in student_ids))
    check(
        "每个学生指标汇总 = 指标数 + 主题数",
        all(len(packages[sid]["indicator_summary"]) == n_ind + n_theme for sid in student_ids),
        f"{n_ind}+{n_theme}",
    )
    check("班级总表行数 = 学生数", len(class_overview) == len(student_ids), f"{len(class_overview)} / {len(student_ids)}")
    check("班级指标汇总 = 指标数 × 分组数", len(class_ind) == n_ind * n_group, f"{len(class_ind)} / {n_ind}×{n_group}")
    check("班级主题汇总 = 主题数 × 分组数", len(class_theme) == n_theme * n_group, f"{len(class_theme)} / {n_theme}×{n_group}")
    check("按主题每张 = 学生数", all(len(v) == len(student_ids) for v in theme_tables.values()), str(len(student_ids)))
    check("指标字典行数 = 课程要求行数", len(ind_dict) == len(store.datasets.curriculum), f"{len(ind_dict)} / {len(store.datasets.curriculum)}")
    check("题目字典 json = 题目内容条数", len(q_dict) == len(q_content), f"{len(q_dict)} / {len(q_content)}")
    check("题目字典 json 不含题干", "stem" not in q_dict[0], "")
    check("考试对比里没有'没参加'的指标行", all(
        r["row_type"] == "exam_total" or "没有参加" not in str(r.get("note") or "")
        for sid in student_ids for r in packages[sid]["exam_comparison"]
    ))
    check("考试对比每场都有小计行", all(
        sum(1 for r in packages[sid]["exam_comparison"] if r["row_type"] == "exam_total") == len(exam_dict)
        for sid in student_ids
    ), str(len(exam_dict)))
    check("剔除数 + 进统计数 = 原始行数", len(quality["被剔除记录"]) + record_total == len(store.datasets.records),
          f"{len(quality['被剔除记录'])}+{record_total}")
    check("多版本明细 = 2 × 多版本组数", len(quality["多版本明细"]) == 2 * _count(quality, "multi_version"))
    check("判分存疑 = 非正常标签条数", len(quality["判分存疑"]) == n_suspect, f"{len(quality['判分存疑'])} / {n_suspect}")
    check("课标原文条目 20 条（三段小节全部条目）", len(ctext["原文条目"]) == 20, str(len(ctext["原文条目"])))
    check("课标原文没有空条目", all(str(r["text"]).strip() for r in ctext["原文条目"]))
    check("课标指标对应 13 条", len(ctext["指标对应"]) == 13, str(len(ctext["指标对应"])))
    check(
        "T03 两条共用同一句原文（拆分可追溯）",
        next(r["quote_full"] for r in ctext["指标对应"] if r["indicator_id"] == "T03I1" and r["item_label"] == "②")
        == next(r["quote_full"] for r in ctext["指标对应"] if r["indicator_id"] == "T03I2" and r["item_label"] == "②"),
    )
    check("index 路径都存在", all((OUT / r["path"]).exists() for r in index_rows))
    first_json = OUT / "01_按学生" / student_ids[0] / f"{student_ids[0]}.json"
    check("无 NaN 字符串", "NaN" not in first_json.read_text(encoding="utf-8"))
    check("无 None 字符串", "None" not in first_json.read_text(encoding="utf-8"))
    check("所有得分率在 0~1 之间", all(r["score_rate"] is None or 0 <= r["score_rate"] <= 1 for r in index_rows))

    # ---- 算账：这些恒等式跟具体是哪一批数据无关，换一批真实数据也该成立 ----
    # 结构断言只能发现"数字错位"，只有这里能发现"数字算错"。
    def _f4(x):
        return None if x is None else round(float(x), 4)

    rec = store.clean.records_clean
    per = rec.groupby("学生编号").agg(
        score=("得分", "sum"), full=("满分", "sum"),
        n_rows=("记录编号", "size"), n_q=("材料编号", "nunique"),
    )
    stu_bad = []
    for sid in student_ids:
        s = packages[sid]["student"]
        try:
            want = per.loc[sid]
        except KeyError:
            stu_bad.append(f"{sid} 没有记录")
            continue
        if (_f4(s["score_total"]) != _f4(want["score"])
                or _f4(s["full_score_total"]) != _f4(want["full"])
                or s["record_count"] != int(want["n_rows"])
                or s["distinct_question_count"] != int(want["n_q"])):
            stu_bad.append(sid)
    check("每个学生的合计 = 他自己的记录之和（得分/满分/条数/题目数）", not stu_bad, str(stu_bad[:5]), group="算账")

    # 学生的"能考到多少题"要等于 9 个指标的可考之和；做过题数同理
    sum_bad = []
    for sid in student_ids:
        rows = [r for r in packages[sid]["indicator_summary"] if r["row_type"] == "indicator"]
        s = packages[sid]["student"]
        if (sum(r["questions_available"] for r in rows) != s["available_question_count"]
                or sum(r["distinct_attempted"] for r in rows) != s["distinct_question_count"]):
            sum_bad.append(sid)
    check("学生的可考题数 / 做过题数 = 9 个指标之和", not sum_bad, str(sum_bad[:5]), group="算账")

    row_bad, cov_bad = [], []
    for sid in student_ids:
        for r in packages[sid]["question_records"]:
            full = r["full_score"]
            if r["score"] > full:
                row_bad.append(f"{r['record_id']} 超满分")
            if _f4(r["score_rate"]) != (None if not full else _f4(r["score"] / full)):
                row_bad.append(f"{r['record_id']} 率")
    check("每条记录：得分 ≤ 满分，且得分率 = 得分 ÷ 满分", not row_bad, str(row_bad[:5]), group="算账")

    ind_bad = []
    for sid in student_ids:
        for r in packages[sid]["indicator_summary"]:
            if r["row_type"] != "indicator":
                continue
            avail, did = r["questions_available"], r["distinct_attempted"]
            if not (did <= avail <= r["questions_in_bank"]):
                ind_bad.append(f"{sid}/{r['indicator_id']} 上下界")
            if r["coverage_rate"] != (None if not avail else _f4(did / avail)):
                ind_bad.append(f"{sid}/{r['indicator_id']} 覆盖率")
            if r["score"] is not None and _f4(r["score_rate"]) != _f4(r["score"] / r["full_score"]):
                ind_bad.append(f"{sid}/{r['indicator_id']} 得分率")
    check("指标行：做过 ≤ 可考 ≤ 全库题数；覆盖率 = 做过 ÷ 可考；得分率 = 得分 ÷ 满分", not ind_bad, str(ind_bad[:5]), group="算账")

    # 判定线：可考 0 道时保持题库上限（min(3, 题库)），否则 max(2, min(min(3, 题库), 可考))。
    # 这条只验"判定线算得对不对"，不验档位高低——档位怎么来的由 facts 决定。
    def _threshold(bank: int, avail: int) -> int:
        if avail == 0:
            return min(3, bank)
        return max(2, min(min(3, bank), avail))

    thr_bad = []
    for sid in student_ids:
        for r in packages[sid]["indicator_summary"]:
            if r["row_type"] != "indicator":
                continue
            want = _threshold(r["questions_in_bank"], r["questions_available"])
            if r["evidence_threshold"] != want:
                thr_bad.append(f"{sid}/{r['indicator_id']} {r['evidence_threshold']}≠{want}")
            if r["distinct_attempted"] >= want and r["conclusion_level"] != "证据充足":
                thr_bad.append(f"{sid}/{r['indicator_id']} 够了却没判充足")
            if 0 < r["distinct_attempted"] < want and r["conclusion_level"] != "证据偏少":
                thr_bad.append(f"{sid}/{r['indicator_id']} 不够却没判偏少")
    check("指标行判定线 = max(2, min(min(3,题库),可考))，档位按「做过 vs 判定线」分", not thr_bad, str(thr_bad[:5]), group="算账")
    theme_thr_bad = [
        f"{sid}/{r['indicator_id']}"
        for sid in student_ids
        for r in packages[sid]["indicator_summary"]
        if r["row_type"] == "theme" and r["evidence_threshold"] != 3
    ]
    check("主题小计的判定线 = 3 道不同题", not theme_thr_bad, str(theme_thr_bad[:5]), group="算账")

    theme_bad, exam_bad = [], []
    for sid in student_ids:
        rows = packages[sid]["indicator_summary"]
        for tid in {r["theme_id"] for r in rows}:
            kids = [r for r in rows if r["row_type"] == "indicator" and r["theme_id"] == tid]
            tot = next(r for r in rows if r["row_type"] == "theme" and r["theme_id"] == tid)
            if tot["score"] is None:
                continue
            # 个别指标整格是 null（可考 0 或没做过），求和时按 0 算，
            # 但只在该格确实没有分的情况下——有分就必须加进来
            def _v(row, key):
                val = row[key]
                return 0 if val is None else val
            if (_f4(tot["score"]) != _f4(sum(_v(k, "score") for k in kids))
                    or _f4(tot["full_score"]) != _f4(sum(_v(k, "full_score") for k in kids))
                    or tot["distinct_attempted"] != sum(_v(k, "distinct_attempted") for k in kids)
                    or tot["questions_available"] != sum(_v(k, "questions_available") for k in kids)):
                theme_bad.append(f"{sid}/{tid}")
        ec = packages[sid]["exam_comparison"]
        for eid in {r["exam_id"] for r in ec}:
            det = [r for r in ec if r["row_type"] == "indicator" and r["exam_id"] == eid]
            tot = next(r for r in ec if r["row_type"] == "exam_total" and r["exam_id"] == eid)
            if tot["score"] is None:
                continue
            if (_f4(tot["score"]) != _f4(sum(r["score"] or 0 for r in det))
                    or _f4(tot["full_score"]) != _f4(sum(r["full_score"] or 0 for r in det))
                    or tot["distinct_attempted"] != sum(r["distinct_attempted"] or 0 for r in det)
                    or tot["questions_in_exam"] is None):
                exam_bad.append(f"{sid}/{eid}")
    check("主题小计 = 该主题三个指标行之和", not theme_bad, str(theme_bad[:5]), group="算账")
    check("每场小计 = 该场各指标行之和", not exam_bad, str(exam_bad[:5]), group="算账")

    cls_bad = [r["student_id"] for r in class_overview
               if _f4(r["score"]) != _f4(packages[r["student_id"]]["student"]["score_total"])
               or _f4(r["score_rate"]) != _f4(r["score"] / r["full_score"] if r["full_score"] else None)]
    check("班级总表每行 = 该学生合计，得分率 = 得分 ÷ 满分", not cls_bad, str(cls_bad[:5]), group="算账")

    grp_bad, grp_rate_bad = [], []
    for r in class_ind:
        grp = r["group"]
        sids = student_ids if grp == "全年级" else [
            s for s in student_ids if packages[s]["student"]["class_id"] == grp]
        tot = 0.0
        ful = 0.0
        for s in sids:
            row = next((x for x in packages[s]["indicator_summary"]
                        if x["row_type"] == "indicator" and x["indicator_id"] == r["indicator_id"]), None)
            if row and row["score"] is not None:
                tot += row["score"]
                ful += row["full_score"]
        if _f4(r["score"]) != _f4(tot) or _f4(r["full_score"]) != _f4(ful):
            grp_bad.append(f"{grp}/{r['indicator_id']}")
        if r["score"] is not None and _f4(r["score_rate"]) != _f4(r["score"] / r["full_score"] if r["full_score"] else None):
            grp_rate_bad.append(f"{grp}/{r['indicator_id']}")
    check("班级指标汇总 = 该组学生该指标之和", not grp_bad, str(grp_bad[:5]), group="算账")
    check("班级指标汇总的得分率 = 得分 ÷ 满分", not grp_rate_bad, str(grp_rate_bad[:5]), group="算账")

    theme_rate_bad = [f"{r['student_id']}/{tid}" for tid, rows in theme_tables.items() for r in rows
                      if r["score"] is not None
                      and _f4(r["score_rate"]) != _f4(r["score"] / r["full_score"] if r["full_score"] else None)]
    check("按主题每行的得分率 = 得分 ÷ 满分", not theme_rate_bad, str(theme_rate_bad[:5]), group="算账")

    # 口径卡 R5：证据强度只按"不同题目数"分档（15 / 8），不是按题次。
    # 这条断言把"文档写的那条口径"和"代码实际用的那个字段"钉在一起，
    # 以后谁把 _strength 改成吃 valid_record_count，这里立刻红。
    def _strength_by_r5(distinct: int) -> str:
        if distinct >= 15:
            return "充足"
        if distinct >= 8:
            return "偏少"
        return "不足"

    strength_bad = [
        f"{s}:{f.evidence_strength_level}≠{_strength_by_r5(f.distinct_attempted_question_count)}"
        for s, f in store.student_facts.items()
        if f.evidence_strength_level != _strength_by_r5(f.distinct_attempted_question_count)
    ]
    check("证据强度按「不同题目数」分档（15 / 8），不是按题次", not strength_bad,
          str(strength_bad[:5]), group="算账")

    is_reference = data_dir.resolve() == DATA_DIR.resolve()
    if is_reference:
        # ② 参考数据基准：这些数字只对赛题那份数据成立
        check_ref("学生 40 人", len(index_rows) == 40, str(len(index_rows)))
        check_ref("记录合计 788", record_total == 788, str(record_total))
        check_ref("每人指标汇总 12 行（9+3）", len(d17["indicator_summary"]) == 12, str(len(d17["indicator_summary"])))
        ec = d17["exam_comparison"]
        check_ref("考试对比只留这场真出了题的行 + 每场小计", len(ec) < 20, str(len(ec)))
        check_ref("考试对比保留两场小计", sum(1 for r in ec if r["row_type"] == "exam_total") == 2, "")
        check_ref("题目内容 54 条（题号 Q 开头）", len(q_content) == 54, str(len(q_content)))
        check_ref("D17/T01I1 得分 4", d17_ind["T01I1"]["score"] == 4, str(d17_ind["T01I1"]["score"]))
        check_ref("D17/T01I1 满分 4", d17_ind["T01I1"]["full_score"] == 4, str(d17_ind["T01I1"]["full_score"]))
        check_ref("D17/T01I1 覆盖 0.3333", d17_ind["T01I1"]["coverage_rate"] == 0.3333, str(d17_ind["T01I1"]["coverage_rate"]))
        check_ref("D17/T02I2 可考 0", d17_ind["T02I2"]["questions_available"] == 0, str(d17_ind["T02I2"]["questions_available"]))
        check_ref("D17/T02I2 全部为 null", d17_ind["T02I2"]["score"] is None and d17_ind["T02I2"]["score_rate"] is None)
        check_ref("D03 记录 19 条", len(d03["question_records"]) == 19, str(len(d03["question_records"])))
        check_ref("班级总表 40 行", len(class_overview) == 40, str(len(class_overview)))
        check_ref("班级指标汇总 27 行", len(class_ind) == 27, str(len(class_ind)))
        check_ref("班级主题汇总 9 行", len(class_theme) == 9, str(len(class_theme)))
        check_ref("按主题三张各 40 行", all(len(v) == 40 for v in theme_tables.values()))
        check_ref("指标字典 9 行", len(ind_dict) == 9, str(len(ind_dict)))
        check_ref("题目字典 json 54 题（只留结构）", len(q_dict) == 54, str(len(q_dict)))
        check_ref("题目字典 csv 65 行（含学习卡与教材条）", len(q_dict_full) == 65, str(len(q_dict_full)))
        check_ref("考试字典 2 行", len(exam_dict) == 2, str(len(exam_dict)))
        check_ref("被剔除 18 条", len(quality["被剔除记录"]) == 18, str(len(quality["被剔除记录"])))
        check_ref("多版本 14 行", len(quality["多版本明细"]) == 14, str(len(quality["多版本明细"])))
        check_ref("判分存疑 9 条", len(quality["判分存疑"]) == 9, str(len(quality["判分存疑"])))
        check_ref("全年级 T01 得分率 0.5771", full_row["score_rate"] == 0.5771, str(full_row["score_rate"]))
        for g in baseline_rows:
            check(f"基准 {g['name']}", str(g["expected"]) == str(g["actual"]),
                  f"{g['actual']}", group="基准")
    else:
        print(
            f"[基准] 数据源不是赛题原始数据（{data_dir}），"
            "31 条基准数字与 40 人 / 788 条这类数字只记进台账、不做断言（换一批数据它们本来就该变）。"
        )

    # ---- 版本号 ----
    check("build_id 形如 20260101-090000", bool(re.fullmatch(r"\d{8}-\d{6}", build_id)), build_id, group="落盘")
    check("index.json 的 build_id 与本次一致", _read_json(OUT / "index.json")["build_id"] == build_id, group="落盘")

    # ---- 闸门：断言全过才落盘；有失败就把整份暂存丢掉，dataset/ 一个字都不动 ----
    failed_now = [c for c in CHECK if not c[1]]
    if failed_now:
        shutil.rmtree(staging, ignore_errors=True)
        for name, ok, detail, group in CHECK:
            print(f"[{'PASS' if ok else 'FAIL'}] [{group}] {name} {detail}")
        print(
            f"共 {len(CHECK) - len(failed_now)} 条断言通过，{len(failed_now)} 条失败。"
            f"本次没有落盘：{target} 保持上一版，也没写台账。"
        )
        return 1

    # ---- 手写的东西（截图与两份说明）不归脚本管，换盘前先搬进暂存 ----
    # 换盘是整目录改名，不搬过去就会跟着旧目录一起被删掉。
    if target.exists():
        for name in KEEP_IN_DATASET:
            src = target / name
            if not src.exists():
                continue
            dst = staging / name
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    # ---- 落盘：先记住每个文件的指纹，换上去再逐个核对 ----
    fingerprint = {
        p.relative_to(staging).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in staging.rglob("*")
        if p.is_file()
    }
    _swap(staging, target)
    OUT = target
    check(
        "换上去之后每个文件与换之前逐字节一致",
        all(hashlib.sha256((OUT / rel).read_bytes()).hexdigest() == sha for rel, sha in fingerprint.items()),
        f"{len(fingerprint)} 个文件",
        group="落盘",
    )

    out_files = sorted(p for p in OUT.rglob("*") if p.is_file())
    manifest = [
        {"path": p.relative_to(OUT).as_posix(), "bytes": p.stat().st_size,
         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in out_files
    ]
    n_files = len(out_files) + 1          # 报告自身也算一个产出文件
    check("文件清单与实际文件一一对应", [m["path"] for m in manifest] == [p.relative_to(OUT).as_posix() for p in out_files], f"{len(manifest)} 个", group="落盘")
    check("清单里每个文件都有 sha256", all(len(m["sha256"]) == 64 for m in manifest), group="落盘")

    passed = [c for c in CHECK if c[1]]
    failed = [c for c in CHECK if not c[1]]
    groups: dict[str, int] = {}
    for _name, _ok, _detail, _group in CHECK:
        groups[_group] = groups.get(_group, 0) + 1
    lines = ["# 校验报告", "",
             f"数据版本：`{build_id}`（生成时间 {index['generated_at']}，rule_set R1–R13）", "",
             f"断言 {len(CHECK)} 条：通过 {len(passed)}，失败 {len(failed)}", "",
             "## 分组",
             "",
             "| 分组 | 条数 | 换一批数据还成立吗 |",
             "|---|---|---|",
             f"| 结构 | {groups.get('结构', 0)} | 成立 |",
             f"| 算账 | {groups.get('算账', 0)} | 成立 |",
             f"| 参考数字 | {groups.get('参考数字', 0)} | 不成立，只在赛题那份模拟数据上跑 |",
             f"| 基准 | {groups.get('基准', 0)} | 不成立，同上 |",
             f"| 落盘 | {groups.get('落盘', 0)} | 成立 |",
             "",
             "（分组与条数由本脚本统计，文档不写死数字，避免对不上。）", "",
             "## 逐条", ""]
    lines.append("| 分组 | 检查项 | 结果 | 实测 |")
    lines.append("|---|---|---|---|")
    for name, ok, detail, group in CHECK:
        lines.append(f"| {group} | {name} | {'通过' if ok else '**失败**'} | {detail} |")
    lines.append("")
    lines.append(f"产出文件：{n_files} 个（含本报告）")
    report_text = "\n".join(lines) + "\n"
    (OUT / "校验报告.md").write_text(report_text, encoding="utf-8")

    if write_ledger:
        # 报告已经落在盘上，清单按磁盘实际内容算（含报告自身），避免"台账与磁盘两回事"
        disk_files = sorted(p for p in OUT.rglob("*") if p.is_file())
        manifest = [
            {"path": p.relative_to(OUT).as_posix(), "bytes": p.stat().st_size,
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in disk_files
        ]
        build_dir = ROOT / "data" / "builds" / build_id
        build_dir.mkdir(parents=True, exist_ok=True)
        DS.write_csv(build_dir / "文件清单.csv", manifest, H_MANIFEST)
        build_record = {
            "build_id": build_id,
            "generated_at": index["generated_at"],
            "dataset_dir": "dataset/",
            "data_source": str(data_dir),
            "assertion_mode": "参考数据（含 31 条基准）" if is_reference else "通用检查",
            "rule_set": index["rule_set"],
            "file_count": len(manifest),
            "total_bytes": sum(m["bytes"] for m in manifest),
            "assertions_passed": len(passed),
            "assertions_failed": len(failed),
            "assertion_groups": {k: v for k, v in sorted(groups.items())},
            "index_sha256": next(m["sha256"] for m in manifest if m["path"] == "index.json"),
            "汇总": {r["name"]: r["actual"] for r in baseline_rows},
            "说明": "这一份记的是本次生成的台账。dataset/ 永远是当前生效的那一份；"
                    "文件清单里的 sha256 用来核对“页面拿到的文件”是不是这一次生成的。",
        }
        DS.write_json(build_dir / "记录.json", build_record)

        # ---- 与上一版比：数字变了哪些、文件变了哪些，写成一页给人看的说明 ----
        previous = VS.latest_build(ROOT, exclude=build_id)
        change = VS.diff(previous, build_record, ROOT)
        note_path = VS.write_change_note(change, ROOT)
        removed = VS.prune(ROOT)      # 保留策略：目前一份都不删
        # 台账与磁盘核对（用刚写好的核对，不靠断言列表，避免自证）
        drift = [m["path"] for m in manifest
                 if hashlib.sha256((OUT / m["path"]).read_bytes()).hexdigest() != m["sha256"]]
        print(f"[台账] {build_id}：{len(manifest)} 个文件逐个核对 sha256，"
              + ("全部一致。" if not drift else f"有 {len(drift)} 个对不上：{drift[:3]}"))
        print(f"[台账] {change['from']} → {build_id}："
              f"数字变化 {len(change['numbers'])} 处，"
              f"文件 +{len(change['files']['added'])} / ~{len(change['files']['changed'])} / "
              f"-{len(change['files']['removed'])}"
              + (f"；清理旧版本 {len(removed)} 份" if removed else "；旧版本全部保留")
              + f"；变更说明 {note_path.name}")

    for name, ok, detail, group in CHECK:
        print(f"[{'PASS' if ok else 'FAIL'}] [{group}] {name} {detail}")
    location = f"台账 data/builds/{build_id}/" if write_ledger else "试跑，未写台账"
    print(f"共 {len(passed)} 条断言通过，{len(failed)} 条失败。数据版本 {build_id}，{location}。")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
