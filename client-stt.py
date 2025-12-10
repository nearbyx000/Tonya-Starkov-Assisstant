import socket
import struct
import os
import time
import subprocess
import logging
import speech_recognition as sr

# --- КОНФИГУРАЦИЯ ---
SERVER_IP = "192.168.3.24"
SERVER_PORT = 5000

# Используем PulseAudio (исходя из вашего скриншота check-mic)
MIC_INDEX = 4 

TTS_OUTPUT_FILE = "response.mp3"
TTS_VOICE = "ru-RU-DmitryNeural"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

class VoiceClient:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Чувствительность. Если микрофон ловит шум как "попа", увеличивайте это число (до 3000-4000)
        self.recognizer.energy_threshold = 1000 
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0 # Ждать 1 сек тишины перед отправкой

    def _play_audio(self):
        if not os.path.exists(TTS_OUTPUT_FILE):
            logging.error("Файл озвучки не найден!")
            return
        
        logging.info("Воспроизведение звука...")
        try:
            # Используем mpg123 с явным указанием PulseAudio (иногда помогает -a)
            # Если не будет звука, уберите '-o', 'pulse'
            subprocess.run(["mpg123", "-q", TTS_OUTPUT_FILE], check=True)
        except Exception as e:
            logging.error(f"Ошибка воспроизведения: {e}")

    def _connect(self) -> socket.socket:
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_IP, SERVER_PORT))
                logging.info(f"Успешное подключение к {SERVER_IP}")
                return sock
            except OSError:
                time.sleep(3)

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                raise ConnectionResetError
            data += packet
        return data

    def run(self):
        sock = self._connect()
        try:
            # Явно указываем микрофон
            source = sr.Microphone(device_index=MIC_INDEX)
            
            with source:
                logging.info("Калибровка шума (помолчите 2 сек)...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                logging.info(f"Готов! Слушаю через устройство {MIC_INDEX}...")
                
                while True:
                    try:
                        # Слушаем
                        audio = self.recognizer.listen(source, timeout=None)
                        wav_data = audio.get_wav_data()
                        logging.info(f"Записано {len(wav_data)} байт. Отправка...")

                        # Отправка
                        sock.sendall(struct.pack('!I', len(wav_data)))
                        sock.sendall(wav_data)

                        # Прием заголовка
                        header = self._recv_exact(sock, 4)
                        resp_len = struct.unpack('!I', header)[0]
                        
                        if resp_len > 0:
                            # Прием текста
                            data = self._recv_exact(sock, resp_len)
                            text = data.decode('utf-8')
                            logging.info(f"Ответ сервера: {text}")

                            # Генерация TTS
                            cmd = ["edge-tts", "--text", text, "--voice", TTS_VOICE, "--write-media", TTS_OUTPUT_FILE]
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
                            
                            # Воспроизведение
                            self._play_audio()
                            logging.info("Слушаю снова...")
                        else:
                            logging.info("Сервер прислал пустой ответ (игнорирую).")
                        
                    except (BrokenPipeError, ConnectionResetError):
                        logging.warning("Связь потеряна. Реконнект...")
                        sock.close()
                        sock = self._connect()
                    except Exception as e:
                        logging.error(f"Ошибка цикла: {e}")
                        time.sleep(1)
        except OSError as e:
            logging.error(f"Ошибка микрофона: {e}")
            logging.error("Попробуйте изменить MIC_INDEX на 10 (default)")

if __name__ == "__main__":
    try:
        VoiceClient().run()
    except KeyboardInterrupt:
        pass