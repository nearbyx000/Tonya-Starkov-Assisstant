#!/usr/bin/env python3
import socket
import pyaudio
import subprocess
import sys
import select
import os

# --- КОНФИГУРАЦИЯ ---
PC_SERVER_IP = "192.168.3.10"
PC_SERVER_PORT = 5000

# Голос (можно менять). Варианты:
# ru-RU-SvetlanaNeural (Женский, строгий)
# ru-RU-DmitryNeural (Мужской, спокойный)
VOICE = "ru-RU-SvetlanaNeural"

# Настройки микрофона
INPUT_DEVICE_INDEX = 4
CHUNK = 4000
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def speak_text(text: str):
    """
    Озвучивает текст через Edge-TTS (Online) + mpg123.
    """
    if not text:
        return
    
    print(f"[TTS] Generating: {text}")
    
    # Файл для временного сохранения звука
    output_file = "/tmp/voice_response.mp3"
    
    try:
        # 1. Генерируем аудио файл через Edge-TTS
        # Используем subprocess для вызова команды терминала
        subprocess.run(
            ["edge-tts", "--text", text, "--voice", VOICE, "--write-media", output_file],
            check=True
        )
        
        # 2. Воспроизводим файл через mpg123
        subprocess.run(
            ["mpg123", "-q", output_file], # -q чтобы не мусорил в логи
            check=True
        )
        
    except subprocess.CalledProcessError as e:
        print(f"[Error] TTS failed: {e}")
    except FileNotFoundError:
        print("[Error] 'edge-tts' or 'mpg123' not found. Install them first.")

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
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                sock.sendall(data)
            except IOError:
                pass
            except BrokenPipeError:
                print("[Error] Connection lost.")
                break

            ready_to_read, _, _ = select.select([sock], [], [], 0.01)
            
            if ready_to_read:
                try:
                    response_data = sock.recv(4096)
                    if not response_data:
                        break
                    
                    text_answer = response_data.decode('utf-8')
                    print(f"[Server] Received: {text_answer}")
                    
                    # Стоп микрофон
                    stream.stop_stream()
                    
                    # Озвучка (Online)
                    speak_text(text_answer)
                    
                    # Старт микрофон
                    stream.start_stream()
                    print("[Mic] Listening...")
                    
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