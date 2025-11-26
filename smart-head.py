#!/usr/bin/env python3
import socket
import pyaudio
import subprocess
import sys
import select
import os

# --- КОНФИГУРАЦИЯ ---
# IP-адрес вашего ПК (Сервера)
PC_SERVER_IP = "192.168.3.10"
PC_SERVER_PORT = 5000

# Пути к файлам Piper
# Путь к исполняемому файлу (бинарнику), который вы скачали
PIPER_BINARY_PATH = "/home/pi/piper/piper"
# Путь к файлу модели голоса (.onnx)
PIPER_MODEL_PATH = "/home/pi/models/ru_RU-irina-medium.onnx"

# Настройки микрофона (Index 4 = PulseAudio, Index 10 = default)
INPUT_DEVICE_INDEX = 4

# Аудио параметры
CHUNK = 4000
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def speak_text(text: str):
    """
    Озвучивает текст через Piper + aplay.
    """
    if not text:
        return
    
    print(f"[TTS] Processing: {text}")
    
    # Проверка наличия бинарного файла piper
    if not os.path.exists(PIPER_BINARY_PATH):
        print(f"[Error] Piper binary not found at: {PIPER_BINARY_PATH}")
        print("Please download piper_linux_aarch64.tar.gz and extract it to /home/pi/")
        return

    try:
        # Используем полный путь к бинарному файлу piper
        piper_cmd = [PIPER_BINARY_PATH, '--model', PIPER_MODEL_PATH, '--output-raw']
        aplay_cmd = ['aplay', '-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-']
        
        p_piper = subprocess.Popen(piper_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p_aplay = subprocess.Popen(aplay_cmd, stdin=p_piper.stdout)
        
        p_piper.communicate(input=text.encode('utf-8'))
        p_aplay.wait()
        
    except Exception as e:
        print(f"[Error] TTS execution failed: {e}")

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
            print(f"[Error] Failed to open microphone (Index {INPUT_DEVICE_INDEX}): {e}")
            return
        
        while True:
            # 1. Чтение с микрофона и отправка на сервер
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                sock.sendall(data)
            except IOError:
                pass
            except BrokenPipeError:
                print("[Error] Connection to server lost.")
                break

            # 2. Проверка входящих данных (текстовый ответ от сервера)
            ready_to_read, _, _ = select.select([sock], [], [], 0.01)
            
            if ready_to_read:
                try:
                    response_data = sock.recv(4096)
                    if not response_data:
                        break
                    
                    text_answer = response_data.decode('utf-8')
                    print(f"[Server] Received: {text_answer}")
                    
                    # Приостановка микрофона, чтобы не слушать самого себя
                    stream.stop_stream()
                    
                    # Озвучивание ответа
                    speak_text(text_answer)
                    
                    # Возобновление работы микрофона
                    stream.start_stream()
                    print("[Mic] Listening again...")
                    
                except BlockingIOError:
                    pass
                except UnicodeDecodeError:
                    print("[Error] Failed to decode server response")

    except KeyboardInterrupt:
        print("\n[Exit] User interrupted.")
    except ConnectionRefusedError:
        print(f"[Error] Could not connect to {PC_SERVER_IP}. Is the server running?")
    except Exception as e:
        print(f"[Error] Critical failure: {e}")
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        sock.close()
        p.terminate()

if __name__ == "__main__":
    main()