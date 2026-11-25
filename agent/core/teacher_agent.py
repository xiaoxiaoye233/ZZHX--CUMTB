"""
教师端 LangChain 智能体模块：
功能 3：teacher_chat(message, session_id)
    教师多轮对话 -> 用 create_agent 结合「查学生数据库 + 查班级数据库 + 查课标 PDF 知识库 + 查教材 + 本地 JSON 长期会话记忆」辅助授课
"""
from langchain.agents import create_agent

from agent.core.llm import get_chat_model
from agent.core.plain_text import ensure_plain_text
from agent.core.student_agent import load_prompt_text
from agent.memory.file_history import (
    attach_last_assistant_ref,
    invoke_with_history,
    load_chat_history,
    teacher_session_key,
)
from agent.rag.textbook_locator import (
    begin_textbook_turn,
    finish_textbook_turn,
    resolve_best_textbook_ref,
)
from agent.tools.db_tools import (
    query_class_analysis,
    query_student_scores,
    query_student_wrong_questions,
)
from agent.tools.rag_tools import search_curriculum_standard, search_textbook_knowledge


def get_teacher_history(session_id: str = "default") -> list[dict]:
    """读取教师保存在本地 JSON 文件里的完整长期对话记录"""
    session_key = teacher_session_key(session_id)
    return load_chat_history(session_key)


# ==================== 功能 3：教师对话（查学生/班级数据库 + 查课标授课 + 长期会话记忆） ====================
def teacher_chat_with_ref(message: str, session_id: str = "default") -> tuple[str, dict | None]:
    """教师对话并返回（纯文本回复, 最相关的教材文件及页码引用）。"""
    user_text = message.strip()
    session_key = teacher_session_key(session_id)

    system_prompt = load_prompt_text("teacher_chat.txt")

    agent = create_agent(
        model=get_chat_model(),
        tools=[
            query_class_analysis,
            query_student_scores,
            query_student_wrong_questions,
            search_curriculum_standard,
            search_textbook_knowledge,
        ],
        system_prompt=system_prompt,
    )

    begin_textbook_turn()
    try:
        reply = ensure_plain_text(invoke_with_history(agent, session_key, user_text, "AI 教研助手"))
    finally:
        tool_refs = finish_textbook_turn()

    textbook_ref = resolve_best_textbook_ref(user_text, tool_refs, assistant_reply=reply)
    if textbook_ref:
        attach_last_assistant_ref(session_key, textbook_ref)
    return reply, textbook_ref


def teacher_chat(message: str, session_id: str = "default") -> str:
    """
    经典 Agent 写法（P5 课程） + 长期会话记忆（P3 第 21 课）：
    create_agent + 5 个工具（查学生成绩、查学生错题、查班级整体学情、查课标要求、查教材内容）+ 本地 JSON 持久化历史
    """
    reply, _ = teacher_chat_with_ref(message, session_id)
    return reply
