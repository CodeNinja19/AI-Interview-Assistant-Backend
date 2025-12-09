from fastapi import APIRouter, Request, Depends
import uuid
from mongodb.userConversations import add_or_update_conversation, get_user_conversations
from ChatBot.invoke_agent import invoke_agent, get_conversation_history
from mongodb.schema.userConversation import UserChat
from routes.dependencies.check_login import check_login
router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(check_login)]
)

@router.get("/newConversation")
async def new_conversation(request: Request):
    conversation_id = str(uuid.uuid4())
    username = request.state.user.username  # Set by CheckLoginMiddleware
    await add_or_update_conversation(request, username, conversation_id)
    return {"conversation_id": conversation_id}

@router.get("/history")
async def conversation_history(request: Request) -> dict:
    user = request.state.user  # Set by CheckLoginMiddleware
    conversations = await get_user_conversations(request, user.username)
    if conversations:
        return conversations.model_dump(by_alias=True)
    return {"message": "No conversations found"}

@router.post("/message")
async def send_message(userQuery: UserChat ,request: Request):
    response = await invoke_agent(request, userQuery.message, userQuery.conversation_id)
    return {"message": response,"type":"ai"}

@router.get("/conversation_history/{conversation_id}")
async def get_chat_conversation_history(request: Request, conversation_id: str):
    history = get_conversation_history(request, conversation_id)
    return {"history": history}