from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 数据库 URL（直接在这里改密码和库名即可）
ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/zjhx_teaching?charset=utf8mb4"

# 数据层路径配置
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_LAYER_ROOT = REPO_ROOT / "数据层"
UPLOAD_TARGET_DIR = (
    DATA_LAYER_ROOT / "赛题数据" / "赛题资料包" / "4_赛题数据" / "模拟学情数据"
)
STEPS_DIR = DATA_LAYER_ROOT / "src" / "steps"
DATASET_DIR = DATA_LAYER_ROOT / "dataset"
STUDENTS_DATA_DIR = DATASET_DIR / "01_按学生"

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,          # 可选：输出 SQL 日志
    pool_size=10,       # 设置连接池中保持的持久连接数
    max_overflow=20,    # 设置连接池允许创建的额外连接数
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
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
