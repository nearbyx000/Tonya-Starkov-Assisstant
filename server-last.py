import socketserver
import struct
import logging
import os
from dataclasses import dataclass
from typing import Optional, List, Dict
from faster_whisper import WhisperModel
from openai import OpenAI

@dataclass(frozen=True)
class Config:
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    WHISPER_SIZE: str = "medium"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_TYPE: str = "int8"
    LLM_URL: str = "http://localhost:1234/v1"
    LLM_KEY: str = "lm-studio"
    HISTORY_LIMIT: int = 10
    TEMP_FILE: str = "buffer.wav"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

class InferenceEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InferenceEngine, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        logging.info("Initializing Inference Engine...")
        self.stt = WhisperModel(
            Config.WHISPER_SIZE, 
            device=Config.WHISPER_DEVICE, 
            compute_type=Config.WHISPER_TYPE
        )
        self.llm = OpenAI(base_url=Config.LLM_URL, api_key=Config.LLM_KEY)
        # History is initialized empty. System prompt is managed via LM Studio settings.
        self.history: List[Dict[str, str]] = []
        logging.info("Engine ready.")

    def transcribe(self, audio_bytes: bytes) -> str:
        with open(Config.TEMP_FILE, "wb") as f:
            f.write(audio_bytes)
        
        segments, _ = self.stt.transcribe(Config.TEMP_FILE, language="ru", beam_size=5)
        text = " ".join([s.text for s in segments]).strip()
        
        if os.path.exists(Config.TEMP_FILE):
            os.remove(Config.TEMP_FILE)
            
        return text

    def query_llm(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        
        if len(self.history) > Config.HISTORY_LIMIT:
            self.history = self.history[-Config.HISTORY_LIMIT:]

        try:
            completion = self.llm.chat.completions.create(
                model="local-model",
                messages=self.history,
                temperature=0.7,
                max_tokens=300
            )
            response = completion.choices[0].message.content
            self.history.append({"role": "assistant", "content": response})
            return response
        except Exception as e:
            logging.error(f"LLM request failed: {e}")
            return "Ошибка обработки запроса."

class VoiceRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_addr = self.client_address[0]
        logging.info(f"Client connected: {client_addr}")
        engine = InferenceEngine()

        while True:
            try:
                # Protocol: [Header 4 bytes (Length)] + [Payload (Audio)]
                header = self._recv_exact(4)
                if not header:
                    break
                
                payload_size = struct.unpack('!I', header)[0]
                if payload_size == 0:
                    continue

                logging.info(f"Receiving {payload_size} bytes from {client_addr}")
                audio_data = self._recv_exact(payload_size)
                if not audio_data:
                    break

                text = engine.transcribe(audio_data)
                logging.info(f"[{client_addr}] STT: {text}")

                response_text = ""
                if len(text) > 1:
                    response_text = engine.query_llm(text)
                    logging.info(f"[{client_addr}] LLM: {response_text}")

                encoded = response_text.encode('utf-8')
                self.request.sendall(struct.pack('!I', len(encoded)))
                self.request.sendall(encoded)

            except (ConnectionResetError, BrokenPipeError):
                logging.warning(f"Connection reset by {client_addr}")
                break
            except Exception as e:
                logging.error(f"Handler error: {e}")
                break

    def _recv_exact(self, n: int) -> Optional[bytes]:
        data = b''
        while len(data) < n:
            packet = self.request.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    InferenceEngine() # Pre-load models
    with ThreadedTCPServer((Config.HOST, Config.PORT), VoiceRequestHandler) as server:
        logging.info(f"Server running on {Config.HOST}:{Config.PORT}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()