import socket
import struct
import os
import time
import subprocess
import logging
import speech_recognition as sr
import pygame

# Configuration
SERVER_IP = "192.168.3.24"
SERVER_PORT = 5000
MIC_INDEX = 4
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
        self.recognizer.energy_threshold = 1000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.6
        self._init_mixer()

    def _init_mixer(self):
        try:
            pygame.mixer.init()
        except pygame.error as e:
            logging.error(f"Audio mixer init failed: {e}")

    def _generate_tts(self, text: str) -> bool:
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
        if not os.path.exists(TTS_OUTPUT_FILE):
            return
        
        try:
            pygame.mixer.music.load(TTS_OUTPUT_FILE)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logging.error(f"Playback error: {e}")

    def _connect(self) -> socket.socket:
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_IP, SERVER_PORT))
                logging.info(f"Connected to {SERVER_IP}:{SERVER_PORT}")
                return sock
            except OSError:
                logging.warning("Connection failed. Retrying in 3s...")
                time.sleep(3)

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                raise ConnectionResetError("Socket closed")
            data += packet
        return data

    def run(self):
        sock = self._connect()
        
        with sr.Microphone(device_index=MIC_INDEX) as source:
            logging.info("Calibrating background noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            logging.info("Listening...")
            
            while True:
                try:
                    # 1. Listen (Blocks until phrase ends)
                    audio = self.recognizer.listen(source)
                    wav_data = audio.get_wav_data()

                    # 2. Send
                    sock.sendall(struct.pack('!I', len(wav_data)))
                    sock.sendall(wav_data)

                    # 3. Receive header
                    header = self._recv_exact(sock, 4)
                    resp_len = struct.unpack('!I', header)[0]
                    
                    if resp_len > 0:
                        # 4. Receive text
                        data = self._recv_exact(sock, resp_len)
                        text = data.decode('utf-8')
                        logging.info(f"Response: {text}")

                        # 5. Playback (Blocks listening)
                        if self._generate_tts(text):
                            self._play_audio()
                            
                        logging.info("Listening again...")
                    else:
                        logging.info("Ignored.")

                except (BrokenPipeError, ConnectionResetError):
                    logging.warning("Reconnecting...")
                    sock.close()
                    sock = self._connect()
                except Exception as e:
                    logging.error(f"Error: {e}")
                    time.sleep(1)

if __name__ == "__main__":
    client = VoiceClient()
    try:
        client.run()
    except KeyboardInterrupt:
        pass