r"""
单独测试 Agent 的命令行脚本（无需启动 FastAPI，直接就能体验全部功能）：
运行方式：
    cd D:\ZJHX--CUMTB\agent
    python run_demo.py
"""
from pathlib import Path
import sys

# 把上层目录 D:\ZJHX--CUMTB 加入导入路径，就能用 from agent.xxx import ...
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.core.student_agent import generate_student_advice, student_chat  # noqa: E402
from agent.core.teacher_agent import teacher_chat  # noqa: E402
from agent.rag.vector_store import load_pdfs_to_chroma  # noqa: E402


if __name__ == "__main__":
    print("=" * 60)
    print("步骤 1：扫描 agent/knowledge_base 里的教材与课标 PDF 并向量化")
    print("=" * 60)
    print(load_pdfs_to_chroma())

    print("\n" + "=" * 60)
    print("步骤 2：测试进入学生路由 -> 自动查库并生成个性化建议（D01）")
    print("=" * 60)
    print(generate_student_advice("D04"))

    print("\n" + "=" * 60)
    print("步骤 3：测试学生对话（结合数据库 + 教材 RAG + 保护自尊心）")
    print("=" * 60)
    print(student_chat("D04", "我觉得自己好笨，这几道不等式题一直做错，能帮我看看哪里薄弱吗？"))

    print("\n" + "=" * 60)
    print("步骤 4：测试教师对话（查班级数据库 + 查课标要求）")
    print("=" * 60)
    print(teacher_chat("帮我看看 DC02 班整体最薄弱的是什么，并结合课标说说下节课怎么讲？"))
