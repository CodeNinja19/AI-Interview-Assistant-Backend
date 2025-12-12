from langchain_core.tools import tool
from ChatBot.events import VoiceAgentEvent
from fastapi import WebSocket
import json
from ChatBot.socket_manager import get_active_socket
from langchain_core.tools import tool
@tool
async def open_editor( question: str, initial_code: str) -> str:
    """
    This is an tool that will allow you to open text editor on the users webpage. Which will allow him to 
    reply to a coding question with an code in c++. Always try giving the user complete this function type questions. 

    E.g:
        question: Give the code to find an element in sorted array.
        initial_code: "#include<bits/stdc++.h>\nusing namespace std;\nint main(){\nreturn 0;\n}"
    Arguments:
        question: The coding question the user must solve and provide the code for.
        initial_code: The code you want to past on users screen. It may be an boiler plate code or any other code that the user has to complete.
    Returns:
        It gives the confirmation message. That tell if the user text editor was opened or not.
    """
    websocket = get_active_socket()
    try:
        await websocket.send_text(json.dumps({
            "type": "open_editor",
            "initialCode":initial_code,
            "question": question
        }))
        return "Successfully opened the editor"
    except Exception as e:
        return f"There was an error while sending the message {e}"[:50]