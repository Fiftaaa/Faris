import os
import re
import json
import time
import datetime
import threading

import yt_dlp
import vlc
import pygame

from voice.recognition import recognize_speech  # used for conversational prompts
from voice.synthesis import speak_async


try:
    from utils.config import ALARM_CONFIG_FILE
except Exception:
    ALARM_CONFIG_FILE = "alarm_config.json"

last_song = None
playlist = []
_alarm_thread = None
_music_lock = threading.Lock()
_vlc_instance = None
_vlc_player = None
_music_stop_listener = None
_music_active = False  # guarded by _music_lock


def _ensure_vlc():
    global _vlc_instance, _vlc_player
    if _vlc_instance is None:
        _vlc_instance = vlc.Instance()
    if _vlc_player is None:
        _vlc_player = _vlc_instance.media_player_new()
    return _vlc_player


def _stop_vlc():
    global _vlc_player
    if _vlc_player is not None:
        try:
            _vlc_player.stop()
        except Exception:
            pass



def _resolve_ytdlp_url(query: str) -> str:
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch',
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        return info['entries'][0]['url'] if 'entries' in info else info['url']


def play_music(song_name: str):
    global last_song, _music_active
    last_song = song_name

    # Build source
    if os.path.isfile(song_name):
        source = ("file", song_name)
    else:
        try:
            url = _resolve_ytdlp_url(song_name)
            source = ("url", url)
        except Exception as e:
            speak_async("Не вдалося знайти або відтворити пісню.")
            return

    # Start VLC
    player = _ensure_vlc()
    if source[0] == "file":
        media = _vlc_instance.media_new_path(source[1])
    else:
        media = _vlc_instance.media_new(source[1])
    player.set_media(media)

    with _music_lock:
        _music_active = True

    player.play()
    speak_async("Грає пісня. Скажи 'стоп', щоб зупинити.")


def stop_music():

    global _music_active
    _stop_vlc()
    with _music_lock:
        _music_active = False


def parse_alarm_time(text: str):
    """
    Parse Ukrainian / simple phrases like 'на 7 30', 'о 21:05', 'на пів на восьму' (basic support).
    Returns (hour, minute) or (None, None)
    """
    text = text.lower().strip()
    # Direct HH[:.,/]MM
    m = re.search(r'(\d{1,2})\s*[:.,/]\s*(\d{2})', text)
    if m:
        h, mm = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mm <= 59:
            return h, mm

    # "на 7 30" (space separated)
    m = re.search(r'\b(\d{1,2})\s+(\d{1,2})\b', text)
    if m:
        h, mm = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mm <= 59:
            return h, mm

    # Fallback: single hour like "на 7" -> 7:00
    m = re.search(r'\b(?:на|о)?\s*(\d{1,2})\b', text)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return h, 0

    return None, None


def set_alarm():
    max_attempts = 3
    attempts = 0

    while attempts < max_attempts:
        speak_async("На котру годину поставити будильник?")
        user_input = recognize_speech() or ""
        user_input = user_input.lower()

        if "стоп" in user_input:
            speak_async("Встановлення будильника скасовано.")
            return

        # direct "на HH:MM"
        match_direct = re.search(r"постав(?:ити)? будильник на\s*(\d{1,2})[:.,/](\d{2})", user_input)
        if match_direct:
            hour = int(match_direct.group(1))
            minute = int(match_direct.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                break
            else:
                speak_async("Невірний час, спробуй ще раз.")
                attempts += 1
                continue

        # natural parse
        hour, minute = parse_alarm_time(user_input)
        if hour is not None:
            break
        else:
            speak_async("Не вдалося розпізнати час, спробуй ще раз.")
            attempts += 1

    if attempts == max_attempts:
        speak_async("Не вдалося розпізнати час для будильника. Спробуй пізніше.")
        return

    speak_async("Яку музику поставити? Назви або скажи назву пісні.")
    music_text = (recognize_speech() or "").strip()
    if "стоп" in music_text.lower():
        speak_async("Встановлення будильника скасовано.")
        return

    music_path = f"{music_text}.mp3"
    music_query = music_path if os.path.isfile(music_path) else music_text

    save_alarm_config({"hour": hour, "minute": minute, "music": music_query})
    speak_async(f"Будильник встановлено на {hour}:{minute:02}.")

    # start waiter
    t = threading.Thread(target=wait_until_alarm, args=(hour, minute, music_query), daemon=True)
    t.start()


def wait_until_alarm(hour, minute, music_query):
    def play_alarm():
        speak_async("Час прокидатися!")

        # alarm stop listener (local)
        alarm_stop_flag = {"v": False}

        # music source
        if os.path.isfile(music_query):
            pygame.mixer.init()
            pygame.mixer.music.load(music_query)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not alarm_stop_flag["v"]:
                time.sleep(0.5)
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        else:
            try:
                url = _resolve_ytdlp_url(music_query)
                player = _ensure_vlc()
                media = _vlc_instance.media_new(url)
                player.set_media(media)
                player.play()
                while player.is_playing() and not alarm_stop_flag["v"]:
                    time.sleep(0.5)
                player.stop()
            except Exception:
                speak_async("Не вдалося відтворити музику для будильника.")

    # wait loop
    while True:
        now = datetime.datetime.now()
        if now.hour == hour and now.minute == minute:
            play_alarm()
            break
        time.sleep(5)


# --------------- Config I/O ---------------

def load_alarm_config():
    if os.path.exists(ALARM_CONFIG_FILE):
        try:
            with open(ALARM_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_alarm_config(config):
    with open(ALARM_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
