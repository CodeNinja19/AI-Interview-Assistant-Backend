from pydantic import BaseModel, Field
from typing import List

class Conversation(BaseModel):
    username: str
    conversation_ids: List[str]
    last_conversation_id: str
class UserChat(BaseModel):
    message: str
    conversation_id: str