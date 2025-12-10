import socket
import struct
import os
import time
import subprocess
import logging
import speech_recognition as sr
import pygame

# --- Configuration ---
SERVER_IP = "192.168.3.10"  # Укажите актуальный IP сервера
SERVER_PORT = 5000
MIC_INDEX = 4               # Индекс PulseAudio (обычно 4)
TTS_VOICE = "ru-RU-DmitryNeural"
TTS_OUTPUT_FILE = "response.mp3"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

class VoiceClient:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Настройки чувствительности VAD (Voice Activity Detection)
        self.recognizer.energy_threshold = 1000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.6  # Пауза для завершения фразы
        self._init_mixer()

    def _init_mixer(self):
        """Инициализация аудио-микшера для воспроизведения."""
        try:
            pygame.mixer.init()
        except pygame.error as e:
            logging.error(f"Audio mixer init failed: {e}")

    def _generate_tts(self, text: str) -> bool:
        """Генерация аудиофайла через edge-tts (cli)."""
        if os.path.exists(TTS_OUTPUT_FILE):
            os.remove(TTS_OUTPUT_FILE)
        
        cmd = [
            "edge-tts",
            "--text", text,
            "--voice", TTS_VOICE,
            "--write-media", TTS_OUTPUT_FILE
        ]
        try:
            subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL, 
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            logging.error("TTS generation failed.")
            return False

    def _play_audio(self):
        """Блокирующее воспроизведение аудио."""
        if not os.path.exists(TTS_OUTPUT_FILE):
            return
        
        try:
            pygame.mixer.music.load(TTS_OUTPUT_FILE)
            pygame.mixer.music.play()
            
            # Ждем окончания воспроизведения (Block thread)
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
        except Exception as e:
            logging.error(f"Playback error: {e}")

    def _connect(self) -> socket.socket:
        """Установка соединения с ретраями."""
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_IP, SERVER_PORT))
                logging.info(f"Connected to server {SERVER_IP}:{SERVER_PORT}")
                return sock
            except OSError:
                logging.warning("Connection failed. Retrying in 3s...")
                time.sleep(3)

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        """Чтение точного количества байт из сокета."""
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                raise ConnectionResetError("Socket closed during receive")
            data += packet
        return data

    def run(self):
        sock = self._connect()
        
        with sr.Microphone(device_index=MIC_INDEX) as source:
            logging.info("Calibrating background noise (Silence please)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            logging.info("Ready. Listening...")
            
            while True:
                try:
                    # 1. Захват аудио (VAD)
                    # listen блокирует поток до момента тишины
                    audio = self.recognizer.listen(source)
                    wav_data = audio.get_wav_data()
                    logging.info(f"Audio captured: {len(wav_data)} bytes")

                    # 2. Отправка данных
                    # Протокол: [Header 4 bytes (Size)] + [Payload]
                    sock.sendall(struct.pack('!I', len(wav_data)))
                    sock.sendall(wav_data)

                    # 3. Ожидание заголовка ответа
                    header = self._recv_exact(sock, 4)
                    resp_len = struct.unpack('!I', header)[0]
                    
                    if resp_len > 0:
                        # 4. Чтение тела ответа (текст)
                        data = self._recv_exact(sock, resp_len)
                        text = data.decode('utf-8')
                        logging.info(f"Server response: {text}")

                        # 5. Озвучка (Блокирующая)
                        # Микрофон не слушает, пока идет этот блок
                        if self._generate_tts(text):
                            self._play_audio()
                            
                        logging.info("Listening again...")
                    else:
                        logging.info("Ignored (Empty response)")

                except (BrokenPipeError, ConnectionResetError):
                    logging.warning("Connection lost. Reconnecting...")
                    sock.close()
                    sock = self._connect()
                except Exception as e:
                    logging.error(f"Runtime error: {e}")
                    # Небольшая пауза перед повтором, чтобы не спамить ошибками
                    time.sleep(1)

if __name__ == "__main__":
    client = VoiceClient()
    try:
        client.run()
    except KeyboardInterrupt:
        logging.info("Client stopped by user.")