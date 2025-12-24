import asyncio
import edge_tts
import os
import subprocess

# Используем Светлану, так как она реже всего "отваливается"
# Если в шаге 2 вы увидели DmitryNeural, можете вернуть его сюда.
VOICE = "ru-RU-SvetlanaNeural"
TEXT = "Проверка аудиосистемы. Я готова к работе."
OUTPUT_FILE = "test_audio.mp3"


async def main():
    print(f"1. Генерирую файл (Голос: {VOICE})...")

    try:
        communicate = edge_tts.Communicate(TEXT, VOICE)
        await communicate.save(OUTPUT_FILE)
    except Exception as e:
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА] Не удалось получить аудио от Microsoft.")
        print(f"Детали: {e}")
        print("Совет: Проверьте интернет или смените VOICE.")
        return

    if os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
        print(f"2. Файл создан успешно ({os.path.getsize(OUTPUT_FILE)} байт).")
        print("3. Воспроизведение через mpg123...")

        # Запуск плеера
        result = subprocess.run(['mpg123', '-q', OUTPUT_FILE])

        if result.returncode != 0:
            print("[ОШИБКА] mpg123 не смог воспроизвести файл. Проверьте аудио-выход.")
    else:
        print("[ОШИБКА] Файл создан, но он пустой.")


if __name__ == "__main__":
    asyncio.run(main())