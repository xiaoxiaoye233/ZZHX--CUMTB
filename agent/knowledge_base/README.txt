=== RAG 知识库 PDF 存放说明 ===

1. 放教材 PDF（供学生答疑时优先检索）：
   请把教材 PDF 或 TXT 文件放入：D:\ZJHX--CUMTB\agent\knowledge_base\textbook\

2. 放课标说明 PDF（供教师授课/备课咨询时优先检索）：
   请把课标说明 PDF 或 TXT 文件放入：D:\ZJHX--CUMTB\agent\knowledge_base\curriculum\

3. 放入文件后，如何把 PDF 切分并向量化存入 Chroma？
   方式 A（命令行运行）：
     cd D:\ZJHX--CUMTB\agent
     python rag/vector_store.py

   方式 B（调用后端接口）：
     POST http://127.0.0.1:8000/api/agent/rebuild-rag

说明：系统会自动记录每个文件的 MD5 到 knowledge_base/md5.txt，
同一个文件不会重复向量化；新增文件后重新运行一次即可增量入库。
