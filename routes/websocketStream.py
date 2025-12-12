import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import AsyncIterator
from ChatBot.socket_manager import active_websocket
# Import your modules
from ChatBot.stt import stt_stream
from ChatBot.invoke_agent import agent_stream
from ChatBot.tts import tts_stream
from ChatBot.events import VoiceAgentEvent

router = APIRouter(prefix='/socket')

@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    print("INFO: Setting the websocket")
    active_websocket.set(websocket)
    await websocket.accept()
    print("INFO: WebSocket connection accepted")

    # 1. Queue for RAW AUDIO (Bytes from Frontend)
    audio_queue = asyncio.Queue()
    
    # 2. Queue for EVENTS (The "Bus" where STT and Config meet)
    # This acts as the central hub for data flow
    event_queue = asyncio.Queue()

    # Shared State
    state = {
        "listen_only": False,       # Default mode
        "transcript_buffer": []     # Stores text while in Listen Mode
    }

    # --- TASK A: Read from WebSocket (Audio + Config) ---
    # --- TASK A: Read from WebSocket ---
    # --- TASK A: Read from WebSocket ---
    async def receive_socket_data():
        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message:
                    data = message["bytes"]
                    if data and len(data) > 0:
                        await audio_queue.put(data)

                elif "text" in message:
                    try:
                        data = json.loads(message["text"])
                        
                        # 1. ✅ RESTORED: Config / Mode Switching Logic
                        if data.get("type") == "config":
                            new_mode = data.get("listen_only", False)
                            
                            # LOGIC: If switching FROM Listen (True) TO Interactive (False)
                            # We must tell the gate to FLUSH the buffer now.
                            if state["listen_only"] and not new_mode:
                                print("DEBUG: 🟢 Switching to Interactive. Flushing Buffer...")
                                await event_queue.put(VoiceAgentEvent(
                                    type="system_command", 
                                    text="flush_buffer"
                                ))
                            
                            state["listen_only"] = new_mode
                            print(f"INFO: Mode set to: {'Listen Only' if new_mode else 'Interactive'}")

                        # 2. Handle Code Submission
                        elif data.get("type") == "code_submission":
                            user_code = data.get("code", "")
                            print(f"DEBUG: 📥 Received Code Submission: {len(user_code)} chars")
                            
                            # Send to queue (Logic Gate will decide to buffer or pass based on mode)
                            await event_queue.put(VoiceAgentEvent(
                                type="user_submission", 
                                text=f"I have submitted the following code for review:\n```cpp\n{user_code}\n```",
                                is_final=True
                            ))

                    except Exception as e:
                        print(f"JSON Error: {e}")

        except WebSocketDisconnect:
            print("INFO: Client disconnected")
        except Exception as e:
            print(f"Socket Error: {e}")
        finally:
            await audio_queue.put(None)
            await event_queue.put(None)


    # --- TASK B: Google STT Producer ---
    async def run_stt_process():
        try:
            # Pass the Queue DIRECTLY to stt_stream. 
            async for event in stt_stream(audio_queue, websocket): 
                await event_queue.put(event)
                
        except asyncio.CancelledError:
            # ✅ This handles the "End Stream" signal gracefully
            print("INFO: STT Process cancelled (Standard Shutdown)")
            
        except Exception as e:
            # This handles actual crashes (like Google API errors)
            print(f"STT Process Error: {e}")
            
        finally:
            # Always ensure the event queue knows we are done
            await event_queue.put(None)
    # --- TASK C: The Logic Gate (Middleware) ---
    async def buffer_gate_middleware():
        while True:
            # Wait for NEXT event (Could be STT or a Button Click Command)
            event = await event_queue.get()
            if event is None: break # Stop signal

            # --- LOGIC 1: Handle "Flush" Command ---
            if event.type == "system_command" and event.text == "flush_buffer":
                if state["transcript_buffer"]:
                    # Combine buffered sentences
                    full_context = " ".join(state["transcript_buffer"])
                    print(f"DEBUG: 🚀 Replaying Context: '{full_context}'")
                    
                    state["transcript_buffer"] = [] # Clear
                    
                    # Send to Agent immediately
                    yield VoiceAgentEvent(type="stt_output", text=full_context, is_final=True)
                continue

            # --- LOGIC 2: Echo User Transcript to Frontend ---
            # Always update the UI, even in Listen Mode
            if event.type == "stt_output" and event.is_final and event.text:
                try:
                    await websocket.send_text(json.dumps({
                        "type": "user_transcript", 
                        "text": event.text
                    }))
                except Exception:
                    pass # Socket might be closed

            # --- LOGIC 3: Mode Handling ---
            if state["listen_only"]:
                # ✅ CHANGED: Buffer if it is STT *OR* a Code Submission
                is_content_event = (event.type == "stt_output" and event.is_final) or (event.type == "user_submission")

                if is_content_event and event.text:
                    state["transcript_buffer"].append(event.text)
                    print(f"🔒 Buffered Content: {event.text[:30]}...")
                
                else:
                    # Pass through system events (like errors or logs)
                    if event.type != "stt_output" and event.type != "user_submission":
                        yield event
            else:
                # INTERACTIVE MODE: Pass everything to the Agent
                yield event

    # --- TASK D: The Response Pipeline ---
    async def run_response_pipeline():
        try:
            # 1. Connect Gate to Agent
            gate_stream = buffer_gate_middleware()
            
            # 2. Connect Agent to TTS
            # agent_stream takes the stream first, then the websocket/request
            agent_output = agent_stream(gate_stream, websocket)
            
            # 3. Connect TTS to WebSocket Output
            final_stream = tts_stream(agent_output)

            async for event in final_stream:
                if event.type == "tts_chunk":
                    await websocket.send_bytes(event.audio)
                elif event.type == "agent_chunk":
                    # Stream Agent Text to UI
                    await websocket.send_text(event.text)
                    
        except Exception as e:
            print(f"Pipeline Error: {e}")
            import traceback
            traceback.print_exc()

    # --- MAIN EXECUTION ---
    # Run all tasks concurrently
    try:
        await asyncio.gather(
            receive_socket_data(), 
            run_stt_process(), 
            run_response_pipeline()
        )
    except Exception:
        pass