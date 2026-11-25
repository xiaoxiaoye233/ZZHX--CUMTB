"""
RAG 向量知识库模块（完全沿用 P3 课程的 PyPDFLoader + RecursiveCharacterTextSplitter + Chroma 写法）：
1. 扫描 agent/knowledge_base/textbook（教材）和 agent/knowledge_base/curriculum（课标）里的 PDF / TXT
2. 用 MD5 去重，防止同一个 PDF 反复向量化浪费额度
3. 切片后批量写入本地持久化 Chroma 向量数据库
4. 提供按分类（教材 / 课标）检索函数给 Agent 工具调用
"""
import hashlib
from pathlib import Path
import sys

# 支持直接命令行运行：cd D:\ZJHX--CUMTB\agent && python rag/vector_store.py
REPO_ROOT = Path(__file__).resolve().parents[2]  # D:\ZJHX--CUMTB
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langchain_chroma import Chroma  # noqa: E402
from langchain_community.document_loaders import PyPDFLoader, TextLoader  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from agent.config.settings import (  # noqa: E402
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CURRICULUM_PDF_DIR,
    MD5_STORE_PATH,
    RETRIEVER_TOP_K,
    TEXTBOOK_PDF_DIR,
)
from agent.core.llm import get_embed_model  # noqa: E402
from agent.rag.textbook_locator import (  # noqa: E402
    record_textbook_tool_hit,
    rerank_textbook_docs,
    search_local_textbook_pages,
)


def get_vector_store() -> Chroma:
    """获取本地持久化 Chroma 向量数据库对象"""
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=get_embed_model(),
        persist_directory=str(CHROMA_PERSIST_DIR),
    )


def get_file_md5(file_path: Path) -> str:
    """计算文件 MD5 指纹，用于判断这个文件是不是已经入过库"""
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()


def load_saved_md5_set() -> set[str]:
    """读取已经入库的文件 MD5 集合"""
    if not MD5_STORE_PATH.exists():
        return set()
    lines = MD5_STORE_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip()}


def save_md5(md5_hex: str) -> None:
    """把新入库文件的 MD5 追加记到 md5.txt"""
    MD5_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MD5_STORE_PATH.open("a", encoding="utf-8") as f:
        f.write(md5_hex + "\n")


def read_single_file(file_path: Path, category: str):
    """用 PyPDFLoader / TextLoader 读取单个文件，并给每页打上分类元数据"""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        try:
            loader = PyPDFLoader(file_path=str(file_path))
            docs = loader.load()
        except Exception:
            # 个别 PDF 内嵌特殊 Type1 字体时，使用 pypdfium2 兜底逐页提取
            import pypdfium2 as pdfium

            docs = []
            pdf_doc = pdfium.PdfDocument(str(file_path))
            try:
                for page_idx in range(len(pdf_doc)):
                    txt = pdf_doc[page_idx].get_textpage().get_text_range() or ""
                    docs.append(Document(page_content=txt, metadata={"page": page_idx}))
            finally:
                pdf_doc.close()
    elif suffix == ".txt":
        loader = TextLoader(file_path=str(file_path), encoding="utf-8")
        docs = loader.load()
    else:
        return []

    # 给每个 Document 打上分类标签（textbook 教材 / curriculum 课标），方便后面精准过滤检索
    for doc in docs:
        doc.metadata["category"] = category
        doc.metadata["source_file"] = file_path.name
    return docs


def load_pdfs_to_chroma() -> dict:
    """
    扫描 knowledge_base/textbook 和 knowledge_base/curriculum 下的全部 PDF/TXT，
    切分并向量化存入 Chroma 数据库。
    """
    TEXTBOOK_PDF_DIR.mkdir(parents=True, exist_ok=True)
    CURRICULUM_PDF_DIR.mkdir(parents=True, exist_ok=True)

    vector_store = get_vector_store()
    saved_md5_set = load_saved_md5_set()

    # 文本切分器（和 P3 课程写法一致）
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    )

    folders = [
        ("textbook", TEXTBOOK_PDF_DIR),
        ("curriculum", CURRICULUM_PDF_DIR),
    ]

    added_files = []
    skipped_files = []
    total_chunks = 0

    for category, folder in folders:
        for file_path in sorted(folder.iterdir()):
            if not file_path.is_file():
                continue
            # 跳过说明占位文件
            if file_path.name.startswith("请把") or file_path.name.startswith("."):
                continue
            if file_path.suffix.lower() not in (".pdf", ".txt"):
                continue

            md5_hex = get_file_md5(file_path)
            if md5_hex in saved_md5_set:
                skipped_files.append(f"{category}/{file_path.name}")
                continue

            docs = read_single_file(file_path, category)
            if not docs:
                continue

            split_docs = splitter.split_documents(docs)
            # 过滤掉纯空白页切片
            split_docs = [d for d in split_docs if d.page_content and d.page_content.strip()]
            if not split_docs:
                continue

            # 阿里云 DashScope 嵌入模型单次最多 25 条文本，所以每 20 条分批写入更稳妥
            batch_size = 20
            for i in range(0, len(split_docs), batch_size):
                batch = split_docs[i : i + batch_size]
                vector_store.add_documents(batch)

            save_md5(md5_hex)
            saved_md5_set.add(md5_hex)
            added_files.append(f"{category}/{file_path.name}")
            total_chunks += len(split_docs)

    return {
        "added_files": added_files,
        "skipped_files": skipped_files,
        "total_chunks_added": total_chunks,
    }


def search_knowledge(query: str, category: str | None = None, k: int = RETRIEVER_TOP_K) -> str:
    """
    从 Chroma 向量库中检索相关资料，返回拼接好的参考文本：
    - category="textbook"：优先查教材 PDF
    - category="curriculum"：优先查课标 PDF
    - category=None：查整个知识库
    """
    vector_store = get_vector_store()

    docs = []
    if category:
        try:
            docs = vector_store.similarity_search(query, k=k, filter={"category": category})
        except Exception:
            docs = []

    # 如果对应分类还没放入 PDF，自动退回检索整个知识库
    if not docs:
        try:
            docs = vector_store.similarity_search(query, k=k)
        except Exception:
            docs = []

    if not docs and category == "textbook":
        local_hits = search_local_textbook_pages(query, top_k=k)
        docs = [
            Document(
                page_content=hit["raw_text"],
                metadata={
                    "category": "textbook",
                    "source_file": hit["source_file"],
                    "page": hit["page"] - 1,
                },
            )
            for hit in local_hits
        ]

    if not docs:
        return "（当前 PDF 向量知识库中暂无相关文档，请先将教材或课标 PDF 放入 agent/knowledge_base 文件夹并运行向量化。）"

    if category == "textbook":
        docs = rerank_textbook_docs(query, docs)
        top_doc = docs[0]
        top_source = top_doc.metadata.get("source_file", "")
        top_page = top_doc.metadata.get("page")
        if top_source:
            record_textbook_tool_hit(
                query=query,
                source_file=str(top_source),
                page_one_based=(top_page + 1) if isinstance(top_page, int) else 1,
            )

    lines = []
    for index, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source_file", "未知资料")
        page = doc.metadata.get("page")
        page_text = f"第 {page + 1} 页" if isinstance(page, int) else ""
        lines.append(f"【参考资料{index} | {source} {page_text}】\n{doc.page_content.strip()}")

    return "\n\n".join(lines)


if __name__ == "__main__":
    print("开始扫描 agent/knowledge_base 下的教材与课标 PDF 并向量化...")
    summary = load_pdfs_to_chroma()
    print("向量化完成:", summary)
