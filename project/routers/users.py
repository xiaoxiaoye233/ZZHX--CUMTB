from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_db
from crud import users
from schemas.users import UserInfoResponse, UserLoginRequest
from utils.response import success_response

# 创建 APIRouter 实例
router = APIRouter(prefix="/api/auth", tags=["users"])


@router.post("/login")
async def login(user_data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    # 登录逻辑：验证账号是否存在 → 验证密码 → 响应结果（不需要注册）
    account = user_data.account.strip()
    password = user_data.password.strip()
    if not account or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入账号和密码")

    user = await users.authenticate_user(db, account, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误，请重新输入")

    response_data = UserInfoResponse.model_validate(user)
    return success_response(message="登录成功", data=response_data)
