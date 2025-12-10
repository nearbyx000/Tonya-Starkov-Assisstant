# 1. Создаем папку для TTS, чтобы не мусорить
mkdir -p /home/pi/piper_tts
cd /home/pi/piper_tts

# 2. Скачиваем бинарник Piper (Версия для arm64/Pi 4/5)
echo "Скачивание движка..."
wget -O piper.tar.gz https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
tar -xf piper.tar.gz

# 3. Скачиваем русскую модель (Irina Medium - лучший баланс качества/скорости)
echo "Скачивание голоса..."
wget -O model.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx
wget -O model.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json

echo "✅ Готово! Путь к Piper: /home/pi/piper_tts/piper/piper"