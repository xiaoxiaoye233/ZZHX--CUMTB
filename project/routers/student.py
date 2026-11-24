import asyncio
from pathlib import Path
import sys
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

# 确保能导入同级的独立 agent 文件夹（D:\ZJHX--CUMTB\agent）
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from agent.core.student_agent import (
    generate_student_advice,
    get_student_history,
    save_student_opening_advice,
)
from config.db_conf import get_db
from crud import student
from models.dataset import StudentProfile
from utils.print_access import require_print_student
from utils.print_settings import auto_print_enabled
from utils.response import success_response
from utils.student_report import generate_and_print_report

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/students", tags=["student"])


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
    require_print_student(request, sid)
    rows = await student.get_student_overview_rows_from_db(db, sid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")
    profile = await db.scalar(select(StudentProfile).where(StudentProfile.student_id == sid))
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


@router.get("/{student_id}/advice")
async def get_student_advice(student_id: str, db: AsyncSession = Depends(get_db)):
    # 首次进入学生路由时：自动查数据库并调用 LangChain 大模型生成个性化建议，并写入长期会话首条记录
    sid = student_id.strip().upper()
    rows = await student.get_student_overview_rows_from_db(db, sid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")

    advice = await asyncio.to_thread(generate_student_advice, sid)

    # 把首次生成的个性化建议保存到该同学的长期会话记录中
    save_student_opening_advice(sid, advice)
    return success_response(message="生成个性化建议成功", data=advice)


@router.get("/{student_id}/agent/history")
async def get_student_agent_history(student_id: str, db: AsyncSession = Depends(get_db)):
    # 获取某个学生的长期聊天记录（学生端打开页面 + 教师端 Agent 设置按学号查看均调用此接口）
    sid = student_id.strip().upper()
    rows = await student.get_student_overview_rows(db, sid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {sid} 的数据")

    history = get_student_history(sid)
    return success_response(message="获取学生长期会话历史成功", data=history)
