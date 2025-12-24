import socket
import struct
import os
import whisper
from openai import OpenAI
from datetime import datetime

# --- CONFIGURATION ---
HOST = "0.0.0.0"       # Слушаем все интерфейсы
PORT = 5000
WHISPER_MODEL = "base" # 'tiny', 'base', 'small', 'medium'
OPENAI_API_KEY = "sk-..." # ВСТАВЬТЕ ВАШ КЛЮЧ ЗДЕСЬ ИЛИ ИСПОЛЬЗУЙТЕ os.getenv

# System prompt sets the personality
SYSTEM_PROMPT = "Ты — голосовой ассистент Тоня. Отвечай кратко, по делу и с легким сарказмом."

class AIBackend:
    def __init__(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Загрузка модели Whisper ({WHISPER_MODEL})...")
        self.whisper_model = whisper.load_model(WHISPER_MODEL)

        # Инициализация клиента OpenAI (v1.0+)
        # Если ключ в ENV, аргумент api_key можно убрать
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
                model="gpt-4", # Или "gpt-3.5-turbo"
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
        """Гарантированное чтение n байт."""
        data = b''
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def run(self):
        print(f"Сервер запущен на {HOST}:{PORT}")

        while True:
            conn, addr = self.sock.accept()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Подключение: {addr[0]}")

            try:
                # 1. Читаем размер аудио (4 байта, big-endian)
                len_bytes = self._recv_exact(conn, 4)
                if not len_bytes:
                    continue

                payload_size = struct.unpack('>I', len_bytes)[0]
                print(f"Прием {payload_size} байт аудио...")

                # 2. Читаем аудио данные
                audio_data = self._recv_exact(conn, payload_size)
                if not audio_data:
                    continue

                # 3. Сохраняем во временный файл
                temp_file = "temp_input.wav"
                with open(temp_file, "wb") as f:
                    f.write(audio_data)

                # 4. Обработка (Speech -> Text)
                transcript = self.ai.transcribe(temp_file)
                if not transcript:
                    print("Пустая транскрипция.")
                    self._send_response(conn, "Не удалось распознать речь.")
                    continue

                print(f"Запрос: {transcript}")

                # 5. Обработка (Text -> AI -> Text)
                if "выключись" in transcript.lower(): # Пример простой команды
                    response_text = "Сервер завершает работу по команде."
                    self._send_response(conn, response_text)
                    break

                response_text = self.ai.ask_gpt(transcript)
                print(f"Ответ: {response_text}")

                # 6. Отправка ответа
                self._send_response(conn, response_text)

            except Exception as e:
                print(f"[ERROR] Connection loop: {e}")
            finally:
                conn.close()
                if os.path.exists("temp_input.wav"):
                    os.remove("temp_input.wav")

    def _send_response(self, conn, text):
        data = text.encode('utf-8')
        # Отправляем длину (4 байта) + сам текст
        conn.sendall(struct.pack('>I', len(data)) + data)

if __name__ == "__main__":
    # Сначала грузим тяжелые модели
    backend = AIBackend()
    # Запускаем сервер
    server = VoiceServer(backend)
    server.run()