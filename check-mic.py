import pyaudio

def list_input_devices():
    """Сканирует систему и выводит список всех доступных микрофонов."""
    
    p = pyaudio.PyAudio()
    device_count = p.get_device_count()
    
    print("--- Список доступных аудиоустройств ---")
    
    found_mic = False
    
    # Итерируем по всем найденным устройствам
    for i in range(device_count):
        dev = p.get_device_info_by_index(i)
        
        # Проверяем, есть ли у устройства входные каналы (микрофон)
        if dev['maxInputChannels'] > 0:
            found_mic = True
            print(f"ГОТОВ К ИСПОЛЬЗОВАНИЮ: Индекс {i} | Название: {dev['name']} | Каналы: {dev['maxInputChannels']}")
        else:
            print(f"ТОЛЬКО ВЫВОД: Индекс {i} | Название: {dev['name']}")

    p.terminate()
    
    if not found_mic:
        print("\nОшибка: Входные устройства (микрофоны) не найдены. Проверьте подключение.")

if __name__ == '__main__':
    list_input_devices()