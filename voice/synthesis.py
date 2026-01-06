import threading
import tempfile
import os
import pygame
import time
from gtts import gTTS

speak_lock = threading.Lock()
stop_speaking_flag = False

def speak(text):
    filename = "temp_voice.mp3"
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except PermissionError:
            return
    with speak_lock:
        tts = gTTS(text=text, lang='uk')
        tts.save(filename)
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        os.remove(filename)

def speak_async(text):
    def run_speak():
        global stop_speaking_flag
        stop_speaking_flag = False
        tts = gTTS(text=text, lang='uk')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
        tts.save(temp_path)
        pygame.mixer.init()
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if stop_speaking_flag:
                pygame.mixer.music.stop()
                break
            time.sleep(0.1)
        pygame.mixer.quit()
        os.remove(temp_path)
    t = threading.Thread(target=run_speak)
    t.start()
    return t

def stop_speaking():
    global stop_speaking_flag
    stop_speaking_flag = True
    pygame.mixer.music.stop()