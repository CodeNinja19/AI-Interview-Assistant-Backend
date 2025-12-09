import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import AsyncIterator

# Import your modules
from ChatBot.stt import stt_stream
from ChatBot.invoke_agent import agent_stream
from ChatBot.tts import tts_stream
from ChatBot.events import VoiceAgentEvent

router = APIRouter(prefix='/socket')

@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
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
    async def receive_socket_data():
        try:
            while True:
                # Catch RuntimeError here in case socket disconnects mid-read
                message = await websocket.receive()

                if "bytes" in message:
                    data = message["bytes"]
                    # CRITICAL: Filter empty bytes to prevent Google 400 Errors
                    if data and len(data) > 0:
                        await audio_queue.put(data)
                
                elif "text" in message:
                    try:
                        config = json.loads(message["text"])
                        if config.get("type") == "config":
                            new_mode = config.get("listen_only", False)
                            
                            # LOGIC: Switch FROM Listen TO Interactive
                            # We need to tell the gate to release the held text
                            if state["listen_only"] and not new_mode:
                                print("DEBUG: 🟢 Switching to Interactive. Flushing Buffer...")
                                await event_queue.put(VoiceAgentEvent(
                                    type="system_command", 
                                    text="flush_buffer"
                                ))
                            
                            state["listen_only"] = new_mode
                            print(f"INFO: Mode set to: {'Listen Only' if new_mode else 'Interactive'}")
                            
                    except Exception as e:
                        print(f"Config Error: {e}")

        except WebSocketDisconnect:
            print("INFO: Client disconnected (Standard)")
            
        except RuntimeError as e:
            # Handle "Cannot call receive once a disconnect message has been received"
            if "disconnect" in str(e).lower():
                print("INFO: Client connection lost (Runtime)")
            else:
                print(f"Socket Error: {e}")
                
        finally:
            # Signal all other tasks to stop
            await audio_queue.put(None)
            await event_queue.put(None)

    # --- TASK B: Google STT Producer ---
    async def run_stt_process():
        try:
            # Pass the Queue DIRECTLY to stt_stream. 
            # Do NOT use a generator here, or you break the "Infinite/Lazy" logic.
            async for event in stt_stream(audio_queue, websocket): 
                await event_queue.put(event)
        except Exception as e:
            print(f"STT Process Error: {e}")
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
                # LISTEN MODE: Store text, do NOT yield to Agent
                if event.type == "stt_output" and event.is_final and event.text:
                    state["transcript_buffer"].append(event.text)
                    print(f"🔒 Buffered: '{event.text}'")
                else:
                    # Pass through non-speech events (logs, errors)
                    if event.type != "stt_output":
                        yield event
            else:
                # INTERACTIVE MODE: Pass everything
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