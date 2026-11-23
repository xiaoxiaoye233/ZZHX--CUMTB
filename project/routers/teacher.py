from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_db
from crud import teacher
from utils import file_tools
from utils.response import success_response

# 创建 APIRouter 实例
router = APIRouter(prefix="/api", tags=["teacher"])


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
    try:
        saved_path = file_tools.save_uploaded_bytes(content, file.filename or "", target_name)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if step == 1:
        return success_response(
            message=f"第 1 步完成：已替换保存为「{saved_path.name}」，请继续上传第 2 份文件「作答记录」。",
            data={"step": 1, "saved_file": saved_path.name},
        )

    # 第 2 步完成：运行 数据层/src/steps 中的全部 python 脚本
    scripts = file_tools.run_steps_scripts()

    # 脚本跑完后同步 00-04 数据和学生账号进 MySQL（如果 MySQL 正在运行）
    db_counts = None
    try:
        db_counts = await teacher.sync_dataset_to_db(db)
    except Exception:
        pass

    return success_response(
        message=f"全部导入完成：「{saved_path.name}」已保存，已运行脚本 {scripts} 并刷新数据。",
        data={"step": 2, "saved_file": saved_path.name, "scripts": scripts, "db_counts": db_counts},
    )


@router.get("/teacher/overview")
async def get_teacher_overview(db: AsyncSession = Depends(get_db)):
    # 获取教师首页与数据详情页数据：班级平均分、最低得分率主题、各学生各主题得分与总得分
    overview = await teacher.get_teacher_overview(db)
    return success_response(message="获取教师数据概览成功", data=overview)


@router.post("/sync-dataset")
async def sync_dataset_now(db: AsyncSession = Depends(get_db)):
    # 手动触发一次把 00-04 全部数据与学生账号同步到 MySQL
    counts = await teacher.sync_dataset_to_db(db)
    return success_response(message="同步 00-04 数据集到 MySQL 成功", data=counts)
