from pathlib import Path

# ==================== 目录路径配置 ====================
AGENT_ROOT = Path(__file__).resolve().parents[1]          # D:\ZJHX--CUMTB\agent

# ==================== 大模型与嵌入模型配置（阿里云通义千问 DashScope） ====================
# 请确保系统环境变量已配置 DASHSCOPE_API_KEY
CHAT_MODEL_NAME = "qwen-plus"                              # 可选：qwen-flash / qwen-max / qwen-turbo（qwen3-max 当前账号不支持）
EMBEDDING_MODEL_NAME = "text-embedding-v4"

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

# ==================== MySQL 数据库配置（直接在这里改密码/库名） ====================
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "zjhx_teaching",
    "charset": "utf8mb4",
}
