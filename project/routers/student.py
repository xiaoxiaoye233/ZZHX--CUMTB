from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_db
from crud import student
from utils.response import success_response

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/students", tags=["student"])

# 接口实现流程
# 1. 模块化路由
# 2. 定义模型类（models/dataset.py）
# 3. 在 crud/student.py 封装查询方法
# 4. 在路由函数里调用 crud，返回 success_response


@router.get("/{student_id}/score-table")
async def get_student_score_table(student_id: str, db: AsyncSession = Depends(get_db)):
    # 获取某个学生的速览成绩表
    rows = await student.get_student_overview_rows(db, student_id.strip())
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {student_id} 的数据")
    return success_response(message="获取学生成绩表成功", data=rows)


@router.get("/{student_id}/advice")
async def get_student_advice(student_id: str, db: AsyncSession = Depends(get_db)):
    # 进入学生路由时自动生成个性化建议
    rows = await student.get_student_overview_rows(db, student_id.strip())
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到学号 {student_id} 的数据")
    advice = student.build_student_advice(student_id.strip(), rows)
    return success_response(message="生成个性化建议成功", data=advice)
