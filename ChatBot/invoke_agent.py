import re
from fastapi import Request, WebSocket
from uuid import uuid4
from typing import AsyncIterator
from ChatBot.events import VoiceAgentEvent, AgentChunkEvent
from langchain_core.messages import HumanMessage, AIMessage
async def invoke_agent(request: Request, messages: str, conversation_id: str):
    agent = request.app.agent
    config = {
        "configurable":{"thread_id": conversation_id + request.state.user.username}
    }
    response = await agent.ainvoke({"messages": [HumanMessage(content=messages)]}, config)
    return response["messages"][-1].content

# async def agent_stream(
#     event_stream: AsyncIterator[VoiceAgentEvent],
#     request: WebSocket,  # Changed from Request to WebSocket to match your caller
# ) -> AsyncIterator[VoiceAgentEvent]:
#     """
#     Transform stream: Voice Events → Voice Events (with Agent Responses)
#     """
#     # Generate unique thread ID for conversation memory
#     thread_id = str(uuid4())
#     agent = request.app.agent
    
#     async for event in event_stream:
#         # Pass through all upstream events
#         yield event

#         # Process final transcripts through the agent
#         # CRITICAL FIX 1: Check 'event.text', not 'event.transcript'
#         if event.type == "stt_output" and event.text and event.is_final:
            
#             print(f"DEBUG: Processing Agent Input: {event.text}")
            
#             try:
#                 # CRITICAL FIX 2: Use 'event.text' for the content
#                 human_msg = HumanMessage(content=event.text)

#                 stream = agent.astream(
#                     {"messages": [human_msg]},
#                     {"configurable": {"thread_id": thread_id}},
#                     stream_mode="messages",
#                 )

#                 # Yield agent response chunks as they arrive
#                 async for message, _ in stream:
#                     # Ensure message content exists before yielding
#                     if hasattr(message, 'content') and message.content:
#                         yield AgentChunkEvent(text=message.content)
                        
#             except Exception as e:
#                 print(f"AGENT ERROR: {e}")

async def agent_stream(
    event_stream: AsyncIterator[VoiceAgentEvent], 
    request: WebSocket
) -> AsyncIterator[VoiceAgentEvent]:
    
    agent = request.app.agent
    thread_id = str(uuid4())
    
    # Sentence Buffer State
    text_buffer = ""

    async for event in event_stream:
        # Pass through upstream events (logs, STT status)
        yield event

        # Process Final User Input
        if event.type == "stt_output" and event.text and event.is_final:
            
            print(f"DEBUG: 🧠 Agent Thinking on: {event.text}")
            
            try:
                human_msg = HumanMessage(content=event.text)

                stream = agent.astream(
                    {"messages": [human_msg]},
                    {"configurable": {"thread_id": thread_id}},
                    stream_mode="messages",
                )

                async for message, _ in stream:
                    if hasattr(message, 'content') and message.content:
                        token = message.content
                        text_buffer += token

                        # --- SENTENCE DETECTION LOGIC ---
                        # Check if buffer contains a sentence ending (. ? !) followed by space or newline
                        # We use a regex lookbehind to find the split point
                        if re.search(r'[.!?]\s+', text_buffer):
                            parts = re.split(r'(?<=[.!?])\s+', text_buffer)
                            
                            # Yield all complete sentences
                            for i in range(len(parts) - 1):
                                sentence = parts[i]
                                if sentence.strip():
                                    print(f"DEBUG: 📤 Yielding Sentence: '{sentence}'")
                                    yield AgentChunkEvent(text=sentence)
                            
                            # Keep the incomplete part (if any) in the buffer
                            text_buffer = parts[-1]
                
                # End of Stream: Flush whatever is left in the buffer
                if text_buffer.strip():
                     print(f"DEBUG: 📤 Yielding Final Fragment: '{text_buffer}'")
                     yield AgentChunkEvent(text=text_buffer)
                     text_buffer = ""
                        
            except Exception as e:
                print(f"AGENT ERROR: {e}")
def get_conversation_history(request: Request, conversation_id: str):
    agent = request.app.agent
    config = {
        "configurable":{"thread_id": conversation_id + request.state.user.username}
    }
    last_state = agent.get_state(config)
    print("Last state:", last_state)
    response = []
    if not last_state or not hasattr(last_state, 'values') or 'messages' not in last_state.values:
        return response
    for  index, curr in enumerate(last_state.values["messages"]):
        if isinstance(curr, HumanMessage):
            response.append({"type": "human", "text": curr.content})
        elif isinstance(curr, AIMessage) and (index == len(last_state.values["messages"]) - 1 or isinstance(last_state.values["messages"][index + 1], HumanMessage)):   
            response.append({"type": "ai", "text": curr.content})
    return response