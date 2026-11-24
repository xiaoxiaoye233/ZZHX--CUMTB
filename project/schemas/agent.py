from typing import Optional

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """
    Agent 对话请求参数模型（学生端 / 教师端共用）
    """
    role: str = Field(..., description="角色：student 或 teacher")
    message: str = Field(..., description="用户输入的问题")
    student_id: Optional[str] = Field(None, description="学生端必填学号，如 D01")
    session_id: str = Field("default", description="会话编号，用于区分多轮记忆")
