"""
大模型与嵌入模型工厂：
和 P3 课程一致，使用阿里云通义千问 ChatTongyi 与 DashScopeEmbeddings。
运行前请确保环境变量 DASHSCOPE_API_KEY 已配置。
"""
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings

from agent.config.settings import CHAT_MODEL_NAME, EMBEDDING_MODEL_NAME


def get_chat_model():
    """获取聊天大模型对象（默认 qwen-plus）"""
    return ChatTongyi(model=CHAT_MODEL_NAME)


def get_embed_model():
    """获取文本向量嵌入模型对象（默认 text-embedding-v4）"""
    return DashScopeEmbeddings(model=EMBEDDING_MODEL_NAME)
