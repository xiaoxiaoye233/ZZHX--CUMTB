import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import sys
from typing import Annotated, Optional
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette import status

# 确保能导入同级的独立 agent 文件夹
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from agent.config.settings import TEXTBOOK_PDF_DIR
from agent.core.student_agent import get_student_history, student_chat_with_ref
from agent.core.teacher_agent import get_teacher_history, teacher_chat_with_ref
from agent.rag.vector_store import (
    get_file_md5,
    load_pdfs_to_chroma,
    remove_file_from_chroma,
)
from schemas.agent import AgentChatRequest
from utils.knowledge_graph import (
    load_knowledge_graph,
    reset_knowledge_graph,
    save_knowledge_graph,
)
from utils.print_access import require_teacher
from utils.response import success_response

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/agent", tags=["agent"])


def _ai_key_configured() -> bool:
    return bool(os.environ.get("DASHSCOPE_API_KEY", "").strip())


@router.post("/chat")
async def chat_with_agent(payload: AgentChatRequest, request: Request):
    # 对话路由：按 role 分流到学生 Agent 或教师 Agent（自动写入长期会话 JSON）
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入您的问题")

    if payload.role == "student":
        student_id = (payload.student_id or "D01").strip().upper()
        # 使用 asyncio.to_thread 在后台线程执行同步 LangChain 调用，不阻塞 FastAPI
        reply, textbook_ref = await asyncio.to_thread(
            student_chat_with_ref, student_id, user_message
        )
        return success_response(
            message="对话成功",
            data={"reply": reply, "role": "student", "textbook_ref": textbook_ref},
        )

    if payload.role == "teacher":
        require_teacher(request)
        if not _ai_key_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="请在项目根目录 .env 中设置 DASHSCOPE_API_KEY，然后重启后端。",
            )
        reply, textbook_ref = await asyncio.to_thread(
            teacher_chat_with_ref, user_message, payload.session_id
        )
        return success_response(
            message="对话成功",
            data={"reply": reply, "role": "teacher", "textbook_ref": textbook_ref},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="role 参数只能是 student 或 teacher",
    )


@router.get("/history")
async def get_agent_chat_history(
    request: Request,
    role: str = "teacher",
    student_id: Optional[str] = None,
    session_id: str = "default",
):
    # 获取长期会话历史记录（教师端打开路由加载自己的历史记录）
    if role == "teacher":
        require_teacher(request)
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


@router.post("/rebuild-rag", dependencies=[Depends(require_teacher)])
async def rebuild_rag_knowledge_base():
    # 一键扫描 agent/knowledge_base/textbook 和 agent/knowledge_base/curriculum 里的新增 PDF 并向量化入 Chroma
    summary = await asyncio.to_thread(load_pdfs_to_chroma)
    return success_response(message="PDF 知识库向量化完成", data=summary)


def _build_textbook_item(file_path: Path) -> dict:
    stat = file_path.stat()
    return {
        "name": file_path.name,
        "title": file_path.stem,
        "size": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "url": f"/api/agent/textbooks/{quote(file_path.name)}",
    }


logger = logging.getLogger(__name__)


async def _background_rebuild_rag() -> None:
    try:
        await asyncio.to_thread(load_pdfs_to_chroma)
    except Exception:
        logger.warning("后台自动向量化教材知识库失败", exc_info=True)


@router.get("/textbooks")
def list_textbooks():
    TEXTBOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for file_path in sorted(TEXTBOOK_PDF_DIR.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.name.startswith(".") or file_path.name.startswith("请把"):
            continue
        if file_path.suffix.lower() not in (".pdf", ".txt"):
            continue
        items.append(_build_textbook_item(file_path))
    return success_response(message="获取教材列表成功", data=items)


@router.get("/textbooks/{filename}")
def preview_textbook(filename: str):
    TEXTBOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
    base_dir = TEXTBOOK_PDF_DIR.resolve()
    safe_name = Path(filename).name
    target = (base_dir / safe_name).resolve()
    if target.parent != base_dir or not target.is_file() or target.suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定教材文件")
    media_type = "application/pdf" if target.suffix.lower() == ".pdf" else "text/plain; charset=utf-8"
    return FileResponse(
        path=str(target),
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


@router.post("/textbooks", dependencies=[Depends(require_teacher)])
async def upload_textbook(file: UploadFile = File(...)):
    raw_name = Path(file.filename or "").name.strip()
    if not raw_name or Path(raw_name).suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 PDF 或 TXT 格式的教材文件")

    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw_name)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传的教材文件为空")

    TEXTBOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
    target_path = TEXTBOOK_PDF_DIR / safe_name
    if target_path.is_file():
        old_md5 = get_file_md5(target_path)
        await asyncio.to_thread(remove_file_from_chroma, safe_name, old_md5)
    target_path.write_bytes(content)

    asyncio.create_task(_background_rebuild_rag())
    return success_response(
        message=f"文件「{safe_name}」已添加",
        data=_build_textbook_item(target_path),
    )


@router.delete("/textbooks/{filename}", dependencies=[Depends(require_teacher)])
async def delete_textbook(filename: str):
    TEXTBOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
    base_dir = TEXTBOOK_PDF_DIR.resolve()
    safe_name = Path(filename).name
    target = (base_dir / safe_name).resolve()
    if target.parent != base_dir or not target.is_file() or target.suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到要删除的教材文件")

    old_md5 = get_file_md5(target)
    target.unlink()
    await asyncio.to_thread(remove_file_from_chroma, safe_name, old_md5)
    return success_response(message=f"文件「{safe_name}」已删除", data={"name": safe_name})


@router.get("/knowledge-graph")
def get_knowledge_graph():
    return success_response(message="获取知识图谱成功", data=load_knowledge_graph())


@router.put("/knowledge-graph", dependencies=[Depends(require_teacher)])
def update_knowledge_graph(payload: Annotated[dict, Body()]):
    try:
        saved = save_knowledge_graph(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_response(message="知识图谱已保存", data=saved)


@router.post("/knowledge-graph/reset", dependencies=[Depends(require_teacher)])
def restore_default_knowledge_graph():
    restored = reset_knowledge_graph()
    return success_response(message="已恢复初始知识图谱", data=restored)
