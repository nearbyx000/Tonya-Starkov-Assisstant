
import socket
import pyaudio
import numpy as np
import noisereduce as nr
import webrtcvad
from scipy import signal
import asyncio
import edge_tts
import subprocess
import time

# Configuration
PC_SERVER_IP = "192.168.3.115"  # Change to your PC IP
PC_SERVER_PORT = 5000
VOICE = "ru-RU-DmitryNeural"
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
RECORD_SECONDS = 5
INPUT_DEVICE_INDEX = None  # None = default, or set to specific device


# Audio Preprocessor
class AudioPreprocessor:


    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.vad = webrtcvad.Vad(2)  # Aggressiveness: 0-3

    def preprocess(self, audio_data):
        """Complete audio preprocessing pipeline"""
        # 1. Normalize
        if np.max(np.abs(audio_data)) > 0:
            audio_data = audio_data / np.max(np.abs(audio_data))

        # 2. High-pass filter (removes low-frequency noise like hum)
        audio_data = self._highpass_filter(audio_data)

        # 3. Noise reduction
        audio_data = nr.reduce_noise(
            y=audio_data,
            sr=self.sample_rate,
            stationary=True,  # Set False for non-stationary noise
            prop_decrease=0.8
        )

        # 4. Voice Activity Detection
        audio_data = self._apply_vad(audio_data)

        return audio_data

    def _highpass_filter(self, audio):
        """Remove frequencies below 300Hz"""
        sos = signal.butter(4, 300, 'hp', fs=self.sample_rate, output='sos')
        return signal.sosfilt(sos, audio)

    def _apply_vad(self, audio):
        """Extract only speech segments"""
        frame_duration = 30  # ms
        frame_size = int(self.sample_rate * frame_duration / 1000)

        speech_frames = []
        for i in range(0, len(audio) - frame_size, frame_size):
            frame = audio[i:i + frame_size]

            # Convert to int16 for VAD
            frame_int16 = (frame * 32767).astype(np.int16)
            frame_bytes = frame_int16.tobytes()

            # Check if speech
            try:
                if self.vad.is_speech(frame_bytes, self.sample_rate):
                    speech_frames.append(frame)
            except:
                # If VAD fails, keep the frame
                speech_frames.append(frame)

        if speech_frames:
            return np.concatenate(speech_frames)
        return audio


# Client Class
class VoiceAssistantClient:
    """Improved client with noise cancellation"""

    def __init__(self):
        self.preprocessor = AudioPreprocessor(SAMPLE_RATE)
        self.audio = pyaudio.PyAudio()
        self.is_speaking = False

    def capture_audio(self):
        """Capture audio from microphone with preprocessing"""
        print("Listening...")

        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=INPUT_DEVICE_INDEX,
            frames_per_buffer=CHUNK_SIZE
        )

        frames = []
        for _ in range(0, int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS)):
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
            except IOError as e:
                print(f"Warning: {e}")
                continue

        stream.stop_stream()
        stream.close()

        # Convert to numpy array
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        audio_float = audio_data.astype(np.float32) / 32768.0

        print("Preprocessing audio...")

        # Apply preprocessing (noise reduction + VAD)
        clean_audio = self.preprocessor.preprocess(audio_float)

        # Convert back to int16
        clean_int16 = (clean_audio * 32767).astype(np.int16)

        return clean_int16.tobytes()

    def send_to_server(self, audio_bytes):
        """Send audio to server and get response"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((PC_SERVER_IP, PC_SERVER_PORT))

            # Send audio size first
            size = len(audio_bytes)
            sock.sendall(size.to_bytes(4, 'big'))

            # Send audio data
            sock.sendall(audio_bytes)

            # Receive response
            response_size = int.from_bytes(sock.recv(4), 'big')
            response_text = sock.recv(response_size).decode('utf-8')

            sock.close()

            return response_text

        except Exception as e:
            print(f"Server error: {e}")
            return None

    async def speak(self, text):
        """Speak text using Edge-TTS"""
        self.is_speaking = True
        print(f"Speaking: {text}")

        try:
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save("response.mp3")

            # Play audio
            subprocess.run(['mpg123', '-q', 'response.mp3'])

        except Exception as e:
            print(f"TTS error: {e}")

        finally:
            self.is_speaking = False
            time.sleep(0.5)  # Buffer clearing delay

    def run(self):
        """Main loop"""
        print("=" * 50)
        print("Tonya-Starkov Assistant (IMPROVED)")
        print("=" * 50)
        print(f"Server: {PC_SERVER_IP}:{PC_SERVER_PORT}")
        print(f"Voice: {VOICE}")
        print("=" * 50)

        while True:
            try:
                # Capture audio
                audio_data = self.capture_audio()

                # Send to server
                print("Sending to server...")
                response = self.send_to_server(audio_data)

                if response:
                    print(f"Response: {response}")
                    asyncio.run(self.speak(response))
                else:
                    print("No response from server")

                print("\n" + "-" * 50 + "\n")

            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

        self.audio.terminate()


# Main
if __name__ == "__main__":
    client = VoiceAssistantClient()