from fastapi import Request
from mongodb.schema.userConversation import Conversation

async def add_or_update_conversation(request: Request, username: str, conversation_id: str):
    """
    Add a conversation ID to the user's conversation list and set it as the last conversation.
    """
    await request.app.database["userConversation"].update_one(
        {"username": username},
        {
            "$addToSet": {"conversation_ids": conversation_id},
            "$set": {"last_conversation_id": conversation_id}
        },
        upsert=True
    )

async def get_user_conversations(request: Request, username: str):
    """
    Retrieve the user's conversation IDs and last conversation ID.
    """
    response = await request.app.database["userConversation"].find_one({"username": username})
    print("Fetched conversations:", response)
    return Conversation(
        username=str(response["username"]),
        conversation_ids=[str(x) for x in response["conversation_ids"]],  
        last_conversation_id=str(response["last_conversation_id"])
    )