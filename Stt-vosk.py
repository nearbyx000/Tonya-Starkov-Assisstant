import pyaudio
import json
from vosk import Model, KaldiRecognizer

# 1. Задайте путь к вашей модели
MODEL_PATH = "vosk-model-small-ru-0.22"  # Укажите имя папки, куда вы распаковали модель

# 2. Параметры аудиопотока
CHUNK = 4000
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000 # Частота дискретизации, должна совпадать с частотой модели

# --- Инициализация Vosk и PyAudio ---

print(f"Загрузка модели Vosk из папки: {MODEL_PATH}...")
try:
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, RATE)
except Exception as e:
    print(f"Ошибка при загрузке модели: {e}")
    print("Проверьте, правильно ли указан путь к папке с моделью.")
    exit()

p = pyaudio.PyAudio()

stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

print("\n--- ✅ Vosk готов! Говорите в микрофон... ---")

while True:
    data = stream.read(CHUNK, exception_on_overflow=False)
    
    # Если Vosk принял часть речи
    if rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        
        recognized_text = result.get('text', '').strip()
        
        # Выводим распознанный текст, если он не пустой
        if recognized_text:
            print(f"Вы сказали: **{recognized_text}**")
            
    # Если Vosk находится в процессе распознавания (полезно для отладки)
    # else:
    #     partial = json.loads(rec.PartialResult())
    #     print(f"Частичный результат: {partial.get('partial')}")