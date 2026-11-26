"""课标条目与前置关系（content_map）。

这里只放两样数据，别的都不放：

1. `CURRICULUM_CITATIONS`：9 个指标各自引用课标的哪几条，以及**条目的完整原文**。
   数据集里 `curriculum_scope` 一列只写编号（`CR01 ①②③⑤ P62/55`），原文放在
   `dataset/00_字典/课标原文.json` 与 `.csv` 里，两边编号一一对应。
2. `PREREQUISITE_EDGES`：9 条前置关系。**数据表里没有这个字段**，是按教材章节顺序
   归纳的，属教学解释，不是数据结论。

三条来源纪律：
- 原文**逐字照抄**，只去掉句末标点；摘句用的哪半句写在 `used_part` 里，不做改写。
- 页码双写：`file_page` 是 PDF 文件页，`body_page` 是书上印的页码（课标 PDF 第 62 页印 55）。
- 课标原件是扫描件（无文字层），文字由页面图像逐条转录，两页截图在
  `dataset/05_出处截图/kb_p62.png`、`kb_p63.png`，可逐条核对。
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# 课标原文：三段小节的全部条目，一字不改（只去句末标点）
# 键 = 小节识别号；value = dict(小节标题链, 文件页, 正文页, 条目列表)
# 条目 = (编号, 原文, 用于哪些指标)  —— 「用于哪些指标」为空表示本轮没有指标引用它
# --------------------------------------------------------------------------

CURRICULUM_SECTION_TEXT: dict[str, dict] = {
    "CR01": dict(
        group="CR01",
        theme_id="T01",
        heading_path="四、课程内容 → （3）代数式",
        section_heading="（3）代数式",
        file_pages=[62, 63],
        body_pages=[55, 56],
        note="①②③④⑤⑥⑦ 在文件第 62 页（印 55），⑧⑨ 接在文件第 63 页（印 56）开头。",
        items=[
            ("①", "借助现实情境了解代数式，进一步理解用字母表示数的意义。", ["T01I3"]),
            ("②", "能分析具体问题中的简单数量关系，并用代数式表示；能根据特定的问题查阅资料，找到所需的公式。", ["T01I1", "T01I3"]),
            ("③", "会把具体数代入代数式进行计算。", ["T01I1"]),
            ("④", "了解整数指数幂的意义和基本性质；会用科学记数法表示数（包括在计算器上表示）。", []),
            ("⑤", "理解整式的概念，掌握合并同类项和去括号的法则；能进行简单的整式加减运算，能进行简单的整式乘法运算（多项式乘法仅限于一次式之间和一次式与二次式的乘法）。", ["T01I2"]),
            ("⑥", "理解乘法公式 (a+b)(a−b)=a²−b²，(a±b)²=a²±2ab+b²，了解公式的几何背景，能利用公式进行简单的计算和推理。", []),
            ("⑦", "能用提公因式法、公式法（直接利用公式不超过二次）进行因式分解（指数是正整数）。", []),
            ("⑧", "了解分式和最简分式的概念，能利用分式的基本性质进行约分和通分；能对简单的分式进行加、减、乘、除运算。", []),
            ("⑨", "了解代数推理（例 66）。", []),
        ],
    ),
    "CR02": dict(
        group="CR02",
        theme_id="T02",
        heading_path="四、课程内容 → 2. 方程与不等式 → （1）方程与方程组",
        section_heading="（1）方程与方程组",
        file_pages=[63],
        body_pages=[56],
        note="「2. 方程与不等式」是这一页的大标题，「（1）方程与方程组」是它下一级小节。",
        items=[
            ("①", "能根据现实情境理解方程的意义，能针对具体问题列出方程；理解方程解的意义，经历估计方程解的过程。", ["T02I3"]),
            ("②", "掌握等式的基本性质；能解一元一次方程和可化为一元一次方程的分式方程。", ["T02I1"]),
            ("③", "掌握消元法，能解二元一次方程组。", ["T02I2"]),
            ("④", "* 能解简单的三元一次方程组[1]。", []),
            ("⑤", "理解配方法，能用配方法、公式法、因式分解法解数字系数的一元二次方程。", []),
            ("⑥", "会用一元二次方程根的判别式判别方程是否有实根及两个实根是否相等。", []),
            ("⑦", "了解一元二次方程的根与系数的关系（例 67）。", []),
            ("⑧", "能根据具体问题的实际意义，检验方程解的合理性。", ["T02I3"]),
        ],
    ),
    "CR03": dict(
        group="CR03",
        theme_id="T03",
        heading_path="四、课程内容 → 2. 方程与不等式 → （2）不等式与不等式组",
        section_heading="（2）不等式与不等式组",
        file_pages=[63],
        body_pages=[56],
        note="与「（1）方程与方程组」同页；" "脚注：标有 * 的内容为选学内容，不作为考试要求。",
        items=[
            ("①", "结合具体问题，了解不等式的意义，探索不等式的基本性质。", ["T03I1"]),
            ("②", "能解数字系数的一元一次不等式，并能在数轴上表示出解集；会用数轴确定两个一元一次不等式组成的不等式组的解集。", ["T03I1", "T03I2"]),
            ("③", "能根据具体问题中的数量关系，列出一元一次不等式，解决简单的问题。", ["T03I3"]),
        ],
    ),
}

# --------------------------------------------------------------------------
# 指标 → 引用条目。原文一律取上面的全文；`used_part` 写清这个指标用的是哪半句。
# --------------------------------------------------------------------------

CURRICULUM_CITATIONS: dict[str, list[dict]] = {
    "T01I1": [
        dict(
            citation_identifier="CR01-②",
            group="CR01",
            item_label="②",
            heading_path="四、课程内容 → （3）代数式",
            section_heading="（3）代数式",
            used_part="前半句：能分析具体问题中的简单数量关系，并用代数式表示",
            file_page=62,
            body_page=55,
        ),
        dict(
            citation_identifier="CR01-③",
            group="CR01",
            item_label="③",
            heading_path="四、课程内容 → （3）代数式",
            section_heading="（3）代数式",
            used_part="整条",
            file_page=62,
            body_page=55,
        ),
    ],
    "T01I2": [
        dict(
            citation_identifier="CR01-⑤",
            group="CR01",
            item_label="⑤",
            heading_path="四、课程内容 → （3）代数式",
            section_heading="（3）代数式",
            used_part="前半句：理解整式的概念，掌握合并同类项和去括号的法则；能进行简单的整式加减运算",
            file_page=62,
            body_page=55,
        )
    ],
    "T01I3": [
        dict(
            citation_identifier="CR01-①",
            group="CR01",
            item_label="①",
            heading_path="四、课程内容 → （3）代数式",
            section_heading="（3）代数式",
            used_part="整条",
            file_page=62,
            body_page=55,
        ),
        dict(
            citation_identifier="CR01-②",
            group="CR01",
            item_label="②",
            heading_path="四、课程内容 → （3）代数式",
            section_heading="（3）代数式",
            used_part="前半句：能分析具体问题中的简单数量关系，并用代数式表示",
            file_page=62,
            body_page=55,
        ),
    ],
    "T02I1": [
        dict(
            citation_identifier="CR02-②",
            group="CR02",
            item_label="②",
            heading_path="四、课程内容 → 2. 方程与不等式 → （1）方程与方程组",
            section_heading="（1）方程与方程组",
            used_part="前半句：掌握等式的基本性质；能解一元一次方程",
            file_page=63,
            body_page=56,
        )
    ],
    "T02I2": [
        dict(
            citation_identifier="CR02-③",
            group="CR02",
            item_label="③",
            heading_path="四、课程内容 → 2. 方程与不等式 → （1）方程与方程组",
            section_heading="（1）方程与方程组",
            used_part="整条",
            file_page=63,
            body_page=56,
        )
    ],
    "T02I3": [
        dict(
            citation_identifier="CR02-①",
            group="CR02",
            item_label="①",
            heading_path="四、课程内容 → 2. 方程与不等式 → （1）方程与方程组",
            section_heading="（1）方程与方程组",
            used_part="前半句：能根据现实情境理解方程的意义，能针对具体问题列出方程",
            file_page=63,
            body_page=56,
        ),
        dict(
            citation_identifier="CR02-⑧",
            group="CR02",
            item_label="⑧",
            heading_path="四、课程内容 → 2. 方程与不等式 → （1）方程与方程组",
            section_heading="（1）方程与方程组",
            used_part="整条",
            file_page=63,
            body_page=56,
        ),
    ],
    "T03I1": [
        dict(
            citation_identifier="CR03-①",
            group="CR03",
            item_label="①",
            heading_path="四、课程内容 → 2. 方程与不等式 → （2）不等式与不等式组",
            section_heading="（2）不等式与不等式组",
            used_part="整条",
            file_page=63,
            body_page=56,
        ),
        dict(
            citation_identifier="CR03-②",
            group="CR03",
            item_label="②",
            heading_path="四、课程内容 → 2. 方程与不等式 → （2）不等式与不等式组",
            section_heading="（2）不等式与不等式组",
            used_part="前半句：能解数字系数的一元一次不等式，并能在数轴上表示出解集",
            file_page=63,
            body_page=56,
        ),
    ],
    "T03I2": [
        dict(
            citation_identifier="CR03-②",
            group="CR03",
            item_label="②",
            heading_path="四、课程内容 → 2. 方程与不等式 → （2）不等式与不等式组",
            section_heading="（2）不等式与不等式组",
            used_part="后半句：会用数轴确定两个一元一次不等式组成的不等式组的解集（与 T03I1 同一条原文）",
            file_page=63,
            body_page=56,
        )
    ],
    "T03I3": [
        dict(
            citation_identifier="CR03-③",
            group="CR03",
            item_label="③",
            heading_path="四、课程内容 → 2. 方程与不等式 → （2）不等式与不等式组",
            section_heading="（2）不等式与不等式组",
            used_part="整条",
            file_page=63,
            body_page=56,
        )
    ],
}

# 前置关系：数据里没有这个字段，按教材章节顺序归纳，属教学解释（Agent 用的时候要说明这一点）。
PREREQUISITE_EDGES = [
    dict(
        from_indicator="T01I1",
        to_indicator="T01I2",
        relation_type="同主题递进",
        rationale_text="合并同类项、去括号的对象是「项」，先能看懂代数式里有哪些项，谈不上去括号与合并。",
    ),
    dict(
        from_indicator="T01I1",
        to_indicator="T01I3",
        relation_type="同主题递进",
        rationale_text="不会把数量关系写成代数式，就写不出整式，T01I3 的「用整式解释」无从下手。",
    ),
    dict(
        from_indicator="T01I2",
        to_indicator="T01I3",
        relation_type="同主题递进",
        rationale_text="T01I3 的作答往往要先化简再解释，去括号与合并同类项错一处，解释就跟着错。",
    ),
    dict(
        from_indicator="T01I2",
        to_indicator="T02I1",
        relation_type="跨主题支撑",
        rationale_text="解一元一次方程的移项、合并同类项直接复用整式加减，符号处理不过关会在这里重现。",
    ),
    dict(
        from_indicator="T02I1",
        to_indicator="T02I2",
        relation_type="同主题递进",
        rationale_text="消元只是把二元化为一元，化完仍要按 T02I1 的方法解一元一次方程。",
    ),
    dict(
        from_indicator="T02I1",
        to_indicator="T02I3",
        relation_type="同主题递进",
        rationale_text="列方程解应用题的两端是「建模」和「解方程」，缺后者则列对也算错。",
    ),
    dict(
        from_indicator="T02I1",
        to_indicator="T03I1",
        relation_type="跨主题支撑",
        rationale_text="解不等式的步骤与解一元一次方程一一对应，差别只在乘除负数时不等号反向；不会解方程就谈不上「注意反向」。",
    ),
    dict(
        from_indicator="T03I1",
        to_indicator="T03I2",
        relation_type="同主题递进",
        rationale_text="求不等式组的解集，前提是能分别解出每个不等式；单个解错，交集必错。",
    ),
    dict(
        from_indicator="T03I1",
        to_indicator="T03I3",
        relation_type="同主题递进",
        rationale_text="列出不等式后必须能解出来并解释取值范围，否则建议停在「列出」这一步。",
    ),
]


def quote_of(item_label: str, group: str) -> str:
    """按 (小节, 条目编号) 取出课标原文全文。"""
    for item, text, _used in CURRICULUM_SECTION_TEXT[group]["items"]:
        if item == item_label:
            return text
    raise KeyError(f"{group} 里没有条目 {item_label}")
