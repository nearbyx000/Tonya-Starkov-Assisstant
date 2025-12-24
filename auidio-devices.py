# test_audio.py
import asyncio
import edge_tts
import os
import subprocess

VOICE = "ru-RU-DmitryNeural"
TEXT = "Проверка аудиосистемы. Я готова к работе."

async def main():
    print("Генерация аудио...")
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save("test.mp3")

    if os.path.exists("test.mp3"):
        print("Воспроизведение через mpg123...")
        # Флаг -f 32768 увеличивает скейлинг амплитуды (громкость)
        subprocess.run(['mpg123', '-f', '32768', 'test.mp3'])
    else:
        print("ОШИБКА: Файл не создан.")

if __name__ == "__main__":
    asyncio.run(main())