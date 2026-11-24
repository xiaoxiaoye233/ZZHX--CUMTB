import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Annotated
from uuid import UUID
from weakref import WeakValueDictionary

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import select
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
from config.db_conf import get_db, students_data_dir
from crud import student
from models.dataset import StudentProfile
from utils.file_tools import read_json_file
from utils.print_access import require_student_login
from utils.print_settings import auto_print_enabled
from utils.response import success_response
from utils.student_report import generate_and_print_report

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/students", tags=["student"])
_login_advice_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@router.post("/{student_id}/print-report")
async def print_student_report(
    student_id: str,
    visit_id: Annotated[UUID, Body(embed=True)],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not auto_print_enabled():
        return success_response(message="自动打印已关闭", data={"status": "disabled"})

    sid = student_id.strip().upper()
    require_student_login(request, sid, visit_id)
    rows = await student.get_student_overview_rows(db, sid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")

    profile = None
    try:
        profile = await db.scalar(select(StudentProfile).where(StudentProfile.student_id == sid))
    except Exception:
        if db.in_transaction():
            await db.rollback()
        student_json = read_json_file(students_data_dir / sid / f"{sid}.json")
        if isinstance(student_json, dict) and isinstance(student_json.get("student"), dict):
            profile = SimpleNamespace(**student_json["student"])

    result = await asyncio.to_thread(generate_and_print_report, sid, visit_id, profile, rows)
    return success_response(message="学情报告处理完成", data=result)


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
