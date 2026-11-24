r"""
独立 LangChain RAG + Agent 模块（D:\ZJHX--CUMTB\agent）

目录分工：
- config/         模型、RAG 路径、MySQL 配置
- knowledge_base/ 教材 PDF、课标 PDF 及 Chroma 本地向量库
- prompts/        个性化建议、学生答疑（含防御性护栏）、教师备课提示词
- memory/         本地 JSON 文件长期会话记忆（agent/chat_history/）
- rag/            PyPDFLoader 读取 + 切片 + MD5 去重 + Chroma 向量化与检索
- tools/          给 Agent 调用的 @tool（MySQL 学情/错题/班级查询 + RAG 检索）
- core/           大模型工厂、学生端 Agent、教师端 Agent
- run_demo.py     无需启动后端，直接命令行体验全部功能
"""
