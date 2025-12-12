import time
import asyncio
import json
from google.cloud import speech
from google.api_core.exceptions import OutOfRange, InvalidArgument, InternalServerError
from ChatBot.events import VoiceAgentEvent 

STREAM_LIMIT = 240 # 4 Minutes

async def stt_stream(audio_queue: asyncio.Queue, websocket):
    print("DEBUG: STT Stream Initialized (Stop-and-Wait Strategy)")
    
    while True:
        try:
            # 1. Wait for Audio (This will block until the frontend starts sending)
            # On the first run, this grabs the header instantly.
            # On rotation, this waits for the "start_audio" command to take effect.
            initial_chunk = await audio_queue.get()
            
            if initial_chunk is None:
                print("DEBUG: End of Audio Stream.")
                break 

            # 2. Setup Google Client
            client = speech.SpeechAsyncClient()
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="en-US",
                enable_automatic_punctuation=True,
            )
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True
            )

            async def request_generator(header_chunk):
                # Send Config & Header
                yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
                yield speech.StreamingRecognizeRequest(audio_content=header_chunk)
                
                start_time = time.time()
                
                while True:
                    # --- ROTATION LOGIC (STOP-AND-WAIT) ---
                    if time.time() - start_time > STREAM_LIMIT:
                        print("DEBUG: ⏱️ Time Limit. Orchestrating Restart...")
                        
                        # Step A: Tell Frontend to STOP sending audio
                        await websocket.send_text(json.dumps({"type": "stop_audio"}))
                        
                        # Step B: Wait for the 'Stop' to take effect and pipe to dry up
                        # We give it 1 second to ensure all in-flight packets arrive
                        await asyncio.sleep(1.0) 
                        
                        # Step C: FLUSH QUEUE
                        # We are now 100% sure the queue only contains old garbage
                        dropped = 0
                        while not audio_queue.empty():
                            try:
                                audio_queue.get_nowait()
                                dropped += 1
                            except asyncio.QueueEmpty:
                                break
                        print(f"DEBUG: 🧹 Safe-Flushed {dropped} packets.")
                        
                        # Step D: Tell Frontend to START recording again
                        # This generates the NEW Header, which will be the first thing
                        # the main loop sees when we return.
                        await websocket.send_text(json.dumps({"type": "start_audio"}))
                        
                        return # Restart main loop

                    # --- STANDARD STREAMING ---
                    try:
                        data = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                        if data is None: raise StopAsyncIteration()
                        if len(data) > 0:
                            yield speech.StreamingRecognizeRequest(audio_content=data)
                    except asyncio.TimeoutError:
                        continue

            # 3. Run Stream
            try:
                stream_responses = await client.streaming_recognize(requests=request_generator(initial_chunk))
                async for response in stream_responses:
                    if not response.results: continue
                    result = response.results[0]
                    if not result.alternatives: continue
                    transcript = result.alternatives[0].transcript
                    is_final = result.is_final
                    if not transcript.strip(): continue
                    
                    yield VoiceAgentEvent(
                        type="stt_output",
                        text=transcript,
                        is_final=is_final,
                        confidence=result.alternatives[0].confidence
                    )

            except InternalServerError:
                print("WARN: Google 500 Error. Restarting...")
                continue

        except StopAsyncIteration:
            break
        except (OutOfRange, InvalidArgument) as e:
            # Fallback if something still goes wrong
            print(f"⚠️ Stream Error ({e}). Forcing Restart...")
            await websocket.send_text(json.dumps({"type": "stop_audio"}))
            await asyncio.sleep(1.0)
            while not audio_queue.empty(): audio_queue.get_nowait()
            await websocket.send_text(json.dumps({"type": "start_audio"}))
            continue
        except Exception as e:
            print(f"🛑 STT Loop Error: {e}")
            await asyncio.sleep(1)
            continue