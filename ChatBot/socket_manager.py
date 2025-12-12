# socket_manager.py
from contextvars import ContextVar
from fastapi import WebSocket
from typing import Optional

# This variable acts as a placeholder
# It defaults to None, but we will "fill" it during a request
active_websocket: ContextVar[Optional[WebSocket]] = ContextVar("active_websocket", default=None)

def get_active_socket() -> WebSocket:
    ws = active_websocket.get()
    if ws is None:
        raise RuntimeError("No active WebSocket found in this context!")
    return ws