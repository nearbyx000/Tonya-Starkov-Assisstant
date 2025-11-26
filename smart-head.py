#!/usr/bin/env python3
import socket
import pyaudio
import subprocess
import sys
import select
import os
import time  # Добавили библиотеку времени

# --- КОНФИГУРАЦИЯ ---
PC_SERVER_IP = "192.168.3.10"
PC_SERVER_PORT = 5000

# Голос: ru-RU-DmitryNeural или ru-RU-SvetlanaNeural
VOICE = "ru-RU-DmitryNeural"

# Настройки микрофона
INPUT_DEVICE_INDEX = 4
CHUNK = 4000
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def speak_text(text: str):
    """
    Озвучивает текст через Edge-TTS + mpg123.
    """
    if not text:
        return
    
    print(f"[TTS] Generating: {text}")
    output_file = "/tmp/voice_response.mp3"
    
    try:
        subprocess.run(
            ["edge-tts", "--text", text, "--voice", VOICE, "--write-media", output_file],
            check=True
        )
        subprocess.run(
            ["mpg123", "-q", output_file],
            check=True
        )
    except Exception as e:
        print(f"[Error] TTS failed: {e}")

def main():
    print(f"[Init] Connecting to Server at {PC_SERVER_IP}:{PC_SERVER_PORT}...")
    
    p = pyaudio.PyAudio()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.connect((PC_SERVER_IP, PC_SERVER_PORT))
        sock.setblocking(False)
        print("[Network] Connected successfully.")

        try:
            stream = p.open(format=FORMAT, 
                            channels=CHANNELS, 
                            rate=RATE, 
                            input=True,
                            frames_per_buffer=CHUNK, 
                            input_device_index=INPUT_DEVICE_INDEX)
            print("[Mic] Microphone active. Streaming audio...")
        except Exception as e:
            print(f"[Error] Failed to open microphone: {e}")
            return
        
        while True:
            # 1. Читаем микрофон
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                sock.sendall(data)
            except IOError:
                pass
            except BrokenPipeError:
                print("[Error] Connection lost.")
                break

            # 2. Проверяем входящие данные от сервера
            ready_to_read, _, _ = select.select([sock], [], [], 0.01)
            
            if ready_to_read:
                try:
                    response_data = sock.recv(4096)
                    if not response_data:
                        break
                    
                    text_answer = response_data.decode('utf-8')
                    print(f"[Server] Received: {text_answer}")
                    
                    # --- БЛОКИРОВКА СЛУХА НАЧАЛАСЬ ---
                    
                    # 1. Полностью останавливаем поток записи
                    stream.stop_stream()
                    
                    # 2. Озвучиваем ответ
                    speak_text(text_answer)
                    
                    # 3. Добавляем небольшую паузу (0.5 сек), чтобы эхо в комнате утихло
                    time.sleep(0.5)
                    
                    # 4. Возобновляем поток
                    stream.start_stream()
                    
                    # 5. ВАЖНО: Очистка буфера (Flush)
                    # Читаем и выбрасываем мусор, который мог попасть в буфер
                    # пока мы включали микрофон. Сбрасываем примерно 1 секунду аудио.
                    print("[Mic] Flushing buffer...")
                    for _ in range(int(RATE / CHUNK * 1.0)):
                        stream.read(CHUNK, exception_on_overflow=False)
                    
                    # --- БЛОКИРОВКА СЛУХА ЗАКОНЧИЛАСЬ ---
                    
                    print("[Mic] Listening again...")
                    
                except BlockingIOError:
                    pass
                except UnicodeDecodeError:
                    print("[Error] Decode error")

    except KeyboardInterrupt:
        print("\n[Exit] Stopped.")
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        sock.close()
        p.terminate()

if __name__ == "__main__":
    main()