import socket
import struct
import time
import subprocess
import speech_recognition as sr

SERVER_IP = "192.168.3.24"
SERVER_PORT = 5000
MIC_INDEX = 4

class Client:
    def __init__(self):
        self.rec = sr.Recognizer()
        self.rec.energy_threshold = 3000
        self.rec.dynamic_energy_threshold = False
        self.rec.pause_threshold = 0.8

    def _play(self, data):
        try:
            p = subprocess.Popen(["aplay", "-q"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            p.communicate(input=data)
        except: pass

    def _recv_exact(self, sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data += packet
        return data

    def run(self):
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_IP, SERVER_PORT))
                
                with sr.Microphone(device_index=MIC_INDEX) as source:
                    self.rec.adjust_for_ambient_noise(source, duration=1)
                    
                    while True:
                        try:
                            audio = self.rec.listen(source, timeout=None)
                            wav = audio.get_wav_data()
                            
                            sock.sendall(struct.pack('!I', len(wav)))
                            sock.sendall(wav)
                            
                            header = self._recv_exact(sock, 4)
                            if not header: break
                            size = struct.unpack('!I', header)[0]
                            
                            if size > 0:
                                data = self._recv_exact(sock, size)
                                if data: self._play(data)
                        except: break
                sock.close()
            except:
                time.sleep(3)

if __name__ == "__main__":
    try: Client().run()
    except KeyboardInterrupt: pass