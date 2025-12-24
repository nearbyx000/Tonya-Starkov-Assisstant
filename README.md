TONYA VOICE ASSISTANT - SETUP INSTRUCTIONS

================================================================
PART 1: PC SERVER SETUP (Windows/Linux)
================================================================
Prerequisites: 
- Python 3.11 installed
- LM Studio installed and running (Local Server started on port 1234)
- FFmpeg installed and added to system PATH

1. Install Python Libraries:
   Open your terminal or command prompt and run:
   pip install openai-whisper openai pyaudio

2. Find Your Ethernet IP Address:
   - Windows: Open Command Prompt, type "ipconfig". Look for the IPv4 Address under "Ethernet adapter".
   - Linux: Open Terminal, type "ip a".
   - Write down this IP address.

3. Start the Server:
   Navigate to the folder containing server.py and run:
   python server.py

================================================================
PART 2: RASPBERRY PI CLIENT SETUP
================================================================
Prerequisites: 
- Python 3.9 or newer
- USB Microphone connected
- Speaker or Headphones connected (3.5mm Jack or USB)

1. Install System Audio Drivers:
   Run the following commands in the terminal:
   sudo apt update
   sudo apt install python3-pyaudio mpg123 libatlas-base-dev -y

2. Install Python Libraries:
   Run:
   pip install pyaudio noisereduce webrtcvad edge-tts scipy numpy

3. Configure the Connection:
   - Open client.py using a text editor (e.g., nano client.py).
   - Find the line that says: SERVER_IP = "..."
   - Change the IP address inside the quotes to the PC IP you found in Part 1.
   - Save the file.

4. Run the Client:
   Run:
   python3 client.py

================================================================
TROUBLESHOOTING
================================================================

ISSUE: Connection Timed Out / Network Error
- Ensure both devices are on the same network.
- If connecting the PC directly to the Pi via Ethernet cable (no router), you must manually set Static IPs on both devices (e.g., PC: 192.168.1.5, Pi: 192.168.1.6).

ISSUE: No Sound on Raspberry Pi
- The Pi might be sending audio to HDMI. Force it to the headphone jack:
  1. Run: sudo raspi-config
  2. Select: System Options -> Audio -> Headphones
  3. Select: Finish