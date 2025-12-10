import speech_recognition as sr

print("--- Available Audio Devices ---")
mics = sr.Microphone.list_microphone_names()
for index, name in enumerate(mics):
    print(f"Index {index}: {name}")