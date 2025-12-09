import time
import asyncio
import json
from google.cloud import speech
from google.api_core.exceptions import OutOfRange, InvalidArgument
from ChatBot.events import VoiceAgentEvent 

STREAM_LIMIT = 240 # 4 Minutes

async def stt_stream(audio_queue: asyncio.Queue, websocket):
    print("DEBUG: STT Stream Initialized (Magic Byte Filter)")
    
    while True:
        try:
            # 1. Wait for Valid Audio
            chunk = await audio_queue.get()
            
            if chunk is None:
                print("DEBUG: End of Audio Stream.")
                break 
            
            # --- CRITICAL FIX: Magic Byte Filter ---
            # A valid WebM file MUST start with the EBML Header: 1A 45 DF A3
            # If the chunk doesn't start with this, it's a "Tail" chunk from the old stream.
            # We ignore it and wait for the real header.
            if not chunk.startswith(b'\x1a\x45\xdf\xa3'):
                # print(f"DEBUG: Ignoring non-header chunk ({len(chunk)} bytes)")
                continue
            # ---------------------------------------

            # 2. Setup Client (Only if we found a valid header)
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

            async def request_generator():
                # Send Config
                yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
                
                # Send the Header Chunk we verified
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
                
                start_time = time.time()
                
                while True:
                    # Time Limit Check
                    if time.time() - start_time > STREAM_LIMIT:
                        print("DEBUG: ⏱️ Time Limit. Sending Rotation Command...")
                        # Tell Frontend to Restart Mic (This generates a NEW Header)
                        await websocket.send_text(json.dumps({"type": "rotate_audio"}))
                        return 

                    try:
                        data = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                        if data is None: raise StopAsyncIteration()
                        if len(data) > 0:
                            yield speech.StreamingRecognizeRequest(audio_content=data)
                    except asyncio.TimeoutError:
                        continue

            # 3. Start Streaming
            stream_responses = await client.streaming_recognize(requests=request_generator())
            
            async for response in stream_responses:
                if not response.results: continue
                result = response.results[0]
                if not result.alternatives: continue
                
                transcript = result.alternatives[0].transcript
                is_final = result.is_final
                
                if not transcript.strip(): continue
                
                # Yield Event
                yield VoiceAgentEvent(
                    type="stt_output",
                    text=transcript,
                    is_final=is_final,
                    confidence=result.alternatives[0].confidence
                )

        except StopAsyncIteration:
            break
        except (OutOfRange, InvalidArgument) as e:
            # If we get a 400 error, it means we are out of sync.
            # Force a rotation to get a fresh header.
            print(f"⚠️ Google Stream Error ({e}). Forcing Rotation...")
            try:
                await websocket.send_text(json.dumps({"type": "rotate_audio"}))
            except:
                pass
            await asyncio.sleep(1)
            continue
        except Exception as e:
            print(f"🛑 STT Loop Error: {e}")
            await asyncio.sleep(1)
            continue