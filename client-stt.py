import socket
import struct
import os
import time
import subprocess
import logging
import speech_recognition as sr

SERVER_IP = "192.168.3.24"
SERVER_PORT = 5000
MIC_INDEX = 4  # Укажите верный индекс из find_mic.py
TTS_OUTPUT_FILE = "response.mp3"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

class VoiceClient:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 1000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.6

    def _play_audio(self):
        if not os.path.exists(TTS_OUTPUT_FILE):
            return
        try:
            subprocess.run(["mpg123", "-q", TTS_OUTPUT_FILE], check=True)
        except Exception as e:
            logging.error(f"Audio error: {e}")

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
            source = sr.Microphone(device_index=MIC_INDEX)
            with source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                logging.info("Ready")
                
                while True:
                    try:
                        audio = self.recognizer.listen(source)
                        wav_data = audio.get_wav_data()

                        sock.sendall(struct.pack('!I', len(wav_data)))
                        sock.sendall(wav_data)

                        header = self._recv_exact(sock, 4)
                        resp_len = struct.unpack('!I', header)[0]
                        
                        if resp_len > 0:
                            data = self._recv_exact(sock, resp_len)
                            text = data.decode('utf-8')
                            logging.info(f"Server: {text}")

                            cmd = ["edge-tts", "--text", text, "--voice", "ru-RU-DmitryNeural", "--write-media", TTS_OUTPUT_FILE]
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
                            self._play_audio()
                        
                    except (BrokenPipeError, ConnectionResetError):
                        sock.close()
                        sock = self._connect()
                    except Exception as e:
                        logging.error(e)
                        time.sleep(1)
        except OSError as e:
            logging.error(f"Mic Error: {e}")

if __name__ == "__main__":
    try:
        VoiceClient().run()
    except KeyboardInterrupt:
        pass