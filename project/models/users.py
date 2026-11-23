from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """
    登录账号表 ORM 模型（教师账号 123 + 学生账号 D01~D40）
    """
    __tablename__ = "users"

    # 创建索引
    __table_args__ = (
        Index("uk_users_account", "account"),
        Index("idx_users_student_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    account: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="登录账号")
    password: Mapped[str] = mapped_column(String(128), nullable=False, comment="登录密码")
    role: Mapped[str] = mapped_column(String(20), default="student", nullable=False, comment="角色：student / teacher")
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="关联学号")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )

    def __repr__(self):
        return f"<User(id={self.id}, account='{self.account}', role='{self.role}')>"
