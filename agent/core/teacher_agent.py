"""
教师端 LangChain 智能体模块：
功能 3：teacher_chat(message, session_id)
    教师多轮对话 -> 用 create_agent 结合「查学生数据库 + 查班级数据库 + 查课标 PDF 知识库 + 查教材 + 本地 JSON 长期会话记忆」辅助授课
"""
from langchain.agents import create_agent

from agent.core.llm import get_chat_model
from agent.core.student_agent import load_prompt_text
from agent.memory.file_history import (
    invoke_with_history,
    load_chat_history,
    teacher_session_key,
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
def teacher_chat(message: str, session_id: str = "default") -> str:
    """
    经典 Agent 写法（P5 课程） + 长期会话记忆（P3 第 21 课）：
    create_agent + 5 个工具（查学生成绩、查学生错题、查班级整体学情、查课标要求、查教材内容）+ 本地 JSON 持久化历史
    """
    user_text = message.strip()
    session_key = teacher_session_key(session_id)

    # 1. 读取教师端系统提示词
    system_prompt = load_prompt_text("teacher_chat.txt")

    # 2. 创建教师教研助手 Agent
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

    return invoke_with_history(agent, session_key, user_text, "AI 教研助手")
