import os
import sys
import json
import pyaudio
from vosk import Model, KaldiRecognizer

# --- КОНФИГУРАЦИЯ ---

# Путь к папке с распакованной моделью
MODEL_PATH = "vosk-model-small-ru-0.22"

# Индекс микрофона, полученный из check_mic.py
# 4 - это 'pulse' (рекомендуется для Linux/Raspberry Pi)
# Если не сработает, попробуйте 10 ('default')
INPUT_DEVICE_INDEX = 4

# Настройки аудио
SAMPLE_RATE = 16000
CHUNK_SIZE = 4000

class VoiceRecognizer:
    """
    Класс для захвата и распознавания речи через Vosk.
    Использует контекстный менеджер для безопасного управления ресурсами.
    """
    
    def __init__(self, model_path: str, device_index: int, sample_rate: int = 16000):
        self.model_path = model_path
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = CHUNK_SIZE
        
        self.model = self._load_model()
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.audio = pyaudio.PyAudio()
        self.stream = None

    def _load_model(self) -> Model:
        """Проверяет наличие модели и загружает её."""
        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at '{self.model_path}'")
            print("Please download the model from https://alphacephei.com/vosk/models")
            sys.exit(1)
        
        print(f"Loading Vosk model from '{self.model_path}'...")
        return Model(self.model_path)

    def start(self):
        """Открывает аудиопоток с указанного устройства."""
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=self.device_index  # Важно: используем конкретный микрофон
            )
            print(f"Microphone (Index {self.device_index}) active. Listening...")
            
        except Exception as e:
            print(f"Critical Error initializing microphone: {e}")
            print("Try changing INPUT_DEVICE_INDEX in the configuration.")
            sys.exit(1)

    def stop(self):
        """Останавливает поток и освобождает ресурсы."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        print("Audio stream closed.")

    def listen(self):
        """
        Генератор. Слушает микрофон и возвращает (yield) распознанный текст,
        когда фраза завершена.
        """
        if not self.stream:
            self.start()

        while True:
            # Чтение данных из потока
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            except IOError as e:
                print(f"Audio buffer warning: {e}")
                continue

            # Обработка данных моделью
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                
                # Если текст не пустой, возвращаем его
                if text:
                    yield text

    # Поддержка контекстного менеджера (with ... as ...)
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# --- ТОЧКА ВХОДА ---

if __name__ == "__main__":
    print("Initializing Voice Assistant Core...")
    
    try:
        # Инициализация с параметрами конфигурации
        with VoiceRecognizer(MODEL_PATH, INPUT_DEVICE_INDEX, SAMPLE_RATE) as listener:
            
            # Основной цикл обработки команд
            for text in listener.listen():
                print(f"Recognized: {text}")
                
                # Здесь будет интеграция с LLM
                # Пример: llm.process(text)
                
                # Логика выхода
                if "стоп" in text.lower() or "выход" in text.lower():
                    print("Shutdown command received.")
                    break
                    
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")