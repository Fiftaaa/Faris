import requests
from utils.config import ESP32_IP
from voice.synthesis import speak_async

def send_command_to_esp(cmd: str):
    try:
        url = f"http://{ESP32_IP}/control?var=car&val="
        if cmd == "forward":
            url += "1"
        elif cmd == "backward":
            url += "5"
        elif cmd == "left":
            url += "2"
        elif cmd == "right":
            url += "4"
        elif cmd == "spin":
            url += "2"
        elif cmd == "stop":
            url += "3"
        response = requests.get(url, timeout=3)
    except Exception as e:
        speak_async("Не можу зв'язатися з роботом.")

def turn_on_light():
    try:
        url = f"http://{ESP32_IP}/control?var=led&val=255"
        response = requests.get(url, timeout=2)
    except Exception as e:
        pass

def turn_off_light():
    try:
        url = f"http://{ESP32_IP}/control?var=led&val=0"
        response = requests.get(url, timeout=2)
    except Exception as e:
        pass