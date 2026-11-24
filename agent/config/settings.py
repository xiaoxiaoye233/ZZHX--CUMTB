import os
from pathlib import Path


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


# ==================== 目录路径配置 ====================
AGENT_ROOT = Path(__file__).resolve().parents[1]          # <repo>/agent
_load_env_files(AGENT_ROOT.parent / ".env", AGENT_ROOT / ".env")

# ==================== 大模型与嵌入模型配置（阿里云通义千问 DashScope） ====================
# 可在仓库根目录 .env 文件填写 DASHSCOPE_API_KEY，或配置系统环境变量
CHAT_MODEL_NAME = os.environ.get("CHAT_MODEL_NAME", "qwen-plus")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "text-embedding-v4")

# ==================== RAG PDF 知识库路径配置 ====================
KNOWLEDGE_BASE_DIR = AGENT_ROOT / "knowledge_base"
TEXTBOOK_PDF_DIR = KNOWLEDGE_BASE_DIR / "textbook"        # 放教材 PDF（学生答疑主要检索这里）
CURRICULUM_PDF_DIR = KNOWLEDGE_BASE_DIR / "curriculum"    # 放课标说明 PDF（教师授课主要检索这里）
CHROMA_PERSIST_DIR = KNOWLEDGE_BASE_DIR / "chroma_db"     # Chroma 向量库持久化目录
MD5_STORE_PATH = KNOWLEDGE_BASE_DIR / "md5.txt"           # 已入库文件 MD5 指纹，避免重复向量化

# 文本切分与检索参数
CHROMA_COLLECTION_NAME = "teaching_knowledge"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
RETRIEVER_TOP_K = 4

# ==================== 提示词模板目录 ====================
PROMPTS_DIR = AGENT_ROOT / "prompts"

# ==================== 长期会话历史记录配置 ====================
CHAT_HISTORY_DIR = AGENT_ROOT / "chat_history"            # 每个学生和老师的长期聊天 JSON 文件保存目录
MAX_HISTORY_MESSAGES = 20                                 # 每次传给大模型的最近消息条数（20 条 = 最近 10 轮）

# ==================== MySQL 数据库配置（优先读根目录 .env，否则用默认值） ====================
MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "123456"),
    "database": os.environ.get("MYSQL_DATABASE", "zjhx_teaching"),
    "charset": "utf8mb4",
}
