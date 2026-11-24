import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _load_env_files(*env_paths: Path) -> None:
    """从本地 .env 文件加载配置（兼容 Windows 记事本 UTF-8 BOM；留空项不覆盖系统环境变量）。"""
    for env_path in env_paths:
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            elif " #" in value:
                value = value.split(" #", 1)[0].strip()
            if value:
                os.environ[key] = value


# 数据层与仓库根路径配置
repo_root = Path(__file__).resolve().parents[2]
_load_env_files(repo_root / ".env", Path(__file__).resolve().parents[1] / ".env")

# 数据库连接（优先读取根目录 .env，否则使用默认 root / 123456 / zjhx_teaching）
mysql_host = os.environ.get("MYSQL_HOST", "127.0.0.1")
mysql_port = int(os.environ.get("MYSQL_PORT", "3306"))
mysql_user = os.environ.get("MYSQL_USER", "root")
raw_mysql_password = os.environ.get("MYSQL_PASSWORD", "123456")
mysql_password = quote_plus(raw_mysql_password)
mysql_database = os.environ.get("MYSQL_DATABASE", "zjhx_teaching")
async_database_url = (
    f"mysql+aiomysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
)

data_layer_root = repo_root / "数据层"
upload_target_dir = (
    data_layer_root / "赛题数据" / "赛题资料包" / "4_赛题数据" / "模拟学情数据"
)
steps_dir = data_layer_root / "src" / "steps"
dataset_dir = data_layer_root / "dataset"
students_data_dir = dataset_dir / "01_按学生"

# 创建异步引擎
async_engine = create_async_engine(
    async_database_url,
    echo=False,
    pool_size=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    max_overflow=20,
    connect_args={"connect_timeout": 2},
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 依赖项，用于获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.in_transaction():
                # 只读请求（或 MySQL 未启动走 CSV 兜底时）直接回滚，避免对失效连接执行 commit 报错
                if session.new or session.dirty or session.deleted:
                    await session.commit()
                else:
                    await session.rollback()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            await session.close()
