# import os
# from typing import AsyncIterator
# from elevenlabs.client import ElevenLabs
# from elevenlabs import VoiceSettings
# from ChatBot.events import VoiceAgentEvent

# async def tts_stream(event_stream: AsyncIterator[VoiceAgentEvent]) -> AsyncIterator[VoiceAgentEvent]:
#     api_key = os.getenv("ELEVEN_API_KEY")
#     client = ElevenLabs(api_key=api_key) if api_key else None

#     # --- CRITICAL FIX: Buffer Size ---
#     # PCM is uncompressed (heavy). 
#     # 1024 bytes = 11ms (Too small, causes lag).
#     # 8192 bytes = ~92ms (Perfect for streaming).
#     MIN_CHUNK_SIZE = 8192 
    
#     # Define Settings once
#     voice_settings = VoiceSettings(
#         stability=0.4, 
#         similarity_boost=0.5, 
#         style=0.0, 
#         use_speaker_boost=True,
#         speed=1.1, 
#     )

#     async for event in event_stream:
#         # 1. Pass Text Immediately
#         yield event

#         if client and event.type == "agent_chunk" and event.text and event.text.strip():
#             try:
#                 # 2. Convert to RAW PCM
#                 audio_stream = client.text_to_speech.convert(
#                     text=event.text,
#                     voice_id="21m00Tcm4TlvDq8ikWAM", 
#                     model_id="eleven_flash_v2_5",
#                     output_format="pcm_24000", # Raw numbers
#                     voice_settings=voice_settings,
#                 )
                
#                 # 3. Batching Logic
#                 buffer = b""
                
#                 for chunk in audio_stream:
#                     if chunk:
#                         buffer += chunk
                    
#                     # Wait until we have ~100ms of audio before sending
#                     if len(buffer) >= MIN_CHUNK_SIZE * 10:
#                         yield VoiceAgentEvent(type="tts_chunk", audio=buffer)
#                         buffer = b"" # Reset
                
#                 # Send remainder
#                 if len(buffer) > 0:
#                     yield VoiceAgentEvent(type="tts_chunk", audio=buffer)
                
#             except Exception as e:
#                 print(f"TTS ERROR: {e}")

import os
from typing import AsyncIterator
from google.cloud import texttospeech
from ChatBot.events import VoiceAgentEvent

async def tts_stream(event_stream: AsyncIterator[VoiceAgentEvent]) -> AsyncIterator[VoiceAgentEvent]:
    """
    Google Cloud TTS Implementation (Streaming-Compatible)
    """
    # 1. Initialize Client
    try:
        client = texttospeech.TextToSpeechAsyncClient()
    except Exception as e:
        print(f"Google TTS Client Error: {e}")
        client = None

    # Buffer settings: 8KB ~ 170ms of audio
    MIN_CHUNK_SIZE = 8192 

    # 2. Configuration
    # Voice: 'Journey' voices are the most realistic (Pro tier quality)
    # available in: en-US-Journey-D, F, O, etc.
    voice_params = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Neural2-F" # 'F' is a female voice, 'D' is male
    )

    # Audio Config: MATCHES YOUR FRONTEND (Raw PCM, 24kHz)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=24000, 
        speaking_rate=1.1 # 1.0 is normal, 1.1 is slightly faster
    )

    async for event in event_stream:
        # Pass through upstream events
        yield event

        # Process Agent Text (Sentences)
        if client and event.type == "agent_chunk" and event.text and event.text.strip():
            try:
                # print(f"DEBUG: 🗣️ Google TTS: '{event.text}'")
                
                # 3. Create Request
                input_text = texttospeech.SynthesisInput(text=event.text.replace('**', ' ').replace("\n"," "))
                
                # 4. Call API (Per sentence)
                # Note: Google's standard API is extremely fast (~200ms). 
                # We get the whole sentence audio at once.
                
                response = await client.synthesize_speech(
                    input=input_text,  # Remove markdown bold if present
                    voice=voice_params,
                    audio_config=audio_config
                )
                
                # 5. Get Raw Bytes
                raw_audio = response.audio_content
                
                # 6. Chunking Logic (To prevent flooding the frontend)
                # Even though we got the full sentence, we feed it to the
                # frontend in bite-sized pieces to keep the buffer logic happy.
                for i in range(0, len(raw_audio), MIN_CHUNK_SIZE):
                    chunk = raw_audio[i : i + MIN_CHUNK_SIZE]
                    yield VoiceAgentEvent(type="tts_chunk", audio=chunk)
                
            except Exception as e:
                print(f"GOOGLE TTS ERROR: {e}")