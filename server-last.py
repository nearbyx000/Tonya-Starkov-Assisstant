import socket
import struct
import os
import wave
import whisper
from openai import OpenAI
from datetime import datetime

HOST = "0.0.0.0"
PORT = 5000
WHISPER_MODEL = "base"
LM_STUDIO_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
SYSTEM_PROMPT = "Ты — голосовой ассистент Тоня. Отвечай на русском языке. Будь кратка и саркастична."


class AIBackend:
    def __init__(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading Whisper ({WHISPER_MODEL})...")
        self.whisper_model = whisper.load_model(WHISPER_MODEL)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to LM Studio ({LM_STUDIO_URL})...")
        self.gpt_client = OpenAI(
            base_url=LM_STUDIO_URL,
            api_key=LM_STUDIO_API_KEY
        )
        print(f"[{datetime.now().strftime('%H:%M:%S')}] AI Backend ready.")

    def transcribe(self, audio_path):
        try:
            result = self.whisper_model.transcribe(audio_path, fp16=False, language='ru')
            return result.get("text", "").strip()
        except Exception as e:
            print(f"[ERROR] Whisper failed: {e}")
            return None

    def ask_gpt(self, text):
        try:
            response = self.gpt_client.chat.completions.create(
                model="local-model",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] LM Studio connection failed: {e}")
            return "Ошибка связи с локальной нейросетью."


class VoiceServer:
    def __init__(self, ai_backend):
        self.ai = ai_backend
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST, PORT))
        self.sock.listen(1)

    def _recv_exact(self, conn, n):
        data = b''
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet: return None
            data += packet
        return data

    def run(self):
        print(f"Server running on {HOST}:{PORT}")

        while True:
            conn, addr = self.sock.accept()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Connected: {addr[0]}")

            try:
                len_bytes = self._recv_exact(conn, 4)
                if not len_bytes: continue

                payload_size = struct.unpack('>I', len_bytes)[0]
                print(f"Receiving {payload_size} bytes...")

                audio_data = self._recv_exact(conn, payload_size)
                if not audio_data: continue

                temp_file = "temp_input.wav"
                with wave.open(temp_file, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(SAMPLE_WIDTH)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio_data)

                transcript = self.ai.transcribe(temp_file)
                if not transcript:
                    print("Empty transcript.")
                    self._send_response(conn, "Не расслышала.")
                    continue

                print(f"Query: {transcript}")

                if "выключись" in transcript.lower():
                    self._send_response(conn, "Отключаюсь.")
                    break

                response_text = self.ai.ask_gpt(transcript)
                print(f"Response: {response_text}")

                self._send_response(conn, response_text)

            except Exception as e:
                print(f"[ERROR] Processing loop: {e}")
            finally:
                conn.close()
                if os.path.exists("temp_input.wav"):
                    try:
                        os.remove("temp_input.wav")
                    except:
                        pass

    def _send_response(self, conn, text):
        data = text.encode('utf-8')
        try:
            conn.sendall(struct.pack('>I', len(data)) + data)
        except Exception as e:
            print(f"[ERROR] Send failed: {e}")


if __name__ == "__main__":
    try:
        backend = AIBackend()
        VoiceServer(backend).run()
    except KeyboardInterrupt:
        print("\nServer stopped.")