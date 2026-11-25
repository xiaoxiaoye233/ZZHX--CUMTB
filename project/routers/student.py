import asyncio
from pathlib import Path
import sys
from typing import Annotated
from urllib.parse import quote
from uuid import UUID
from weakref import WeakValueDictionary

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

# 确保能导入同级的独立 agent 文件夹
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from agent.core.student_agent import (
    generate_student_advice,
    get_student_history,
    save_student_login_advice,
)
from config.db_conf import get_db
from crud import student
from utils.print_access import require_student_login
from utils.response import success_response
from utils.student_report import (
    render_student_report_bytes,
    resolve_student_report_advice,
)

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/students", tags=["student"])
_login_advice_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@router.get("/{student_id}/score-table")
async def get_student_score_table(student_id: str, db: AsyncSession = Depends(get_db)):
    # 获取某个学生的速览成绩表
    sid = student_id.strip().upper()
    rows = await student.get_student_overview_rows(db, sid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")
    return success_response(message="获取学生成绩表成功", data=rows)


@router.get("/{student_id}/tasks")
async def get_student_task_board(student_id: str, db: AsyncSession = Depends(get_db)):
    # 获取学生端「任务」面板数据：按知识点列出全部关联题及已做/未做状态
    sid = student_id.strip().upper()
    payload = await student.get_student_tasks(db, sid)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")
    return success_response(message="获取学生知识点任务成功", data=payload)


@router.get("/{student_id}/learning-report")
async def get_student_learning_report(
    student_id: str,
    include_advice: bool = True,
    db: AsyncSession = Depends(get_db),
):
    # 获取学情报告数据：学生端包含个性化建议，教师端从成绩单点入时可传 include_advice=false 跳过建议
    sid = student_id.strip().upper()
    payload = await student.get_student_learning_report(db, sid)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")
    payload["advice"] = (
        await asyncio.to_thread(resolve_student_report_advice, sid, payload)
        if include_advice
        else ""
    )
    return success_response(message="获取学生学情报告成功", data=payload)


@router.get("/{student_id}/learning-report/pdf")
async def download_student_learning_report_pdf(
    student_id: str,
    include_advice: bool = True,
    db: AsyncSession = Depends(get_db),
):
    # 直接生成并返回指定学生的学情报告 PDF 文件（支持 include_advice 控制是否输出个性化建议区块）
    sid = student_id.strip().upper()
    payload = await student.get_student_learning_report(db, sid)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")
    payload["include_advice"] = include_advice
    payload["advice"] = (
        await asyncio.to_thread(resolve_student_report_advice, sid, payload)
        if include_advice
        else ""
    )
    pdf_bytes = await asyncio.to_thread(render_student_report_bytes, payload)
    encoded_name = quote(f"学情报告_{sid}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"report_{sid}.pdf\"; filename*=UTF-8''{encoded_name}",
        },
    )


@router.post("/{student_id}/advice")
async def generate_login_advice(
    student_id: str,
    login_id: Annotated[UUID, Body(embed=True)],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    sid = student_id.strip().upper()
    require_student_login(request, sid, login_id)
    key = login_id.hex
    # 同一次登录的请求如果重试，复用已经保存的建议。
    lock = _login_advice_locks.setdefault(key, asyncio.Lock())
    async with lock:
        existing = next((msg for msg in get_student_history(sid) if msg.get("id") == key), None)
        if existing is not None:
            return success_response(message="已生成本次登录的建议", data=existing)

        rows = await student.get_student_overview_rows(db, sid)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")
        if db.in_transaction():
            await db.rollback()
        advice = await asyncio.to_thread(generate_student_advice, sid)
        if not advice:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="暂时无法生成个性化建议")
        message = save_student_login_advice(sid, key, advice)
    return success_response(message="生成个性化建议成功", data=message)


@router.get("/{student_id}/agent/history")
async def get_student_agent_history(student_id: str, db: AsyncSession = Depends(get_db)):
    # 获取某个学生的长期聊天记录（学生端打开页面 + 教师端 Agent 设置按学号查看均调用此接口）
    sid = student_id.strip().upper()
    rows = await student.get_student_overview_rows(db, sid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")

    history = get_student_history(sid)
    return success_response(message="获取学生长期会话历史成功", data=history)
