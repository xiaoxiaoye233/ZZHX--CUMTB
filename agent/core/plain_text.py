"""纯文本清洗护栏：确保 Agent 回复不含任何 Markdown 标记或 LaTeX 公式语法。"""
import re

_LATEX_SYMBOL_MAP = (
    (r"\\times\b", "×"),
    (r"\\div\b", "÷"),
    (r"\\cdot\b", "·"),
    (r"\\pm\b", "±"),
    (r"\\mp\b", "∓"),
    (r"\\leq?\b", "≤"),
    (r"\\geq?\b", "≥"),
    (r"\\neq?\b", "≠"),
    (r"\\approx\b", "≈"),
    (r"\\equiv\b", "≡"),
    (r"\\infty\b", "∞"),
    (r"\\pi\b", "π"),
    (r"\\because\b", "∵"),
    (r"\\therefore\b", "∴"),
    (r"\\triangle\b", "△"),
    (r"\\angle\b", "∠"),
    (r"\\perp\b", "⊥"),
    (r"\\parallel\b", "∥"),
    (r"\\degree\b", "°"),
    (r"\\circ\b", "°"),
    (r"\\to\b", "→"),
    (r"\\rightarrow\b", "→"),
    (r"\\Rightarrow\b", "⇒"),
    (r"\\left\b", ""),
    (r"\\right\b", ""),
    (r"\\,", " "),
    (r"\\;", " "),
    (r"\\quad\b", " "),
    (r"\\qquad\b", " "),
)


def _wrap_frac_part(part: str) -> str:
    clean = part.strip()
    if re.fullmatch(r"[A-Za-z0-9.]+", clean):
        return clean
    return f"({clean})"


def _replace_frac(text: str) -> str:
    pattern = re.compile(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
    for _ in range(6):
        new_text, count = pattern.subn(
            lambda m: f"{_wrap_frac_part(m.group(1))}/{_wrap_frac_part(m.group(2))}",
            text,
        )
        text = new_text
        if count == 0:
            break
    return text


def _replace_sqrt(text: str) -> str:
    text = re.sub(r"\\sqrt\s*\[([^\[\]]+)\]\s*\{([^{}]*)\}", r"\1√(\2)", text)
    pattern = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
    for _ in range(4):
        new_text, count = pattern.subn(r"√(\1)", text)
        text = new_text
        if count == 0:
            break
    return text


_INTERNAL_TOOL_REPLACEMENTS = (
    (r"调用\s*search_textbook_knowledge\s*(?:工具|函数)?", "查阅教材资料"),
    (r"调用\s*search_curriculum_standard\s*(?:工具|函数)?", "查阅课程标准"),
    (r"调用\s*query_class_analysis\s*(?:工具|函数)?", "查询班级学情"),
    (r"调用\s*query_student_scores\s*(?:工具|函数)?", "查询学生成绩"),
    (r"调用\s*query_student_wrong_questions\s*(?:工具|函数)?", "查询学生错题"),
    (r"\bsearch_textbook_knowledge\s*(?:工具|函数)?", "教材资料检索"),
    (r"\bsearch_curriculum_standard\s*(?:工具|函数)?", "课程标准检索"),
    (r"\bquery_class_analysis\s*(?:工具|函数)?", "班级学情查询"),
    (r"\bquery_student_scores\s*(?:工具|函数)?", "学生成绩查询"),
    (r"\bquery_student_wrong_questions\s*(?:工具|函数)?", "学生错题查询"),
)


def ensure_plain_text(raw: str) -> str:
    """移除残留的 Markdown、LaTeX 语法以及内部工具名称，转为干净自然的纯文本。"""
    text = str(raw or "").strip()
    if not text:
        return ""

    # 1. 移除代码块围栏与行内反引号
    text = re.sub(r"```[a-zA-Z0-9_-]*\n?([\s\S]*?)```", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)

    # 1.5 过滤任何意外泄露的内部工具函数名
    for pat, repl in _INTERNAL_TOOL_REPLACEMENTS:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # 2. 移除 LaTeX 公式定界符 $$...$$, \[...\], \(...\), $...$
    text = re.sub(r"\$\$([\s\S]*?)\$\$", r"\1", text)
    text = re.sub(r"\\\[([\s\S]*?)\\\]", r"\1", text)
    text = re.sub(r"\\\(([\s\S]*?)\\\)", r"\1", text)
    text = re.sub(r"(?<!\d)\$([^\$\n]+?)\$(?!\d)", r"\1", text)

    # 3. 展开常见 LaTeX 结构（分式、根号、文本包裹、上下标花括号、常用符号）
    text = _replace_frac(text)
    text = _replace_sqrt(text)
    text = re.sub(r"\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", text)
    text = re.sub(r"_\{([^{}]+)\}", r"_\1", text)
    for pat, repl in _LATEX_SYMBOL_MAP:
        text = re.sub(pat, repl, text)
    text = re.sub(r"\\(?:begin|end)\{[^{}]*\}", "", text)

    # 4. 移除 Markdown 链接、图片、粗体、斜体
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"(?<![A-Za-z0-9*])\*([^*\n]+)\*(?![A-Za-z0-9*])", r"\1", text)

    # 5. 逐行清理标题井号、引用尖括号、无序列表横杠/星号以及水平分割线
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"[-*_]{3,}", stripped):
            continue
        line = re.sub(r"^\s*#{1,6}\s+", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"^(\s*)[-*+]\s+", r"\1", line)
        cleaned_lines.append(line.rstrip())

    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
