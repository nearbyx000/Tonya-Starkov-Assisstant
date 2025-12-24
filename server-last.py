"""
Improved Server for Tonya-Starkov Assistant
- Whisper STT (much better than Vosk)
- GPU acceleration
- Better error handling
"""

import socket
import numpy as np
import whisper
import openai
from datetime import datetime
import tempfile
import wave

# Configuration
HOST = "0.0.0.0"
PORT = 5000
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit audio

# LM Studio settings
LM_STUDIO_URL = "http://localhost:1234/v1"
openai.api_base = LM_STUDIO_URL
openai.api_key = "not-needed"

# Memory settings
HISTORY_LIMIT = 10
conversation_history = []

# System prompt optimized for TTS (English)
SYSTEM_PROMPT_EN = """Role: You are Tonya Starkov, a helpful AI assistant. Your text will be converted to speech.

Rules for TTS-optimized responses:
1. Answer First: Start with 1-2 sentence summary, then expand in short paragraphs
2. Sentence Design: Keep sentences concise with simple punctuation
3. Readability: Expand abbreviations, write numbers in full words when needed
4. URLs: Say "link to site name" instead of full URLs
5. Emphasis: Highlight one key point per section naturally
6. Clarity: Define specialized terms briefly on first mention
7. Boundaries: Never invent facts, present alternatives if uncertain, end cleanly

Personality: Smart, friendly, helpful. Answer concisely with occasional humor."""

# System prompt optimized for TTS (Russian)
SYSTEM_PROMPT_RU = """Роль: Ты Тоня Старков, полезный ИИ-ассистент. Твой текст будет озвучен.

Правила для оптимизации под TTS:
1. Сначала ответ: Начинай с краткого резюме в 1-2 предложения, затем расширяй короткими абзацами
2. Структура предложений: Делай предложения краткими с простой пунктуацией
3. Читаемость: Расшифровывай аббревиатуры, пиши числа словами когда нужна ясность
4. Ссылки: Говори "ссылка на название сайта" вместо полных URL
5. Акценты: Выделяй одну ключевую мысль в секции естественно
6. Ясность: Кратко объясняй специальные термины при первом упоминании
7. Границы: Никогда не выдумывай факты, предлагай альтернативы если не уверен, заканчивай чётко

Личность: Умная, дружелюбная, полезная. Отвечай кратко с лёгким юмором."""

# Choose language
SYSTEM_PROMPT = SYSTEM_PROMPT_RU  # Change to SYSTEM_PROMPT_EN for English

# Recommended models for RTX 4070 12GB:
# 1. Qwen/Qwen2.5-14B-Instruct-Q4_K_M (Best balance)
# 2. mistralai/Mistral-Small-3-7B-Instruct-Q4_K_M (Fastest)
# 3. meta-llama/Llama-3.1-8B-Instruct-Q4_K_M (Most popular)
# Load in LM Studio with Q4_K_M quantization


# Whisper Model
print("Loading Whisper model...")
whisper_model = whisper.load_model("base")  # Options: tiny, base, small, medium, large
print("Whisper loaded!")


# Server Class
class BrainServer:
    """Server with Whisper STT"""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST, PORT))
        self.sock.listen(5)
        print(f"Server listening on {HOST}:{PORT}")

    def transcribe_audio(self, audio_bytes):
        """Transcribe audio using Whisper"""
        try:
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name

                # Write WAV file
                with wave.open(tmp_path, 'wb') as wav_file:
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(SAMPLE_WIDTH)
                    wav_file.setframerate(SAMPLE_RATE)
                    wav_file.writeframes(audio_bytes)

            # Transcribe with Whisper
            print("Transcribing with Whisper...")
            result = whisper_model.transcribe(
                tmp_path,
                language="ru",
                fp16=False  # Set True if you have GPU
            )

            text = result["text"].strip()
            print(f"Recognized: {text}")

            return text

        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    def get_ai_response(self, user_text):
        """Get response from LLM"""
        global conversation_history

        try:
            # Add user message to history
            conversation_history.append({
                "role": "user",
                "content": user_text
            })

            # Keep only recent messages
            if len(conversation_history) > HISTORY_LIMIT * 2:
                conversation_history = conversation_history[-HISTORY_LIMIT * 2:]

            # Prepare messages
            messages = [
                           {"role": "system", "content": SYSTEM_PROMPT}
                       ] + conversation_history

            print("Thinking...")

            # Call LLM
            response = openai.ChatCompletion.create(
                model="local-model",  # LM Studio ignores this
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )

            assistant_text = response.choices[0].message.content.strip()

            # Add to history
            conversation_history.append({
                "role": "assistant",
                "content": assistant_text
            })

            print(f"Response: {assistant_text}")

            return assistant_text

        except Exception as e:
            print(f"LLM error: {e}")
            return "Извини, произошла ошибка. Попробуй еще раз."

    def handle_client(self, client_socket):
        """Handle incoming client connection"""
        try:
            # Receive audio size
            size_bytes = client_socket.recv(4)
            if not size_bytes:
                return

            audio_size = int.from_bytes(size_bytes, 'big')
            print(f"Receiving {audio_size} bytes...")

            # Receive audio data
            audio_data = b''
            while len(audio_data) < audio_size:
                chunk = client_socket.recv(min(4096, audio_size - len(audio_data)))
                if not chunk:
                    break
                audio_data += chunk

            print(f"Received {len(audio_data)} bytes")

            # Transcribe
            text = self.transcribe_audio(audio_data)

            if text and len(text) > 2:
                # Get AI response
                response = self.get_ai_response(text)
            else:
                response = "Я не расслышал. Повтори, пожалуйста."

            # Send response
            response_bytes = response.encode('utf-8')
            client_socket.sendall(len(response_bytes).to_bytes(4, 'big'))
            client_socket.sendall(response_bytes)

            print("Response sent\n")

        except Exception as e:
            print(f"Client error: {e}")

        finally:
            client_socket.close()

    def run(self):
        """Main server loop"""
        print("=" * 50)
        print("Tonya-Starkov Brain Server (IMPROVED)")
        print("=" * 50)
        print(f"STT: Whisper (base model)")
        print(f"LLM: LM Studio @ {LM_STUDIO_URL}")
        print("=" * 50)
        print("Waiting for connections...\n")

        while True:
            try:
                client_socket, addr = self.sock.accept()
                print(f"Connected: {addr}")
                self.handle_client(client_socket)

            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"Error: {e}")

        self.sock.close()


# Main
if __name__ == "__main__":
    # Check if LM Studio is running
    try:
        openai.Model.list()
        print("LM Studio is running\n")
    except:
        print("WARNING: LM Studio not detected!")
        print("Make sure LM Studio is running on port 1234\n")

    server = BrainServer()
    server.run()