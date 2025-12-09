from pydantic import BaseModel
from typing import Optional, Any

class VoiceAgentEvent(BaseModel):
    type: Optional[str] = None  # e.g., "stt_output", "agent_chunk", "tts_chunk"
    text: Optional[str] = None
    audio: Optional[bytes] = None
    transcript: Optional[str] = None
    is_final: Optional[bool] = False
    confidence: Optional[float] = 0.0
    
    class Config:
        arbitrary_types_allowed = True

class AgentChunkEvent(VoiceAgentEvent):
    """Helper to quickly create agent text events"""
    def __init__(self, text: str):
        super().__init__(type="agent_chunk", text=text)