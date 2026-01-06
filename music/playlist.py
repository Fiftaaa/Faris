import json
import os
import time
from utils.config import PLAYLIST_FILE
from voice.synthesis import speak_async


# Завантаження плейлисту
def load_playlist():
    """Завантажує плейлист з файлу"""
    playlist = []
    if os.path.exists(PLAYLIST_FILE):
        try:
            with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
                playlist = json.load(f)
        except Exception as e:
            print(f"❌ Помилка завантаження плейлисту: {e}")
            playlist = []
    return playlist


def save_playlist(playlist):
    """Зберігає плейлист у файл"""
    try:
        os.makedirs(os.path.dirname(PLAYLIST_FILE), exist_ok=True)
        with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(playlist, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Помилка збереження плейлисту: {e}")
        return False


# Глобальні змінні
playlist = load_playlist()
current_song_index = -1


def listen_for_stop(timeout=5):
    """Слухає команди під час відтворення"""
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()

        with sr.Microphone() as source:
            print(f"🎵 Чекаю команду ({timeout}с)...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)

            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=2)
                command = recognizer.recognize_google(audio, language="uk-UA")
                print(f"🎵 Команда: {command}")
                return command.lower().strip()
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except Exception as e:
                print(f"🎵 Помилка розпізнавання: {e}")
                return None

    except Exception as e:
        print(f"🎵 Помилка мікрофона: {e}")
        return None


def play_playlist():
    """Відтворення всього плейлисту"""
    global playlist, current_song_index

    if not playlist:
        speak_async("Плейліст порожній.")
        return

    speak_async(f"Відтворюю плейліст з {len(playlist)} піснями.")
    print(f"🎵 Плейлист: {len(playlist)} пісень")

    current_song_index = 0
    from music.player import play_music, stop_music

    while current_song_index < len(playlist):
        song_item = playlist[current_song_index]

        # Отримуємо назву пісні
        if isinstance(song_item, dict):
            song_name = song_item.get('name', 'Невідома пісня')
        else:
            song_name = str(song_item)

        print(f"🎵 [{current_song_index + 1}/{len(playlist)}] {song_name}")

        # Оновлюємо статистику
        update_song_stats(song_name)

        # Відтворюємо пісню
        speak_async(f"Грає: {song_name}. Скажи стоп, далі чи лайк.")

        # Запускаємо музику в окремому потоці
        music_thread = threading.Thread(target=play_music, args=(song_name,), daemon=True)
        music_thread.start()

        # Чекаємо команд
        command_received = False
        start_time = time.time()

        while time.time() - start_time < 30 and not command_received:  # 30 секунд на пісню
            command = listen_for_stop(timeout=2)

            if command:
                print(f"🎵 Отримано команду: {command}")

                if "стоп" in command:
                    stop_music()
                    speak_async("Зупинила плейліст.")
                    current_song_index = -1
                    return
                elif "далі" in command or "наступна" in command:
                    stop_music()
                    speak_async("Наступна пісня.")
                    command_received = True
                    break
                elif "лайк" in command or "додай" in command:
                    add_song_to_playlist(song_name)
                    speak_async(f"Додала {song_name} до улюблених.")
                    # Продовжуємо грати цю ж пісню
                elif "пауза" in command:
                    # Тут потрібно б реалізувати паузу
                    speak_async("Пауза. Скажи 'продовжити'.")
                    # Чекаємо команду продовжити
                    while True:
                        cmd = listen_for_stop(timeout=5)
                        if cmd and ("продовжити" in cmd or "відновити" in cmd):
                            speak_async("Продовжую.")
                            break
                elif "пропусти" in command:
                    stop_music()
                    speak_async("Пропускаю цю пісню.")
                    command_received = True
                    break

            time.sleep(0.5)

        # Переходимо до наступної пісні
        stop_music()
        current_song_index += 1

    # Кінець плейлисту
    current_song_index = -1
    speak_async("Плейліст закінчився.")


def stop_playlist():
    """Зупинка плейлисту"""
    from music.player import stop_music
    stop_music()
    speak_async("Плейлист зупинено.")
    return True


def add_song_to_playlist(song_name):
    """Додає пісню до плейлисту"""
    global playlist

    try:
        song_name = song_name.strip()
        if not song_name:
            return False

        song_lower = song_name.lower()

        # Перевіряємо чи пісня вже є
        for i, item in enumerate(playlist):
            if isinstance(item, dict):
                existing_name = item.get('name', '').lower()
            else:
                existing_name = str(item).lower()

            if existing_name == song_lower:
                # Оновлюємо статистику
                if isinstance(playlist[i], dict):
                    playlist[i]['likes'] = playlist[i].get('likes', 0) + 1
                    playlist[i]['last_played'] = time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    # Перетворюємо на словник
                    playlist[i] = {
                        'name': item,
                        'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'last_played': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'plays': 1,
                        'likes': 1
                    }

                save_playlist(playlist)
                print(f"❤️ Оновлено пісню: {song_name}")
                return True

        # Додаємо нову пісню
        new_song = {
            'name': song_name,
            'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'last_played': time.strftime('%Y-%m-%d %H:%M:%S'),
            'plays': 0,
            'likes': 1
        }

        playlist.append(new_song)
        save_playlist(playlist)

        print(f"✅ Додано: {song_name}")
        print(f"📊 Всього: {len(playlist)} пісень")
        return True

    except Exception as e:
        print(f"❌ Помилка додавання: {e}")
        return False


def skip_to_next_song():
    """Перехід до наступної пісні"""
    global current_song_index

    from music.player import stop_music
    stop_music()

    if current_song_index >= 0 and current_song_index < len(playlist) - 1:
        current_song_index += 1
        return True
    return False


def get_current_playlist_info():
    """Отримує інформацію про плейлист"""
    global playlist

    if not playlist:
        return "Плейлист порожній"

    total_songs = len(playlist)
    total_plays = 0
    total_likes = 0

    for song in playlist:
        if isinstance(song, dict):
            total_plays += song.get('plays', 0)
            total_likes += song.get('likes', 0)
        else:
            total_plays += 1

    info = f"🎵 Плейлист: {total_songs} пісень\n"
    info += f"▶️ Відтворень: {total_plays}\n"
    info += f"❤️ Лайків: {total_likes}\n"

    # Останні 3 пісні
    if playlist:
        info += "\nОстанні пісні:\n"
        recent = playlist[-3:] if len(playlist) > 3 else playlist
        for i, song in enumerate(recent, 1):
            if isinstance(song, dict):
                name = song.get('name', 'Невідома')
                plays = song.get('plays', 0)
                likes = song.get('likes', 0)
                info += f"{i}. {name} (відтворено {plays}, лайків {likes})\n"
            else:
                info += f"{i}. {song}\n"

    return info


def clear_playlist():
    """Очищення плейлисту"""
    global playlist
    playlist = []
    save_playlist(playlist)
    print("🗑️ Плейлист очищено")
    return True


def update_song_stats(song_name):
    """Оновлює статистику пісні"""
    global playlist

    try:
        for i, item in enumerate(playlist):
            if isinstance(item, dict):
                existing_name = item.get('name', '')
            else:
                existing_name = str(item)

            if existing_name.lower() == song_name.lower():
                if isinstance(playlist[i], dict):
                    playlist[i]['plays'] = playlist[i].get('plays', 0) + 1
                    playlist[i]['last_played'] = time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    playlist[i] = {
                        'name': item,
                        'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'last_played': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'plays': 1,
                        'likes': 0
                    }

                save_playlist(playlist)
                break
    except Exception as e:
        print(f"❌ Помилка оновлення статистики: {e}")


def search_in_playlist(keyword):
    """Пошук у плейлисті"""
    global playlist

    results = []
    keyword_lower = keyword.lower()

    for song in playlist:
        if isinstance(song, dict):
            name = song.get('name', '')
        else:
            name = str(song)

        if keyword_lower in name.lower():
            results.append(song)

    return results


# Додайте імпорт threading вгорі файлу
import threading