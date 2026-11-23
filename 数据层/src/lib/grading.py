"""判分可靠性标注（口径卡 R8）。

只标注，**绝不改分**。官方得分是唯一的分数来源；本模块的作用是把"这条分数本身
可能不可靠"这件事显式记下来，写进数据集的 `04_质量与剔除/判分存疑.csv`。

五类取值与优先级（高 → 低）：
    得分超满分 > 答案一致但判0 > 总分与分项不符 > 已改判 > 正常

"已改判"一个大类里其实有两种情况，说明句要分开写：
    · 旧版本有分、后来改分    → "曾按 2 分记录，复核后改为 1 分"
    · 旧版本是待评分、后来补判 → "曾记为待评分，复核后补判为 3 分"
标签不细分（越细越难讲），但话必须说准。
"""
from __future__ import annotations

import re

import pandas as pd

from clean import parse_rubric_sum

NORMAL = "正常"
ZERO_MARKED = "答案一致但判0"
RUBRIC_MISMATCH = "总分与分项不符"
OVER_FULL = "得分超满分"
REGRADED = "已改判"

PRIORITY = {OVER_FULL: 4, ZERO_MARKED: 3, RUBRIC_MISMATCH: 2, REGRADED: 1, NORMAL: 0}

_TRANS = {
    "（": "(", "）": ")", "；": ";", "，": ",", "　": " ", "＝": "=",
    "＋": "+", "－": "-", "＞": ">", "＜": "<", "≤": "<=", "≥": ">=",
    "×": "*", "÷": "/",
}


def normalize_answer_text(text: str) -> str:
    """把答案压成"数学骨架"，用于判断两种写法是否等价。

    注意：**只用于判分可靠性检查，绝不能用于判分**（口径卡 R8 / 反例 6-1）。
    """
    s = str(text or "").strip()
    for k, v in _TRANS.items():
        s = s.replace(k, v)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(人|元|个|厘米|米|岁|分|件|本|天)$", "", s)
    s = re.sub(r"^x=", "", s)
    return s


def _fmt_score(value) -> str:
    """把旧版本的得分写成可读字符串：空值写'待评分'，2.0 写'2'。"""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "待评分"
    if pd.isna(f):
        return "待评分"
    return str(int(f)) if f == int(f) else str(f)


def _number_or_zero(value) -> int:
    """把单元格转成整数；空值/非数字一律 0。

    不能写 `int(pd.to_numeric(x) or 0)`：NaN 在 Python 里是 truthy，
    `NaN or 0` 还是 NaN，`int(NaN)` 会抛 ValueError。所以必须显式判 isna。
    """
    number = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(number) else int(number)


def flag_grading(ds, clean_result) -> pd.DataFrame:
    """返回 记录编号 / 学生编号 / 材料编号 / 判分可靠性 / 说明 五列。"""
    rec = clean_result.records_clean.copy()
    mat = ds.materials.set_index("材料编号")
    reference = mat["参考答案"].to_dict()

    regraded = {e["新记录编号"]: e for e in clean_result.multi_version_events
                if e.get("改分")}

    rows: list[dict] = []
    for _, r in rec.iterrows():
        rid = r["记录编号"]
        qid = r["材料编号"]
        score = _number_or_zero(r["得分"])
        full = _number_or_zero(r["满分"])
        answer = str(r["学生最终作答"] or "")
        n_answer = normalize_answer_text(answer)
        n_reference = normalize_answer_text(reference.get(qid, ""))
        rubric_sum = parse_rubric_sum(str(r.get("评分点得分", "")))

        flag, note = NORMAL, ""
        if score > full:
            flag = OVER_FULL
            note = f"得分 {score} 分超过满分 {full} 分，属录入异常"
        elif score == 0 and n_answer and n_answer == n_reference:
            flag = ZERO_MARKED
            note = "学生答案与参考答案一致，但该题得分为 0"
        elif rubric_sum is not None and rubric_sum != score:
            flag = RUBRIC_MISMATCH
            note = f"评分点合计 {rubric_sum} 分，总分记 {score} 分"
        elif rid in regraded:
            e = regraded[rid]
            flag = REGRADED
            old = _fmt_score(e["旧得分"])
            # 旧版本是待评分时属"复核后补判"，不是"改分"：措辞要分开，避免写出
            # "曾按 待评分 分记录"这种病句（2026-11-11 修）。
            if old == "待评分":
                note = (f"同一作答事件曾记为待评分（{e['旧记录编号']}），"
                        f"复核后补判为 {score} 分")
            else:
                note = (f"同一作答事件曾按 {old} 分记录（{e['旧记录编号']}），"
                        f"复核后改为 {score} 分")

        rows.append({
            "记录编号": rid,
            "学生编号": r["学生编号"],
            "材料编号": qid,
            "判分可靠性": flag,
            "说明": note,
        })

    return pd.DataFrame(rows)[["记录编号", "学生编号", "材料编号", "判分可靠性", "说明"]]


def grading_caveat_for(record_ids: list[str], flags: pd.DataFrame) -> str:
    """给调用方用：一批记录里若有判分存疑项，生成一句限定说明。"""
    if not record_ids:
        return ""
    sub = flags[flags["记录编号"].isin(record_ids) & (flags["判分可靠性"] != NORMAL)]
    if sub.empty:
        return ""
    parts = [f"{row['记录编号']}（{row['判分可靠性']}）" for _, row in sub.iterrows()]
    return ("以下记录的判分存在疑点，本结论仍按官方得分计算，仅供参考："
            + "；".join(parts))
