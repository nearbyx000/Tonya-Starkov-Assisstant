import socket
import struct
import os
import wave
import whisper
from openai import OpenAI
from datetime import datetime

# --- CONFIGURATION ---
HOST = "0.0.0.0"
PORT = 5000
WHISPER_MODEL = "base"
# Вставьте ключ ниже, если он не задан в переменных среды
OPENAI_API_KEY = "sk-..."

# Аудио параметры (должны совпадать с клиентом!)
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 2 байта = 16 бит

SYSTEM_PROMPT = "Ты — голосовой ассистент Тоня. Отвечай кратко, по делу и с легким сарказмом."


class AIBackend:
    def __init__(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Загрузка модели Whisper ({WHISPER_MODEL})...")
        self.whisper_model = whisper.load_model(WHISPER_MODEL)
        self.gpt_client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] AI Backend готов.")

    def transcribe(self, audio_path):
        try:
            result = self.whisper_model.transcribe(audio_path, fp16=False)
            text = result.get("text", "").strip()
            return text
        except Exception as e:
            print(f"[ERROR] Whisper failed: {e}")
            return None

    def ask_gpt(self, text):
        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] OpenAI API failed: {e}")
            return "Произошла ошибка при обращении к серверу."


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
        print(f"Сервер запущен на {HOST}:{PORT}")

        while True:
            conn, addr = self.sock.accept()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Подключение: {addr[0]}")

            try:
                # 1. Получаем размер данных
                len_bytes = self._recv_exact(conn, 4)
                if not len_bytes: continue

                payload_size = struct.unpack('>I', len_bytes)[0]
                print(f"Прием {payload_size} байт аудио...")

                # 2. Получаем само аудио (RAW PCM)
                audio_data = self._recv_exact(conn, payload_size)
                if not audio_data: continue

                # 3. Сохраняем как валидный WAV
                temp_file = "temp_input.wav"
                with wave.open(temp_file, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(SAMPLE_WIDTH)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio_data)

                # 4. Распознавание
                transcript = self.ai.transcribe(temp_file)
                if not transcript:
                    print("Пустая транскрипция.")
                    self._send_response(conn, "Не удалось распознать речь.")
                    continue

                print(f"Запрос: {transcript}")

                # Команда выхода (опционально)
                if "выключись" in transcript.lower():
                    self._send_response(conn, "Отключаюсь.")
                    break

                # 5. GPT
                response_text = self.ai.ask_gpt(transcript)
                print(f"Ответ: {response_text}")

                # 6. Отправка ответа
                self._send_response(conn, response_text)

            except Exception as e:
                print(f"[ERROR] Loop error: {e}")
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
    backend = AIBackend()
    VoiceServer(backend).run()