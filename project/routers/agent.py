import asyncio
from pathlib import Path
import sys
from typing import Annotated, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import StrictBool
from starlette import status

# 确保能导入同级的独立 agent 文件夹（D:\ZJHX--CUMTB\agent）
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from agent.core.student_agent import get_student_history, student_chat
from agent.core.teacher_agent import get_teacher_history, teacher_chat
from agent.rag.vector_store import load_pdfs_to_chroma
from schemas.agent import AgentChatRequest
from utils.print_access import require_print_teacher
from utils.print_settings import auto_print_enabled, save_auto_print
from utils.response import success_response

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/config")
def get_agent_config(request: Request):
    require_print_teacher(request)
    return success_response(message="获取自动打印设置成功", data={"auto_print": auto_print_enabled()})


@router.patch("/config")
def update_agent_config(request: Request, auto_print: Annotated[StrictBool, Body(embed=True)]):
    require_print_teacher(request)
    save_auto_print(auto_print)
    return success_response(message="自动打印设置已保存", data={"auto_print": auto_print})


@router.post("/chat")
async def chat_with_agent(payload: AgentChatRequest):
    # 对话路由：按 role 分流到学生 Agent 或教师 Agent（自动写入长期会话 JSON）
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入您的问题")

    if payload.role == "student":
        student_id = (payload.student_id or "D01").strip().upper()
        # 使用 asyncio.to_thread 在后台线程执行同步 LangChain 调用，不阻塞 FastAPI
        reply = await asyncio.to_thread(student_chat, student_id, user_message)
        return success_response(message="对话成功", data={"reply": reply, "role": "student"})

    if payload.role == "teacher":
        reply = await asyncio.to_thread(teacher_chat, user_message, payload.session_id)
        return success_response(message="对话成功", data={"reply": reply, "role": "teacher"})

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="role 参数只能是 student 或 teacher",
    )


@router.get("/history")
async def get_agent_chat_history(
    role: str = "teacher",
    student_id: Optional[str] = None,
    session_id: str = "default",
):
    # 获取长期会话历史记录（教师端打开路由加载自己的历史记录）
    if role == "teacher":
        history = get_teacher_history(session_id)
        return success_response(message="获取教师长期会话历史成功", data=history)

    if role == "student":
        sid = (student_id or "D01").strip().upper()
        history = get_student_history(sid)
        return success_response(message="获取学生长期会话历史成功", data=history)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="role 参数只能是 student 或 teacher",
    )


@router.post("/rebuild-rag")
async def rebuild_rag_knowledge_base():
    # 一键扫描 agent/knowledge_base/textbook 和 agent/knowledge_base/curriculum 里的新增 PDF 并向量化入 Chroma
    summary = await asyncio.to_thread(load_pdfs_to_chroma)
    return success_response(message="PDF 知识库向量化完成", data=summary)
