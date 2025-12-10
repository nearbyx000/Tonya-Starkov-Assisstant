import socket
import struct
import os
import time
import subprocess
import logging
import speech_recognition as sr

# --- CONFIG ---
SERVER_IP = "192.168.3.24"
SERVER_PORT = 5000
MIC_INDEX = 4  # PulseAudio

# Жесткие пути (созданные скриптом установки)
PIPER_BIN = "/home/pi/piper_tts/piper/piper"
PIPER_MODEL = "/home/pi/piper_tts/model.onnx"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

class VoiceClient:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 3000  # Высокий порог от шума
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = 0.8

    def _speak_piper(self, text: str):
        """Озвучка через локальный Piper (Без интернета)"""
        if not os.path.exists(PIPER_BIN):
            logging.error(f"Piper не найден по пути: {PIPER_BIN}")
            return

        try:
            # Piper генерирует raw audio -> aplay воспроизводит
            # Это конвейер (pipeline), работающий без временных файлов
            piper_cmd = [
                PIPER_BIN,
                "--model", PIPER_MODEL,
                "--output-raw"
            ]
            aplay_cmd = [
                "aplay",
                "-r", "22050",
                "-f", "S16_LE",
                "-t", "raw",
                "-q" # Тихий режим
            ]

            # Запускаем процесс озвучки
            p_piper = subprocess.Popen(
                piper_cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            # Передаем текст в Piper
            p_aplay = subprocess.Popen(aplay_cmd, stdin=p_piper.stdout)
            
            p_piper.communicate(input=text.encode('utf-8'))
            p_aplay.wait() # Ждем, пока договорит

        except Exception as e:
            logging.error(f"TTS Error: {e}")

    def _connect(self) -> socket.socket:
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_IP, SERVER_PORT))
                logging.info(f"Connected: {SERVER_IP}")
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
            with sr.Microphone(device_index=MIC_INDEX) as source:
                logging.info("Калибровка шума...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                logging.info("Система готова. Говорите.")
                
                while True:
                    try:
                        audio = self.recognizer.listen(source, timeout=None)
                        wav_data = audio.get_wav_data()
                        
                        # Отправка
                        sock.sendall(struct.pack('!I', len(wav_data)))
                        sock.sendall(wav_data)

                        # Прием
                        header = self._recv_exact(sock, 4)
                        resp_len = struct.unpack('!I', header)[0]
                        
                        if resp_len > 0:
                            data = self._recv_exact(sock, resp_len)
                            text = data.decode('utf-8')
                            logging.info(f"AI: {text}")

                            # Озвучка (Piper)
                            self._speak_piper(text)
                        
                    except (BrokenPipeError, ConnectionResetError):
                        logging.warning("Reconnecting...")
                        sock.close()
                        sock = self._connect()
                    except Exception as e:
                        logging.error(f"Loop error: {e}")
                        time.sleep(1)
        except OSError as e:
            logging.error(f"Mic Error: {e}")

if __name__ == "__main__":
    try:
        VoiceClient().run()
    except KeyboardInterrupt:
        pass