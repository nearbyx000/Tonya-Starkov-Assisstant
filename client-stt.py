import socket
import pyaudio
import sys

# --- КОНФИГУРАЦИЯ КЛИЕНТА ---
SERVER_IP = '192.168.3.12' # <--- ВСТАВЬТЕ IP ВАШЕГО МОЩНОГО ПК
SERVER_PORT = 5000
INPUT_DEVICE_INDEX = 4     # Ваш индекс микрофона (pulse)

# Настройки аудио (должны совпадать с сервером)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 4000

p = pyaudio.PyAudio()

try:
    # 1. Подключение к серверу
    print(f"Connecting to server {SERVER_IP}:{SERVER_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))
    print("Connected successfully.")

    # 2. Открытие микрофона
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=INPUT_DEVICE_INDEX)
    
    print("Microphone active. Streaming audio...")

    # 3. Передача данных
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            sock.sendall(data)
        except IOError as e:
            print(f"Audio error: {e}")
            continue
        except BrokenPipeError:
            print("Server disconnected.")
            break

except ConnectionRefusedError:
    print("Could not connect to server. Is it running?")
except KeyboardInterrupt:
    print("\nStopped by user.")
finally:
    if 'stream' in locals():
        stream.stop_stream()
        stream.close()
    if 'sock' in locals():
        sock.close()
    p.terminate()