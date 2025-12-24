import os
import sys
import pyaudio
import contextlib
from ctypes import *

# Константы конфигурации
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  # Или 48000, 16000 в зависимости от микрофона

# Обработчик ошибок для подавления вывода ALSA lib
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(filename, line, function, err, fmt):
    pass


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)


@contextlib.contextmanager
def no_alsa_error():
    """Подавляет спам ошибок ALSA/Jack в stderr."""
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)


def get_input_device_index(p: pyaudio.PyAudio):
    """Находит первый доступный USB-микрофон или возвращает default."""
    info = p.get_host_api_info_by_index(0)
    num_devices = info.get('deviceCount')

    # Приоритет USB устройствам
    for i in range(num_devices):
        dev = p.get_device_info_by_index(i)
        if dev.get('maxInputChannels') > 0:
            if 'USB' in dev.get('name'):
                return i

    # Fallback на системный дефолт, если USB не найден
    return p.get_default_input_device_info()['index']


def main():
    with no_alsa_error():
        p = pyaudio.PyAudio()

    try:
        dev_index = get_input_device_index(p)
        print(f"[INFO] Selected Input Device Index: {dev_index}")

        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=dev_index,
                        frames_per_buffer=CHUNK)

        print("[INFO] Stream started successfully. Recording...")

        # Логика обработки звука
        # while True:
        #    data = stream.read(CHUNK, exception_on_overflow=False)

    except Exception as e:
        print(f"[ERROR] Init failed: {e}")
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        p.terminate()


if __name__ == "__main__":
    main()