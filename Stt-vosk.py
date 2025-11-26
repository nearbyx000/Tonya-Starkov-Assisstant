import os
import sys
import json
import pyaudio
from vosk import Model, KaldiRecognizer

class VoiceRecognizer:
    """
    Класс для распознавания речи с использованием Vosk.
    """
    
    def __init__(self, model_path: str, sample_rate: int = 16000):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.chunk_size = 4000
        self.model = self._load_model()
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.audio_interface = pyaudio.PyAudio()
        self.stream = None

    def _load_model(self) -> Model:
        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at '{self.model_path}'")
            print("Please download the model from https://alphacephei.com/vosk/models")
            sys.exit(1)
        
        print(f"Loading model from '{self.model_path}'...")
        return Model(self.model_path)

    def start(self):
        try:
            self.stream = self.audio_interface.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            print("Microphone active. Listening...")
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            sys.exit(1)

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio_interface.terminate()
        print("Listening stopped.")

    def listen(self):
        """
        Генератор, возвращающий распознанный текст.
        """
        if not self.stream:
            self.start()

        while True:
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                if text:
                    yield text

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# --- 4. ОСНОВНОЙ ЦИКЛ ПРОГРАММЫ (Только распознавание) ---

if __name__ == "__main__":
    
    # Конфигурация Vosk
    MODEL_PATH = "vosk-model-small-ru-0.22"
    SAMPLE_RATE = 16000
    
    try:
        # Используем только VoiceRecognizer
        with VoiceRecognizer(MODEL_PATH, SAMPLE_RATE) as listener:
            for text in listener.listen():
                
                # ЭТО ТОЧКА, ГДЕ РАСПОЗНАННЫЙ ТЕКСТ ГОТОВ
                print(f"Распознано: {text}")
                
                # Здесь будет код для LLM
                # Например: llm_response = send_to_llm(text)
                #          print(llm_response)
                
                # Условие выхода из программы
                if "выход" in text.lower() or "завершить" in text.lower():
                    print("Команда завершения программы получена.")
                    break
                    
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем (Ctrl+C).")
    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")