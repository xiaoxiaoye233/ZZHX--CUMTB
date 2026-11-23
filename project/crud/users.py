from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import STUDENTS_DATA_DIR
from models.users import User


# 根据账号查询用户
async def get_user_by_account(db: AsyncSession, account: str):
    query = select(User).where(User.account == account)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# 校验账号和密码
async def authenticate_user(db: AsyncSession, account: str, password: str):
    user = await get_user_by_account(db, account)
    if not user:
        return None
    if user.password != password:
        return None
    return user


# 根据 01_按学生 文件夹名称把学生账号和密码写入 users 表
async def sync_users_from_folders(db: AsyncSession):
    # 先查出数据库里已有的全部账号，避免重复写入
    query = select(User.account)
    result = await db.execute(query)
    existing_accounts = set(result.scalars().all())

    # 默认保留教师账号 123 / 123
    if "123" not in existing_accounts:
        db.add(User(account="123", password="123", role="teacher", student_id=None))
        existing_accounts.add("123")

    # 扫描 01_按学生 目录下的每个文件夹，文件夹名就是学生账号和密码（如 D01 / D01）
    if STUDENTS_DATA_DIR.exists():
        for folder in sorted(STUDENTS_DATA_DIR.iterdir()):
            if not folder.is_dir():
                continue
            sid = folder.name
            if sid not in existing_accounts:
                db.add(User(account=sid, password=sid, role="student", student_id=sid))
                existing_accounts.add(sid)

    await db.commit()
    return len(existing_accounts)
