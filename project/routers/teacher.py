import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_db
from crud import teacher
from utils import file_tools
from utils.print_access import require_teacher
from utils.response import success_response

# 创建 APIRouter 实例
router = APIRouter(prefix="/api", tags=["teacher"], dependencies=[Depends(require_teacher)])
_dataset_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


async def _sync_dataset(db: AsyncSession) -> dict:
    try:
        return await teacher.sync_dataset_to_db(db)
    except SQLAlchemyError as exc:
        logger.exception("MySQL 学情数据同步失败")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MySQL 同步失败，请检查数据库后重试。",
        ) from exc


@router.post("/teacher/upload")
async def upload_teacher_file(
    step: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # 两步上传逻辑：
    # step=1：替换保存为 模拟学生.<后缀> → 返回提示让老师继续传第 2 份
    # step=2：替换保存为 作答记录.<后缀> → 运行 steps 下的 python 脚本 → 同步 00-04 到 MySQL
    if step not in (1, 2):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="step 参数只能是 1 或 2")

    target_name = "模拟学生" if step == 1 else "作答记录"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传的文件为空。")

    async with _dataset_lock:
        try:
            saved_path = await asyncio.to_thread(
                file_tools.save_uploaded_bytes, content, file.filename or "", target_name,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if step == 2:
            scripts = await asyncio.to_thread(file_tools.run_steps_scripts)
            db_counts = await _sync_dataset(db)

    if step == 1:
        return success_response(
            message=f"第 1 步完成：已替换保存为「{saved_path.name}」，请继续上传第 2 份文件「作答记录」。",
            data={"step": 1, "saved_file": saved_path.name},
        )

    return success_response(
        message=f"全部导入完成：「{saved_path.name}」已保存，已运行脚本 {scripts} 并刷新数据。",
        data={"step": 2, "saved_file": saved_path.name, "scripts": scripts, "db_counts": db_counts},
    )


@router.get("/teacher/overview")
async def get_teacher_overview(db: AsyncSession = Depends(get_db)):
    # 获取教师首页与数据详情页数据：班级平均分、最低得分率主题、各学生各主题得分与总得分
    overview = await teacher.get_teacher_overview(db)
    return success_response(message="获取教师数据概览成功", data=overview)


@router.get("/teacher/report-card")
async def get_class_report_card(
    class_id: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    db: AsyncSession = Depends(get_db),
):
    report = await teacher.get_class_report_card(db, class_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该班级")
    return success_response(message="获取班级成绩单成功", data=report)


@router.get("/teacher/tasks")
async def get_teacher_task_board(db: AsyncSession = Depends(get_db)):
    # 获取教师端「任务」面板数据：支持切换班级查看各知识点的学生平均得分率
    tasks = await teacher.get_teacher_tasks(db)
    return success_response(message="获取教师知识点任务概览成功", data=tasks)


@router.post("/sync-dataset")
async def sync_dataset_now(db: AsyncSession = Depends(get_db)):
    # 手动触发一次把 00-04 全部数据与学生账号同步到 MySQL
    async with _dataset_lock:
        counts = await _sync_dataset(db)
    return success_response(message="同步 00-04 数据集到 MySQL 成功", data=counts)
