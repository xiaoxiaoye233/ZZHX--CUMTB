from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserLoginRequest(BaseModel):
    """
    登录请求参数模型
    """
    account: str = Field(..., description="登录账号")
    password: str = Field(..., description="登录密码")
    remember: bool = Field(False, description="是否记住密码")


class UserInfoResponse(BaseModel):
    """
    用户信息响应模型
    """
    id: int
    account: str
    role: str
    student_id: Optional[str] = None
    login_id: str | None = None

    # 模型类配置：允许从 ORM 对象属性中取值
    model_config = ConfigDict(
        from_attributes=True
    )
