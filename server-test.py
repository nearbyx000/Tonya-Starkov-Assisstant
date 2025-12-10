import socket
import struct
import io
import os
import traceback
import torch
import torchaudio
from faster_whisper import WhisperModel
from openai import OpenAI

HOST = "0.0.0.0"
PORT = 5000
LLM_URL = "http://localhost:1234/v1"
LLM_KEY = "lm-studio"
TTS_SPEAKER = "aidar" 
SAMPLE_RATE = 48000

print(f"--- ЗАПУСК СЕРВЕРА ---")

try:
    print(f"[1/4] Проверка GPU...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"      Устройство: {device}")

    print(f"[2/4] Загрузка Whisper ({device})...")
    # Используем int8 для скорости
    stt_model = WhisperModel("medium", device=device, compute_type="int8")

    print(f"[3/4] Загрузка Silero TTS ({device})...")
    # Скачивание модели локально
    local_file = 'model.pt'
    if not os.path.isfile(local_file):
        torch.hub.download_url_to_file('https://models.silero.ai/models/tts/ru/v4_ru.pt', local_file)  
    
    tts_model = torch.package.PackageImporter(local_file).load_pickle("tts_models", "model")
    tts_model.to(torch.device(device))

    print(f"[4/4] Подключение к LLM...")
    llm_client = OpenAI(base_url=LLM_URL, api_key=LLM_KEY)
    
    # Тестовый запрос к LLM для проверки
    llm_client.models.list()
    
    print(">>> СИСТЕМА ГОТОВА. ЖДУ ПОДКЛЮЧЕНИЯ.")

except Exception:
    print("!!! ОШИБКА ПРИ ЗАГРУЗКЕ МОДЕЛЕЙ !!!")
    traceback.print_exc()
    os._exit(1)

history = []

def process_audio(audio_data):
    global history
    try:
        # STT
        with open("temp.wav", "wb") as f:
            f.write(audio_data)
        
        segments, _ = stt_model.transcribe("temp.wav", language="ru", beam_size=5)
        text = " ".join([s.text for s in segments]).strip()
        
        if os.path.exists("temp.wav"): os.remove("temp.wav")
        if not text or len(text) < 2: return None

        print(f"User: {text}")

        # LLM
        history.append({"role": "user", "content": text})
        history = history[-10:]
        
        completion = llm_client.chat.completions.create(
            model="local-model", messages=history, temperature=0.7, max_tokens=256
        )
        answer = completion.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        print(f"AI:   {answer}")

        # TTS
        audio_tensor = tts_model.apply_tts(text=answer, speaker=TTS_SPEAKER, sample_rate=SAMPLE_RATE)
        
        buffer = io.BytesIO()
        torchaudio.save(buffer, audio_tensor.unsqueeze(0), SAMPLE_RATE, format="wav")
        return buffer.getvalue()

    except Exception as e:
        print(f"Ошибка обработки: {e}")
        traceback.print_exc()
        return None

def recv_all(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet: return None
        data += packet
    return data

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        
        while True:
            conn, addr = s.accept()
            print(f"\n[+] Клиент подключен: {addr[0]}")
            
            with conn:
                while True:
                    try:
                        # 1. Читаем длину (4 байта)
                        header = recv_all(conn, 4)
                        if not header: break
                        size = struct.unpack('!I', header)[0]
                        
                        # 2. Читаем аудио
                        data = recv_all(conn, size)
                        if not data: break
                        
                        # 3. Обработка
                        response_wav = process_audio(data)
                        
                        # 4. Отправка ответа
                        if response_wav:
                            conn.sendall(struct.pack('!I', len(response_wav)))
                            conn.sendall(response_wav)
                        else:
                            # Пустой ответ (чтобы разблокировать клиента)
                            conn.sendall(struct.pack('!I', 0))
                            
                    except ConnectionResetError:
                        break
                    except Exception as e:
                        print(f"Сетевая ошибка: {e}")
                        break
            print("[-] Клиент отключен")

if __name__ == "__main__":
    main()