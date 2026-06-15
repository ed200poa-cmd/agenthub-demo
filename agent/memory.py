from langchain.memory import ConversationBufferMemory
from typing import Dict

_sessions: Dict[str, ConversationBufferMemory] = {}


def get_memory(session_id: str) -> ConversationBufferMemory:
    if session_id not in _sessions:
        _sessions[session_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
        )
    return _sessions[session_id]


def get_history(session_id: str) -> list:
    if session_id not in _sessions:
        return []
    memory = _sessions[session_id]
    messages = memory.chat_memory.messages
    return [
        {"role": "human" if m.__class__.__name__ == "HumanMessage" else "ai", "content": m.content}
        for m in messages
    ]


def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]


def list_sessions() -> list:
    return list(_sessions.keys())
