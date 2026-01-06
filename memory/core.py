import json
import os
import datetime
from utils.config import MEMORY_JSON_FILE, DEVELOPER_MODE
from voice.synthesis import speak_async

def load_memory():
    if os.path.exists(MEMORY_JSON_FILE):
        try:
            with open(MEMORY_JSON_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {}
    return {}

def save_memory(memory_data):
    try:
        with open(MEMORY_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        return False

def process_remember_command(user_text):
    if not DEVELOPER_MODE:
        speak_async("Режим розробника не активовано. Не можу запам'ятати.")
        return
    clean_text = user_text.replace("запам'ятай", "").replace("що", "").strip()
    if not clean_text:
        speak_async("Не вказано, що запам'ятати.")
        return
    memory = load_memory()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory[timestamp] = clean_text
    if save_memory(memory):
        speak_async(f"Запам'ятав: {clean_text}")
    else:
        speak_async("Не вдалося зберегти в пам'ять.")