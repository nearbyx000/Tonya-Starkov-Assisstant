import socket
import json
import os
import sys
from vosk import Model, KaldiRecognizer
from openai import OpenAI

# --- КОНФИГУРАЦИЯ ---
# Путь к большой модели Vosk на ПК
VOSK_MODEL_PATH = "vosk-model-ru-0.10"
HOST = '0.0.0.0'
PORT = 5000

# Настройка клиента OpenAI для LM Studio
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

SYSTEM_PROMPT = "Ты — голосовой ассистент. Отвечай кратко, на русском языке. Не используй markdown и списки."

def ask_llm(text):
    print(f"[LLM] Request: {text}")
    try:
        completion = client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=200,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[Error] LLM request failed: {e}")
        return "Ошибка обработки запроса."

# Проверка наличия модели
if not os.path.exists(VOSK_MODEL_PATH):
    print(f"[Error] Model not found at: {VOSK_MODEL_PATH}")
    sys.exit(1)

print("[Init] Loading Vosk model...")
model = Model(VOSK_MODEL_PATH)
rec = KaldiRecognizer(model, 16000)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"[Server] Listening on port {PORT}")

    while True:
        print("[Server] Waiting for connection...")
        conn, addr = s.accept()
        print(f"[Server] Connected by {addr}")

        with conn:
            conn.setblocking(False)
            while True:
                try:
                    data = conn.recv(4000)
                    if not data:
                        break
                    
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get('text', '').strip()
                        
                        # Фильтр коротких фраз (шума)
                        if len(text) > 2:
                            print(f"[User] {text}")
                            
                            # Запрос к нейросети
                            answer = ask_llm(text)
                            print(f"[Assistant] {answer}")
                            
                            # Отправка ответа клиенту
                            if answer:
                                conn.sendall(answer.encode('utf-8'))
                            
                except BlockingIOError:
                    continue
                except ConnectionResetError:
                    print("[Server] Connection reset by client")
                    break
                except Exception as e:
                    print(f"[Error] {e}")
                    break