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
MIC_INDEX = 4  # PulseAudio

# Сменили голос на Светлану (более стабильный API)
TTS_VOICE = "ru-RU-SvetlanaNeural" 
TTS_OUTPUT_FILE = "response.mp3"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

class VoiceClient:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # ПОДНЯЛИ ПОРОГ: Теперь микрофон не будет реагировать на шорохи и шум
        self.recognizer.energy_threshold = 3000 
        self.recognizer.dynamic_energy_threshold = False # Откл автоподстройку, чтобы не ловил тишину
        self.recognizer.pause_threshold = 1.0

    def _play_audio(self):
        if not os.path.exists(TTS_OUTPUT_FILE):
            logging.error("Файл аудио не создан (ошибка TTS)")
            return
        
        try:
            # -q : тихий режим
            subprocess.run(["mpg123", "-q", TTS_OUTPUT_FILE], check=True)
        except Exception as e:
            logging.error(f"Ошибка плеера: {e}")

    def _generate_tts(self, text: str):
        # Удаляем старый файл
        if os.path.exists(TTS_OUTPUT_FILE):
            os.remove(TTS_OUTPUT_FILE)

        cmd = [
            "edge-tts",
            "--text", text,
            "--voice", TTS_VOICE,
            "--write-media", TTS_OUTPUT_FILE
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Ошибка Edge-TTS: Возможно, проблемы с интернетом или API Microsoft.")

    def _connect(self) -> socket.socket:
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_IP, SERVER_PORT))
                logging.info(f"Подключено к {SERVER_IP}")
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
            source = sr.Microphone(device_index=MIC_INDEX)
            with source:
                logging.info("Калибровка... (Тишина)")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logging.info("Готов. Говорите громко и четко.")
                
                while True:
                    try:
                        # Слушаем
                        audio = self.recognizer.listen(source, timeout=None)
                        wav_data = audio.get_wav_data()
                        logging.info("Фраза записана. Отправка...")

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
                            logging.info(f"Ответ: {text}")

                            # Озвучка
                            self._generate_tts(text)
                            self._play_audio()
                            
                            logging.info("Жду следующую фразу...")
                        else:
                            logging.info("Пустой ответ (шум).")

                    except (BrokenPipeError, ConnectionResetError):
                        logging.warning("Реконнект...")
                        sock.close()
                        sock = self._connect()
                    except Exception as e:
                        logging.error(f"Сбой цикла: {e}")
                        time.sleep(1)
        except OSError as e:
            logging.error(f"Ошибка инициализации микрофона: {e}")

if __name__ == "__main__":
    try:
        VoiceClient().run()
    except KeyboardInterrupt:
        pass