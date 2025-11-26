import socket
import json
import os
import sys
from vosk import Model, KaldiRecognizer

# --- КОНФИГУРАЦИЯ СЕРВЕРА ---
# Путь к БОЛЬШОЙ модели на ПК
MODEL_PATH = "vosk-model-ru-0.10" 
HOST = '0.0.0.0'  # Слушать на всех интерфейсах
PORT = 5000       # Порт для подключения

if not os.path.exists(MODEL_PATH):
    print(f"Model not found at {MODEL_PATH}")
    sys.exit(1)

print("Loading large model (this may take a few seconds)...")
model = Model(MODEL_PATH)
rec = KaldiRecognizer(model, 16000)

print(f"Server started. Listening on port {PORT}...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    
    while True:
        print("Waiting for Raspberry Pi connection...")
        conn, addr = s.accept()
        print(f"Connected by {addr}")
        
        with conn:
            while True:
                # Получаем аудиоданные (сырые байты) от Pi
                data = conn.recv(4000)
                if not data:
                    break
                
                # Обработка Vosk
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get('text', '').strip()
                    
                    if text:
                        print(f"Client said: {text}")
                        # ТУТ ОТПРАВЛЯЕМ ТЕКСТ В LLM
                        # llm_response = my_llm.generate(text)