#!/usr/bin/env python3
import socket
import pyaudio
import subprocess
import sys
import select

# --- КОНФИГУРАЦИЯ ---
# Укажите IP вашего ПК
PC_SERVER_IP = "192.168.3.10"
PC_SERVER_PORT = 5000

# Пути и настройки аудио
PIPER_MODEL_PATH = "/home/pi/models/ru_RU-irina-medium.onnx"
INPUT_DEVICE_INDEX = 4  # Используйте индекс из check_mic.py (обычно 4 для pulse)

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
    print(f"[TTS] Speaking: {text}")
    try:
        piper_cmd = ['piper', '--model', PIPER_MODEL_PATH, '--output-raw']
        aplay_cmd = ['aplay', '-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-']
        
        p_piper = subprocess.Popen(piper_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p_aplay = subprocess.Popen(aplay_cmd, stdin=p_piper.stdout)
        
        p_piper.communicate(input=text.encode('utf-8'))
        p_aplay.wait()
    except Exception as e:
        print(f"[Error] TTS failed: {e}")

def main():
    print(f"[Init] Connecting to {PC_SERVER_IP}:{PC_SERVER_PORT}...")
    
    p = pyaudio.PyAudio()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.connect((PC_SERVER_IP, PC_SERVER_PORT))
        sock.setblocking(False)
        print("[Network] Connected successfully.")

        stream = p.open(format=FORMAT, 
                        channels=CHANNELS, 
                        rate=RATE, 
                        input=True,
                        frames_per_buffer=CHUNK, 
                        input_device_index=INPUT_DEVICE_INDEX)
        
        print("[Mic] Microphone active. Streaming...")
        
        while True:
            # 1. Чтение с микрофона и отправка
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                sock.sendall(data)
            except IOError:
                pass
            except BrokenPipeError:
                print("[Error] Connection to server lost.")
                break

            # 2. Проверка входящих данных (текст от сервера)
            ready_to_read, _, _ = select.select([sock], [], [], 0.01)
            
            if ready_to_read:
                try:
                    response_data = sock.recv(4096)
                    if not response_data:
                        break
                    
                    text_answer = response_data.decode('utf-8')
                    print(f"[Server] Received: {text_answer}")
                    
                    # ПРИОСТАНОВКА МИКРОФОНА
                    stream.stop_stream()
                    
                    # ОЗВУЧКА
                    speak_text(text_answer)
                    
                    # ВОЗОБНОВЛЕНИЕ МИКРОФОНА
                    stream.start_stream()
                    print("[Mic] Listening again...")
                    
                except BlockingIOError:
                    pass
                except UnicodeDecodeError:
                    print("[Error] Failed to decode server response")

    except KeyboardInterrupt:
        print("\n[Exit] User interrupted.")
    except ConnectionRefusedError:
        print("[Error] Connection refused. Is the server running?")
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