import socketserver
import struct
import io
import os
import torch
import torchaudio
from faster_whisper import WhisperModel
from openai import OpenAI

HOST = "0.0.0.0"
PORT = 5000
WHISPER_SIZE = "medium"
WHISPER_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
LLM_URL = "http://localhost:1234/v1"
LLM_KEY = "lm-studio"
TTS_SPEAKER = "aidar"
SAMPLE_RATE = 48000

class Engine:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Engine, cls).__new__(cls)
            cls._instance._init_models()
        return cls._instance

    def _init_models(self):
        self.stt = WhisperModel(WHISPER_SIZE, device=WHISPER_DEVICE, compute_type="int8")
        device = torch.device(WHISPER_DEVICE)
        self.tts, _ = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts', language='ru', speaker='v4_ru')
        self.tts.to(device)
        self.llm = OpenAI(base_url=LLM_URL, api_key=LLM_KEY)
        self.history = []

    def process(self, audio_bytes: bytes) -> bytes:
        with open("buffer.wav", "wb") as f:
            f.write(audio_bytes)
        segments, _ = self.stt.transcribe("buffer.wav", language="ru", beam_size=5)
        text = " ".join([s.text for s in segments]).strip()
        if os.path.exists("buffer.wav"): os.remove("buffer.wav")
        
        if len(text) < 2: return b''
        
        self.history.append({"role": "user", "content": text})
        if len(self.history) > 10: self.history = self.history[-10:]
        
        try:
            resp = self.llm.chat.completions.create(model="local-model", messages=self.history, temperature=0.7, max_tokens=256)
            ai_text = resp.choices[0].message.content
            self.history.append({"role": "assistant", "content": ai_text})
            
            audio_tensor = self.tts.apply_tts(text=ai_text, speaker=TTS_SPEAKER, sample_rate=SAMPLE_RATE)
            buff = io.BytesIO()
            torchaudio.save(buff, audio_tensor.unsqueeze(0), SAMPLE_RATE, format="wav")
            return buff.getvalue()
        except:
            return b''

class RequestHandler(socketserver.BaseRequestHandler):
    def _recv_exact(self, n):
        data = b''
        while len(data) < n:
            packet = self.request.recv(n - len(data))
            if not packet: return None
            data += packet
        return data

    def handle(self):
        engine = Engine()
        while True:
            try:
                header = self._recv_exact(4)
                if not header: break
                size = struct.unpack('!I', header)[0]
                
                mic_data = self._recv_exact(size)
                if not mic_data: break
                
                response_wav = engine.process(mic_data)
                
                self.request.sendall(struct.pack('!I', len(response_wav)))
                if len(response_wav) > 0:
                    self.request.sendall(response_wav)
            except: break

if __name__ == "__main__":
    Engine()
    with socketserver.ThreadingTCPServer((HOST, PORT), RequestHandler) as server:
        server.serve_forever()