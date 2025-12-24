import socket
import asyncio
import subprocess
import time
import os
import contextlib
import numpy as np
import pyaudio
import noisereduce as nr
import webrtcvad
import edge_tts
from scipy import signal
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll

CONFIG = {
    'SERVER_IP': "192.168.3.115",
    'SERVER_PORT': 5000,
    'VOICE': "ru-RU-DmitryNeural",
    'RATE': 16000,
    'CHUNK': 1024,
    'DURATION': 5,
    'VAD_LEVEL': 2,
    'HP_FREQ': 300
}


@contextlib.contextmanager
def ignore_alsa_warnings():
    handler = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)(lambda *args: None)
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(handler)
    yield
    asound.snd_lib_error_set_handler(None)


class AudioProcessor:
    def __init__(self, rate):
        self.rate = rate
        self.vad = webrtcvad.Vad(CONFIG['VAD_LEVEL'])
        self.sos = signal.butter(4, CONFIG['HP_FREQ'], 'hp', fs=rate, output='sos')

    def clean(self, raw_bytes):
        audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if (max_val := np.max(np.abs(audio))) > 0:
            audio /= max_val
        audio = signal.sosfilt(self.sos, audio)
        try:
            audio = nr.reduce_noise(y=audio, sr=self.rate, stationary=True, prop_decrease=0.75, n_fft=1024)
        except Exception:
            pass
        return self._extract_speech(audio)

    def _extract_speech(self, audio):
        frame_size = int(self.rate * 0.03)
        frames = []
        for i in range(0, len(audio) - frame_size, frame_size):
            chunk = audio[i:i + frame_size]
            if self.vad.is_speech((chunk * 32767).astype(np.int16).tobytes(), self.rate):
                frames.append(chunk)
        result = np.concatenate(frames) if frames else audio
        return (result * 32767).astype(np.int16).tobytes()


class VoiceClient:
    def __init__(self):
        self.processor = AudioProcessor(CONFIG['RATE'])
        with ignore_alsa_warnings():
            self.pa = pyaudio.PyAudio()
        self.device_idx = self._find_mic()

    def _find_mic(self):
        for i in range(self.pa.get_host_api_info_by_index(0)['deviceCount']):
            dev = self.pa.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0 and 'USB' in dev['name']:
                print(f"[Init] USB Mic detected: {dev['name']}")
                return i
        return self.pa.get_default_input_device_info()['index']

    def record(self):
        print("[*] Listening...", end=' ', flush=True)
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16, channels=1, rate=CONFIG['RATE'],
                input=True, input_device_index=self.device_idx,
                frames_per_buffer=CONFIG['CHUNK']
            )
            frames = [stream.read(CONFIG['CHUNK'], exception_on_overflow=False)
                      for _ in range(0, int(CONFIG['RATE'] / CONFIG['CHUNK'] * CONFIG['DURATION']))]
            stream.stop_stream()
            stream.close()
            print("Done.")
            return self.processor.clean(b''.join(frames))
        except OSError:
            print("\n[Error] Mic error. Reinitializing...")
            self.device_idx = self._find_mic()
            return None

    def send(self, audio):
        if not audio: return None
        try:
            with socket.create_connection((CONFIG['SERVER_IP'], CONFIG['SERVER_PORT']), timeout=5) as sock:
                sock.sendall(len(audio).to_bytes(4, 'big') + audio)
                resp_len = int.from_bytes(sock.recv(4), 'big')
                return sock.recv(resp_len).decode('utf-8')
        except Exception as e:
            print(f"[Network] Error: {e}")
            return None

    async def speak(self, text):
        if not text: return
        print(f">>> {text}")
        output_file = "response.mp3"
        try:
            # Generate MP3
            communicate = edge_tts.Communicate(text, CONFIG['VOICE'])
            await communicate.save(output_file)

            # Play MP3 if generation succeeded
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                subprocess.run(['mpg123', '-q', output_file], check=False)
            else:
                print("[TTS] Error: File generation failed.")

        except Exception as e:
            print(f"[TTS] Error: {e}")

    def run(self):
        print(f"--- Client Ready ({CONFIG['SERVER_IP']}) ---")
        try:
            while True:
                if (resp := self.send(self.record())):
                    asyncio.run(self.speak(resp))
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.pa.terminate()


if __name__ == "__main__":
    VoiceClient().run()