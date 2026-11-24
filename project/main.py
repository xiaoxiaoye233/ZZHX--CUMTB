from contextlib import asynccontextmanager
from pathlib import Path
import sys

# 把上层目录 D:\ZJHX--CUMTB 加入搜索路径，以便导入独立同级文件夹 agent
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.db_conf import async_engine
from crud import teacher as teacher_crud
from routers import agent, student, teacher, users
from utils.exception_handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时自动尝试在 MySQL 建库、建表并同步 00-04 数据和学生账号
    try:
        counts = await teacher_crud.init_db_and_sync()
        print("MySQL 建库建表并导入 00-04 数据完成:", counts)
    except Exception as exc:
        print(f"[提示] 启动时未能连接 MySQL（接口将自动使用 CSV 兜底）：{exc}")
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(lifespan=lifespan)

# 注册全局异常处理器
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",  # 支持携带 Cookie 的本地开发与局域网跨域请求
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


# 挂载路由 / 注册路由
app.include_router(users.router)
app.include_router(teacher.router)
app.include_router(student.router)
app.include_router(agent.router)
