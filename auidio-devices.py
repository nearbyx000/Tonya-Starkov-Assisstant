"""
List all available audio devices on Raspberry Pi
Run this to find your microphone device index
"""

import pyaudio
import warnings
import os

# Suppress ALSA warnings
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings('ignore')

# Redirect ALSA errors to null
from ctypes import *

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(filename, line, function, err, fmt):
    pass


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

print("Available Audio Devices:")
print("=" * 50)

audio = pyaudio.PyAudio()

for i in range(audio.get_device_count()):
    info = audio.get_device_info_by_index(i)

    # Only show input devices
    if info['maxInputChannels'] > 0:
        print(f"\nDevice {i}: {info['name']}")
        print(f"  Channels: {info['maxInputChannels']}")
        print(f"  Sample Rate: {int(info['defaultSampleRate'])} Hz")
        print(f"  Host API: {audio.get_host_api_info_by_index(info['hostApi'])['name']}")

audio.terminate()

print("\n" + "=" * 50)
print("\nTo use a device, set INPUT_DEVICE_INDEX in client_improved.py")
print("Example: INPUT_DEVICE_INDEX = 2")