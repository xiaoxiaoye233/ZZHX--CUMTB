"""
学生端 LangChain 智能体模块：
功能 1：generate_student_advice(student_id)
    学生登录成功后，自动查数据库 -> 用 ChatPromptTemplate | ChatTongyi | StrOutputParser 生成个性化建议
功能 2：student_chat(student_id, message)
    学生多轮对话 -> 用 create_agent 结合「教材 RAG 检索工具 + 学生数据库工具 + 防御性提示词 + 本地 JSON 长期会话记忆」回答
"""
from langchain.agents import create_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.config.settings import PROMPTS_DIR
from agent.core.llm import get_chat_model
from agent.core.plain_text import ensure_plain_text
from agent.memory.file_history import (
    append_chat_messages,
    attach_last_assistant_ref,
    invoke_with_history,
    load_chat_history,
    student_session_key,
)
from agent.rag.textbook_locator import (
    begin_textbook_turn,
    finish_textbook_turn,
    resolve_best_textbook_ref,
)
from agent.tools.db_tools import (
    get_student_summary_text,
    query_student_scores,
    query_student_wrong_questions,
)
from agent.tools.rag_tools import search_textbook_knowledge


def load_prompt_text(filename: str) -> str:
    """从 agent/prompts/ 文件夹读取提示词文本"""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ==================== 长期会话历史读写（供路由和老师查看复用） ====================
def get_student_history(student_id: str) -> list[dict]:
    """读取某位同学保存在本地 JSON 文件里的完整长期对话记录"""
    session_key = student_session_key(student_id)
    return load_chat_history(session_key)


def save_student_login_advice(student_id: str, login_id: str, advice: str) -> dict:
    """把这次登录的建议追加到学生的本地长期会话。"""
    message = {
        "id": login_id,
        "role": "assistant",
        "content": advice,
        "tag": "Agent 老师 · 个性化建议",
    }
    append_chat_messages(student_session_key(student_id), [message])
    return message


# ==================== 功能 1：登录后生成个性化建议 ====================
def _generate_advice(student_id: str, prompt_filename: str) -> str:
    """把 MySQL 学情填入指定提示词，再用学生 Agent 的聊天模型生成建议。"""
    sid = student_id.strip().upper()

    # 1. 从 MySQL 查询这名同学的真实学情数据
    student_data = get_student_summary_text(sid)

    # 2. 读取提示词模板并组装最基础的 Chain
    template_text = load_prompt_text(prompt_filename)
    prompt = ChatPromptTemplate.from_template(template_text)
    model = get_chat_model()
    chain = prompt | model | StrOutputParser()

    # 3. 执行 Chain 生成个性化建议，并执行纯文本清洗
    advice = chain.invoke(
        {
            "student_id": sid,
            "student_data": student_data,
        }
    )
    return ensure_plain_text(advice)


def generate_student_advice(student_id: str) -> str:
    return _generate_advice(student_id, "student_advice.txt")


def generate_student_report_advice(student_id: str) -> str:
    return _generate_advice(student_id, "student_report_advice.txt")


# ==================== 功能 2：学生对话（教材 RAG + 数据库 + 防御性语言 + 长期会话记忆） ====================
def student_chat_with_ref(student_id: str, message: str) -> tuple[str, dict | None]:
    """学生对话并返回（纯文本回复, 最相关的教材文件及页码引用）。"""
    sid = student_id.strip().upper()
    user_text = message.strip()
    session_key = student_session_key(sid)

    system_prompt = load_prompt_text("student_chat.txt").replace("{student_id}", sid)

    agent = create_agent(
        model=get_chat_model(),
        tools=[
            search_textbook_knowledge,
            query_student_scores,
            query_student_wrong_questions,
        ],
        system_prompt=system_prompt,
    )

    begin_textbook_turn()
    try:
        reply = ensure_plain_text(invoke_with_history(agent, session_key, user_text, "Agent 老师"))
    finally:
        tool_refs = finish_textbook_turn()

    textbook_ref = resolve_best_textbook_ref(user_text, tool_refs, assistant_reply=reply)
    if textbook_ref:
        attach_last_assistant_ref(session_key, textbook_ref)
    return reply, textbook_ref


def student_chat(student_id: str, message: str) -> str:
    """
    经典 Agent 写法（P5 课程） + 长期会话记忆（P3 第 21 课）：
    create_agent + 3 个工具（查本人成绩、查本人错题、检索教材 PDF）+ 防御性系统提示词 + 本地 JSON 持久化历史
    """
    reply, _ = student_chat_with_ref(student_id, message)
    return reply
