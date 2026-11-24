from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import students_data_dir
from models.users import User


def _authenticate_local_fallback(account: str, password: str):
    """当 MySQL 未启动时，使用本地预设与 01_按学生 目录核验账号密码。"""
    if account == "123" and password == "123":
        return SimpleNamespace(id=1, account="123", role="teacher", student_id=None)
    if account == "456" and password == "456":
        return SimpleNamespace(id=2, account="456", role="student", student_id="D01")

    upper_acc = account.upper()
    upper_pwd = password.upper()
    if upper_acc == upper_pwd and (students_data_dir / upper_acc).is_dir():
        return SimpleNamespace(
            id=100,
            account=upper_acc,
            role="student",
            student_id=upper_acc,
        )
    return None


# 根据账号查询用户
async def get_user_by_account(db: AsyncSession, account: str):
    query = select(User).where(User.account == account)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if user is None and account.upper() != account:
        query_upper = select(User).where(User.account == account.upper())
        user = (await db.execute(query_upper)).scalar_one_or_none()
    return user


# 校验账号和密码（优先查 MySQL，MySQL 未启动时自动使用本地目录兜底）
async def authenticate_user(db: AsyncSession, account: str, password: str):
    try:
        user = await get_user_by_account(db, account)
        if user:
            if user.password == password or (
                user.role == "student" and user.password.upper() == password.upper()
            ):
                return user
            return None
        # 若库里尚未写入演示账号 456，兼容 456/456 登录为 D01
        if account == "456" and password == "456":
            return SimpleNamespace(id=2, account="456", role="student", student_id="D01")
        return None
    except Exception:
        if db.in_transaction():
            await db.rollback()
        return _authenticate_local_fallback(account, password)


# 根据 01_按学生 文件夹名称把学生账号和密码写入 users 表
async def sync_users_from_folders(db: AsyncSession):
    query = select(User.account)
    result = await db.execute(query)
    existing_accounts = set(result.scalars().all())

    # 默认保留教师账号 123 / 123 与学生演示账号 456 / 456
    if "123" not in existing_accounts:
        db.add(User(account="123", password="123", role="teacher", student_id=None))
        existing_accounts.add("123")
    if "456" not in existing_accounts:
        db.add(User(account="456", password="456", role="student", student_id="D01"))
        existing_accounts.add("456")

    # 扫描 01_按学生 目录下的每个文件夹，文件夹名就是学生账号和密码（如 D01 / D01）
    if students_data_dir.exists():
        for folder in sorted(students_data_dir.iterdir()):
            if not folder.is_dir():
                continue
            sid = folder.name
            if sid not in existing_accounts:
                db.add(User(account=sid, password=sid, role="student", student_id=sid))
                existing_accounts.add(sid)

    return len(existing_accounts)
