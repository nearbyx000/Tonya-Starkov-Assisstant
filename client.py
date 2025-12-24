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

SERVER_IP = "192.168.3.115"
SERVER_PORT = 5000
VOICE = "ru-RU-SvetlanaNeural"
RATE = 16000
CHUNK = 1024
VAD_LEVEL = 2
HP_FREQ = 300


@contextlib.contextmanager
def ignore_alsa_warnings():
    try:
        handler = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)(lambda *args: None)
        asound = cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except:
        yield


class Client:
    def __init__(self):
        self.vad = webrtcvad.Vad(VAD_LEVEL)
        self.sos = signal.butter(4, HP_FREQ, 'hp', fs=RATE, output='sos')

    def process_audio(self, raw):
        if not raw: return None
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if (m := np.max(np.abs(audio))) > 0: audio /= m
        audio = signal.sosfilt(self.sos, audio)
        try:
            audio = nr.reduce_noise(y=audio, sr=RATE, stationary=True, prop_decrease=0.75, n_fft=512)
        except:
            pass
        return (audio * 32767).astype(np.int16).tobytes()

    def record(self):
        print("\n[*] Rec...", end=' ', flush=True)
        with ignore_alsa_warnings():
            p = pyaudio.PyAudio()
        try:
            dev_idx = p.get_default_input_device_info()['index']
            for i in range(p.get_host_api_info_by_index(0)['deviceCount']):
                d = p.get_device_info_by_index(i)
                if d['maxInputChannels'] > 0 and 'USB' in d['name']:
                    dev_idx = i
                    break

            stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                            input=True, input_device_index=dev_idx, frames_per_buffer=CHUNK)

            frames = []
            for _ in range(0, int(RATE / CHUNK * 5)):
                try:
                    frames.append(stream.read(CHUNK, exception_on_overflow=False))
                except:
                    continue

            stream.stop_stream()
            stream.close()
            print("Done.")
            return self.process_audio(b''.join(frames))
        except Exception as e:
            print(f"[Rec Error] {e}")
            return None
        finally:
            p.terminate()

    def send(self, data):
        try:
            with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=10) as s:
                s.sendall(len(data).to_bytes(4, 'big') + data)
                l = int.from_bytes(s.recv(4), 'big')
                return s.recv(l).decode('utf-8')
        except Exception as e:
            print(f"[Net Error] {e}")
            return None

    async def speak(self, text):
        if not text: return
        print(f">>> {text}")
        f = "response.mp3"
        if os.path.exists(f): os.remove(f)
        try:
            await edge_tts.Communicate(text, VOICE).save(f)
            if os.path.exists(f):
                subprocess.run(['mpg123', f])
        except Exception as e:
            print(f"[TTS Error] {e}")

    def run(self):
        print(f"--- Client {SERVER_IP} ---")
        while True:
            try:
                data = self.record()
                time.sleep(1.0)
                if data:
                    resp = self.send(data)
                    if resp:
                        asyncio.run(self.speak(resp))
                        time.sleep(0.5)
            except KeyboardInterrupt:
                break
            except Exception:
                time.sleep(1)


if __name__ == "__main__":
    Client().run()