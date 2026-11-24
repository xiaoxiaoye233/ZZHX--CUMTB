"""
RAG 知识库检索工具（给 LangChain Agent 调用的 @tool）：
- search_textbook_knowledge：优先检索教材 PDF（学生答疑主要用这个）
- search_curriculum_standard：优先检索课标说明 PDF，并结合 MySQL 课标原文表（教师授课主要用这个）
"""
from langchain_core.tools import tool

from agent.rag.vector_store import search_knowledge
from agent.tools.db_tools import query_curriculum_table


@tool(description="检索教材 PDF 知识库，查找数学概念、公式、定理、例题和教材讲解。参数 query 为要查询的知识点或问题。")
def search_textbook_knowledge(query: str) -> str:
    return search_knowledge(query, category="textbook")


@tool(description="检索课程标准说明 PDF 知识库以及数据库中的课标原文表，查找数学教学要求、课标目标和授课依据。参数 query 为主题或关键词，如 '一元一次方程'、'不等式'。")
def search_curriculum_standard(query: str) -> str:
    pdf_result = search_knowledge(query, category="curriculum")
    db_result = query_curriculum_table(query)

    if db_result:
        return f"{pdf_result}\n\n{db_result}"
    return pdf_result
