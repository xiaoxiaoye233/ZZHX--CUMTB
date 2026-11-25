"""
长期会话记忆模块（直接沿用 P3 课程 21长期会话记忆.py 的本地 JSON 文件思路）：
1. 每个学生一个文件：agent/chat_history/student_D01.json
2. 教师端一个文件：agent/chat_history/teacher_default.json
3. 硬盘里完整保存全部历史记录（用于打开页面时完整展示）；
   传给大模型时只截取最近 MAX_HISTORY_MESSAGES 条（避免历史太长费 token）。
"""
import json
import re
from collections.abc import Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory

from agent.config.settings import CHAT_HISTORY_DIR, MAX_HISTORY_MESSAGES
from agent.core.plain_text import ensure_plain_text


_HISTORY_LOCK = RLock()


def sanitize_key(raw: str) -> str:
    """清理文件名里的特殊字符，只保留字母、数字、下划线和短横线"""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", raw.strip())
    return cleaned or "default"


def student_session_key(student_id: str) -> str:
    """生成学生长期会话的文件标识，例如 D01 -> student_D01（自动统一大写）"""
    return f"student_{sanitize_key(student_id.strip().upper())}"


def teacher_session_key(session_id: str = "default") -> str:
    """生成教师长期会话的文件标识，默认 teacher_default"""
    return f"teacher_{sanitize_key(session_id or 'default')}"


def get_history_file_path(session_key: str) -> Path:
    """获取对应会话的 JSON 文件完整路径，不存在目录会自动创建"""
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_HISTORY_DIR / f"{session_key}.json"


def load_chat_history(session_key: str) -> list[dict]:
    """
    从本地 JSON 文件读取长期会话历史：
    返回格式：[{"role": "user"|"assistant", "content": "...", "tag": "..."}, ...]
    """
    file_path = get_history_file_path(session_key)
    with _HISTORY_LOCK:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
    return data if isinstance(data, list) else []


def save_chat_history(session_key: str, messages: list[dict]) -> None:
    """把完整会话列表以 JSON 格式写回本地文件（ensure_ascii=False 让中文直接可读）"""
    file_path = get_history_file_path(session_key)
    with _HISTORY_LOCK:
        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=file_path.parent, delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(messages, temporary_file, ensure_ascii=False, indent=2)
            temporary_path.replace(file_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def append_chat_messages(
    session_key: str, new_messages: list[dict], *, only_if_empty: bool = False
) -> list[dict]:
    """在同一个锁内读取、追加并保存本地历史。"""
    with _HISTORY_LOCK:
        history = load_chat_history(session_key)
        if only_if_empty and history:
            return history
        history.extend(new_messages)
        save_chat_history(session_key, history)
        return history


def clear_chat_history(session_key: str) -> None:
    """清空某个会话的历史记录"""
    save_chat_history(session_key, [])


def attach_last_assistant_ref(session_key: str, textbook_ref: dict | None) -> None:
    """将本轮命中的教材文件与页码附加到最新一条助手回复中，便于历史会话回放跳转。"""
    if not textbook_ref:
        return
    with _HISTORY_LOCK:
        history = load_chat_history(session_key)
        for row in reversed(history):
            if row.get("role") == "assistant":
                row["textbook_ref"] = textbook_ref
                save_chat_history(session_key, history)
                return


class FileChatMessageHistory(BaseChatMessageHistory):
    """在 LangChain 消息与项目原有的 role/content/tag JSON 之间转换。"""

    def __init__(self, session_key: str, assistant_tag: str):
        self.session_key = session_key
        self.assistant_tag = assistant_tag
        self.write_error: OSError | None = None

    @property
    def messages(self) -> list[BaseMessage]:
        rows = load_chat_history(self.session_key)
        if MAX_HISTORY_MESSAGES > 0:
            # 给本轮用户提问留一个位置。
            start = max(0, len(rows) - (MAX_HISTORY_MESSAGES - 1))
            rows = rows[start:]

        history = []
        for row in rows:
            content = str(row.get("content", "")).strip()
            if not content:
                continue
            if row.get("role") == "user":
                history.append(HumanMessage(content=content))
            elif row.get("role") == "assistant":
                history.append(AIMessage(content=content))
        return history

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        rows = []
        for message in messages:
            if isinstance(message, HumanMessage):
                rows.append({"role": "user", "content": message.content, "tag": ""})
            elif isinstance(message, AIMessage):
                rows.append({"role": "assistant", "content": message.content, "tag": self.assistant_tag})

        try:
            append_chat_messages(self.session_key, rows)
        except OSError as exc:
            # LangChain 在回调中保存历史，调用方仍需知道写入是否失败。
            self.write_error = exc
            raise

    def clear(self) -> None:
        clear_chat_history(self.session_key)


def _prepare_agent_input(prompt_value: ChatPromptValue) -> dict[str, list[BaseMessage]]:
    """把提示词生成的消息转为 Agent 接收的输入。"""
    return {"messages": prompt_value.to_messages()}


def _parse_agent_reply(result: dict) -> str:
    """从 Agent 的消息列表中取出最终回复，并执行纯文本清洗（严禁 Markdown / LaTeX）。"""
    content = result["messages"][-1].content
    if isinstance(content, str):
        raw = content.strip()
    elif isinstance(content, list):
        parts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in content]
        raw = "".join(parts).strip()
    else:
        raw = str(content).strip()
    return ensure_plain_text(raw)


def invoke_with_history(agent, session_key: str, message: str, assistant_tag: str) -> str:
    """为一次 Agent 对话自动加载历史，并把本轮提问和最终回答写回。"""
    # 系统提示词已在创建学生或教师 Agent 时传入。
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    base_chain = prompt | _prepare_agent_input | agent | _parse_agent_reply

    history = None

    def get_history(session_id: str) -> FileChatMessageHistory:
        nonlocal history
        history = FileChatMessageHistory(session_id, assistant_tag)
        return history

    conversation_chain = RunnableWithMessageHistory(
        base_chain,
        get_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    session_config = {
        "configurable": {
            "session_id": session_key,
        }
    }
    reply = conversation_chain.invoke({"input": message}, config=session_config)
    if history is not None and history.write_error is not None:
        raise history.write_error
    return reply
