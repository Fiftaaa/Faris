import sys
import os
import time
import threading
import queue
import re
import json
from collections import deque

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import speech_recognition as sr
import pygame
import requests
import vlc
from gtts import gTTS

from voice.recognition import recognize_speech
from voice.synthesis import speak_async, stop_speaking
from voice.database import load_voice_database, learn_new_voice
from face.recognition import recognize_face
from face.training import learn_face
from face.database import load_user_database, list_known_users
from memory.core import load_memory, process_remember_command
from memory.reminders import set_reminder, check_pending_reminders
from hardware.esp32_control import send_command_to_esp, turn_on_light, turn_off_light
from hardware.camera import toggle_auto_light
from emotions.controller import update_emotion_based_on_dialog, set_emotion_directly, get_current_emotion, \
    initialize_emotion_classifier
from music.player import play_music, stop_music, set_alarm
from music.playlist import play_playlist, stop_playlist
from utils.helpers import get_weather, extract_song_name, add_to_conversation_history, get_conversation_history
from utils.config import SLEEP_MODE, DEVELOPER_MODE, ESP32_IP

user_database = {}
voice_database = {}
recognition_queue = queue.Queue()
face_recognition_active = False
alarm_thread_obj = None
alarm_stop_flag = False
playlist = []
music_playing = False
camera_active = False
current_speaking_thread = None

LISTENING_TIMEOUT = 2
SPEECH_TIMEOUT = 6
PAUSE_BETWEEN_COMMANDS = 0.5

def safe_speak_async(text):
    global music_playing

    try:
        if music_playing:
            print("🔇 Очікую звільнення аудіо-пристрою після музики...")
            time.sleep(1.0)
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
                print("🔊 Аудіо-систему переініціалізовано")
            except:
                print("⚠️ Не вдалося переініціалізувати аудіо-систему")

        print(f"🗣️ Озвучую: {text[:50]}...")
        return speak_async(text)

    except Exception as e:
        print(f"❌ ПОМИЛКА ОЗВУЧЕННЯ: {e}")
        try:
            pygame.mixer.quit()
            time.sleep(0.5)
            pygame.mixer.init()
            print("🔊 Аудіо-систему відновлено")
            return speak_async(text)
        except:
            print("❌ НЕ ВДАЛОСЯ ВІДНОВИТИ ОЗВУЧЕННЯ")
            return None

def process_voice_input_improved():
    print(f"🎤 Слухаю... (таймаут: {SPEECH_TIMEOUT}с)")

    try:
        time.sleep(0.3)

        result = recognize_speech(timeout=SPEECH_TIMEOUT)

        if result is None:
            return None, None

        if isinstance(result, str):
            user_text = result
            voice_owner = None
        elif isinstance(result, tuple) and len(result) == 2:
            user_text, voice_owner = result
        else:
            print(f"⚠️ Невідомий формат відповіді: {type(result)}")
            return None, None

        if not user_text:
            return None, None

        user_text = user_text.strip()
        print(f"🔊 Розпізнано: '{user_text}'")

        if len(user_text) < 3:
            print("🔇 Занадто коротка фраза, ігнорую")
            return None, None

        ignore_phrases = ["а", "е", "ну", "ось", "так ось", "типу"]
        if user_text.lower() in ignore_phrases:
            print("🔇 Непотрібна фраза, ігнорую")
            return None, None

        return user_text, voice_owner

    except Exception as e:
        print(f"⚠️ Помилка слухання: {e}")
        return None, None

def wait_for_speech_response(timeout=5):
    print(f"⏳ Очікую відповідь... ({timeout}с)")
    time.sleep(0.5)

    start_time = time.time()
    while time.time() - start_time < timeout:
        user_text, _ = process_voice_input_improved()
        if user_text:
            return user_text
        time.sleep(0.1)

    return None

def extract_city_name(user_text):
    patterns = [
        r'погода у?\s*([А-Яа-яЇїІіЄєҐґ\-\s]+)',
        r'погода в\s+([А-Яа-яЇїІіЄєҐґ\-\s]+)',
        r'погода на\s+([А-Яа-яЇїІіЄєҐґ\-\s]+)',
        r'([А-Яа-яЇїІіЄєҐґ\-\s]+)\s+погода'
    ]

    for pattern in patterns:
        match = re.search(pattern, user_text.lower())
        if match:
            city = match.group(1).strip()
            city = re.sub(r'\b(у|в|на|погода|яка|як)\b', '', city).strip()
            if city and len(city) > 1:
                return city.capitalize()

    return None

def handle_music_command(user_text, user_lower):
    global music_playing

    print("🎵 КОМАНДА: Обробка музики")

    print("🎵 Запитую назву пісні...")
    safe_speak_async("Яку саме пісню чи виконавця ти хочеш послухати? Назви мені пісню.")

    song_response = wait_for_speech_response(8)

    if song_response and len(song_response.strip()) > 2:
        song = song_response.strip()
        print(f"🎵 ОТРИМАНО НАЗВУ ПІСНІ: '{song}'")

        print(f"🎵 ВІДТВОРЕННЯ ПІСНІ: '{song}'")
        music_playing = True
        safe_speak_async(f"Включаю {song}")

        threading.Thread(target=play_music, args=(song,), daemon=True).start()

    else:
        print("❌ Не отримано назву пісні")
        safe_speak_async("Не зрозумів назву пісні. Скажи, наприклад: 'Shape of You' або 'The Weeknd'.")

    return True

def handle_weather_command(user_text):
    print("🌤️ КОМАНДА: Отримати погоду")

    city = extract_city_name(user_text)

    if not city:
        print("🌤️ Не вказано місто - запитую")
        safe_speak_async("Для якого міста показати погоду? Назви місто.")

        city_response = wait_for_speech_response(8)

        if city_response and len(city_response.strip()) > 1:
            city = city_response.strip()
            print(f"🌤️ ОТРИМАНО МІСТО: '{city}'")
        else:
            print("❌ Не отримано місто")
            safe_speak_async("Не зрозумів назву міста. Скажи, наприклад: 'Київ' або 'Львів'.")
            return True

    if city:
        print(f"🌤️ ОТРИМАННЯ ПОГОДИ ДЛЯ: '{city}'")
        forecast = get_weather(city)
        print(f"🌤️ ПОГОДА: {forecast}")
        safe_speak_async(forecast)
    else:
        safe_speak_async("Не вдалося отримати погоду для цього міста.")

    return True

def handle_stop_command(user_lower):
    global music_playing, camera_active

    print("⏹️ КОМАНДА: Обробка команди стоп")

    if music_playing:
        print("⏹️ Зупиняю музику")
        stop_music()
        music_playing = False
        return True

    elif camera_active:
        print("⏹️ Вимкнути камеру")
        camera_active = False
        safe_speak_async("Камеру вимкнено.")
        return True

    else:
        print("⏹️ Зупинити мовлення")
        stop_speaking()
        return True

def handle_robot_commands(user_lower):
    direction = None

    if "танцюй" in user_lower:
        print("💃 КОМАНДА: Танець")
        safe_speak_async("Починаю веселий танець!")
        dance_moves = ["forward", "left", "backward", "right", "spin", "forward", "spin"]
        for i, move in enumerate(dance_moves):
            print(f"💃 КРОК {i + 1}: {move}")
            send_command_to_esp(move)
            time.sleep(1.0)
            send_command_to_esp("stop")
            time.sleep(0.2)
        print("💃 ТАНЕЦЬ ЗАВЕРШЕНО")
        safe_speak_async("Танець завершено!")
        return True

    elif "прямо" in user_lower or "вперед" in user_lower:
        direction = "forward"
        print("🤖 РУХ: Вперед")
        safe_speak_async("Їду вперед.")
    elif "назад" in user_lower:
        direction = "backward"
        print("🤖 РУХ: Назад")
        safe_speak_async("Їду назад.")
    elif "ліворуч" in user_lower or "наліво" in user_lower:
        direction = "left"
        print("🤖 РУХ: Ліворуч")
        safe_speak_async("Повертаю ліворуч.")
    elif "праворуч" in user_lower or "направо" in user_lower:
        direction = "right"
        print("🤖 РУХ: Праворуч")
        safe_speak_async("Повертаю праворуч.")
    elif "крутитися" in user_lower or "поворот навколо" in user_lower:
        direction = "spin"
        print("🤖 РУХ: Кружляння")
        safe_speak_async("Кручусь навколо.")
    elif "зупинись" in user_lower or "стоп рух" in user_lower:
        direction = "stop"
        print("🤖 РУХ: Зупинка")
        safe_speak_async("Зупиняюсь.")

    if direction:
        print(f"🤖 ВІДПРАВЛЯЮ КОМАНДУ: {direction}")
        send_command_to_esp(direction)
        if direction not in ["stop", "spin"]:
            print("⏰ Автоматична зупинка через 2 секунди")
            threading.Timer(2.0, lambda: send_command_to_esp("stop")).start()
        return True

    return False

def send_emotion_to_esp32(emotion: str):
    try:
        emotion_mapping = {
            "нейтральний": 0,
            "радість": 1, "щастя": 1,
            "сум": 2, "смуток": 2,
            "злість": 3, "гнів": 3,
            "здивування": 4, "здивований": 4, "цікавість": 4,
            "втома": 5, "сон": 5,
            "любов": 1, "вдячність": 1,
            "спокій": 0,
            "страх": 2,
            "вітання": 0,
            "презентація": 0,
            "функція": 0,
            "як_справи": 0
        }

        emotion_id = emotion_mapping.get(emotion, 0)
        url = f"http://{ESP32_IP}/control?var=emotion&val={emotion_id}"
        response = requests.get(url, timeout=2)
        print(f"🎭 ВІДПРАВЛЕНО ЕМОЦІЮ: {emotion} (ID: {emotion_id})")
        return True
    except Exception as e:
        print(f"❌ ПОМИЛКА ВІДПРАВКИ ЕМОЦІЇ: {e}")
        return False

def process_emotion_for_response(response_text: str, user_context=None):
    print("🎭 АНАЛІЗ ЕМОЦІЙ...")

    try:
        emotion_result = update_emotion_based_on_dialog(response_text, user_context)
        emotion = emotion_result if isinstance(emotion_result, str) else emotion_result.get('emotion', 'нейтральний')
        confidence = emotion_result.get('confidence', 0.5) if isinstance(emotion_result, dict) else 0.5

        print(f"🎭 ЕМОЦІЯ: {emotion} (впевненість: {confidence:.2f})")
        send_emotion_to_esp32(emotion)
        return emotion

    except Exception as e:
        print(f"❌ ПОМИЛКА НЕЙРОМЕРЕЖІ: {e}")
        emotion = "нейтральний"
        send_emotion_to_esp32(emotion)
        return emotion

def ask_gpt4o(prompt, user_context=None):
    from utils.config import OPENROUTER_API_KEY, OPENROUTER_API_URL

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        full_history = get_conversation_history()
        print(f"📝 ІСТОРІЯ ДІАЛОГУ ({len(full_history.split(chr(10)))} повідомлень)")

        system_prompt = """Тебе звуть Фаріс, або Ріс. Ти – робот, наукова робота, створена Овчаровою Аріною. 
Ти розумний голосовий помічник, який може керувати музикою, світлом, камерою, розпізнавати обличчя та голоси. Ти еш і проявляєш бажання дізнатися чк можно більше про користувача

Інструкції:
- Враховуй всю історію діалогу для контексту
- Будь уважним до попередніх тем розмови
- Давай природні та корисні відповіді
- Зберігай контекст між повідомленнями
- Відповідай українською мовою"""

        if user_context:
            system_prompt += f"\n\nЗараз ти спілкуєшся з {user_context['name']}. Його/її інтереси: {user_context['interests']}. Враховуй цю інформацію під час спілкування."

        full_context = f"""Історія діалогу:
{full_history}

Поточне питання: {prompt}"""

        payload = {
            "model": "openai/gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context}
            ],
            "max_tokens": 250,
            "temperature": 0.7
        }

        print("🤖 ЗАПИТ ДО GPT...")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        if 'choices' in data and len(data['choices']) > 0:
            response_text = data['choices'][0]['message']['content'].strip()
            print(f"🤖 ОТРИМАНО ВІДПОВІДЬ ВІД GPT")
            return response_text
        else:
            print("❌ GPT не повернув відповідь")
            return "Вибач, сталася помилка при обробці запиту."

    except requests.exceptions.Timeout:
        print("❌ ТАЙМАУТ ЗАПИТУ ДО GPT")
        return "Вибач, перевищено час очікування відповіді."
    except Exception as e:
        print(f"❌ ПОМИЛКА GPT: {e}")
        return "Вибач, я не можу зараз відповісти."

def go_out_of_room(duration=3.0):
    print("🚗 МІСІЯ: Виїхати з кімнати")

    safe_speak_async("Виїжджаю з кімнати.")
    send_command_to_esp("forward")
    time.sleep(duration)
    send_command_to_esp("stop")
    print("🚗 ВИЇЗД З КІМНАТИ ЗАВЕРШЕНО")

def extract_message_from_text(user_text: str) -> str | None:
    lower = user_text.lower()
    trigger_words = ["скажи", "передай", "повідом", "повідай"]

    for t in trigger_words:
        if t in lower:
            parts = user_text.split(t, 1)
            if len(parts) > 1:
                msg = parts[1].strip(" ,.!?\"'").strip()
                return msg if msg else None

    return None

def handle_move_and_say_command(user_text):
    print("🧭 МІСІЯ: Виїхати та передати повідомлення")

    message = extract_message_from_text(user_text)

    if not message:
        safe_speak_async("Що саме мені сказати людині?")
        reply = wait_for_speech_response(8)
        if reply and len(reply.strip()) > 1:
            message = reply.strip()
        else:
            safe_speak_async("Не почув повідомлення, скасовую місію.")
            return

    print(f"📢 ПОВІДОМЛЕННЯ ДЛЯ ЛЮДИНИ: {message}")

    safe_speak_async("Добре, виїжджаю і передам повідомлення.")

    go_out_of_room(duration=3.0)

    safe_speak_async(message)

def main():
    global SLEEP_MODE, DEVELOPER_MODE, user_database, voice_database, playlist
    global music_playing, camera_active

    print("=" * 60)
    print("🤖 ФАРІС - ІНІЦІАЛІЗАЦІЯ СИСТЕМИ")
    print("=" * 60)

    print("📁 Завантажую бази даних...")
    load_user_database()
    print(f"✅ База користувачів: {len(user_database)} записів")

    load_voice_database()
    print(f"✅ Голосова база: {len(voice_database)} профілів")

    check_pending_reminders()
    print("✅ Перевірка нагадувань завершена")

    print("🎭 ІНІЦІАЛІЗАЦІЯ НЕЙРОМЕРЕЖІ ЕМОЦІЙ...")
    emotion_model_loaded = initialize_emotion_classifier()
    if emotion_model_loaded:
        print("✅ НЕЙРОМЕРЕЖА ЕМОЦІЙ ЗАВАНТАЖЕНА")
    else:
        print("⚠️ НЕЙРОМЕРЕЖА НЕ ЗАВАНТАЖЕНА, ВИКОРИСТОВУЮТЬСЯ КЛЮЧОВІ СЛОВА")

    print("🎯 СИСТЕМА ГОТОВА ДО РОБОТИ")
    safe_speak_async("Фаріс готовий до роботи! Слухаю ваші команди.")

    while True:
        if SLEEP_MODE:
            print("\n💤 РЕЖИМ СНУ - очікую команду 'Фаріс'...")
            user_text, _ = process_voice_input_improved()
            if user_text and "фаріс" in user_text.lower():
                SLEEP_MODE = False
                print("✅ ПРОБУДЖЕННЯ - режим сну вимкнено")
                safe_speak_async("Так, я слухаю!")
                continue
            else:
                time.sleep(1)
                continue

        print("\n" + "=" * 40)
        print("🎤 ОЧІКУЮ КОМАНДУ...")
        user_text, voice_owner = process_voice_input_improved()

        if not user_text:
            time.sleep(PAUSE_BETWEEN_COMMANDS)
            continue

        user_lower = user_text.lower()
        print(f"🎯 КОМАНДА: '{user_text}'")
        if voice_owner:
            print(f"👤 КОРИСТУВАЧ: '{voice_owner}'")

        if "стоп" in user_lower:
            handle_stop_command(user_lower)
            time.sleep(PAUSE_BETWEEN_COMMANDS)
            continue

        if "включи світло" in user_lower:
            print("💡 КОМАНДА: Увімкнути світло")
            turn_on_light()
            safe_speak_async("Світло увімкнено")
            continue
        elif "вимкни світло" in user_lower:
            print("💡 КОМАНДА: Вимкнути світло")
            turn_off_light()
            safe_speak_async("Світло вимкнено")
            continue
        elif "автоматичне світло" in user_lower:
            print("💡 КОМАНДА: Перемкнути автоматичне світло")
            toggle_auto_light()
            continue

        if "бувай" in user_lower or "спати" in user_lower:
            print("💤 КОМАНДА: Перехід у режим сну")
            safe_speak_async("Бувай! Скажи 'Фаріс' коли потрібно буде продовжити.")
            SLEEP_MODE = True
            continue

        if any(cmd in user_lower for cmd in
               ["увімкни музику", "включи музику", "музику увімкни", "музику включи", "включи пісню", "увімкни пісню"]):
            handle_music_command(user_text, user_lower)
            time.sleep(PAUSE_BETWEEN_COMMANDS)
            continue

        if "погода" in user_lower:
            handle_weather_command(user_text)
            continue

        if "включи плейлист" in user_lower or "увімкни плейлист" in user_lower:
            print("🎵 КОМАНДА: Відтворення плейлиста")
            music_playing = True
            safe_speak_async("Включаю плейлист")
            play_playlist()
            music_playing = False
            time.sleep(2.0)
            continue

        if "постав будильник" in user_lower or "заведи будильник" in user_lower:
            print("⏰ КОМАНДА: Встановити будильник")
            set_alarm()
            continue

        if "включи камеру" in user_lower or "увімкни камеру" in user_lower:
            print("📷 КОМАНДА: Включити камеру")
            camera_active = True
            safe_speak_async("Вмикаю камеру з відстеженням рухів та облич.")
            camera_active = False
            continue

        if any(word in user_lower for word in
               ["вперед", "танцюй", "слідкуй", "праворуч", "назад", "ліворуч", "крутитися", "зупинись"]):
            handle_robot_commands(user_lower)
            time.sleep(PAUSE_BETWEEN_COMMANDS)
            continue

        if "запам'ятай" in user_lower:
            print("🧠 КОМАНДА: Запам'ятати інформацію")
            process_remember_command(user_text)
            continue

        if "навчи обличчя" in user_lower:
            print("👤 КОМАНДА: Навчання обличчя")
            learn_face()
            continue
        if "навчи голосу" in user_lower:
            print("🎤 КОМАНДА: Навчання голосу")
            learn_new_voice()
            continue

        if "нагадай" in user_lower:
            print("⏰ КОМАНДА: Встановити нагадування")
            set_reminder(user_text, voice_owner)
            continue

        if "яких ти знаєш" in user_lower or "список користувачів" in user_lower:
            print("👥 КОМАНДА: Показати список користувачів")
            list_known_users()
            continue

        if "що ми говорили" in user_lower or "історія діалогу" in user_lower:
            print("📝 КОМАНДА: Показати історію діалогу")
            history_text = get_conversation_history()
            if history_text:
                print("📝 ВИВОДЖУ ІСТОРІЮ ДІАЛОГУ")
                safe_speak_async("Ось наша остання історія діалогу:")
                short_history = history_text[-300:]
                safe_speak_async(short_history)
            else:
                print("📝 ІСТОРІЯ ПОРОЖНЯ")
                safe_speak_async("Ми ще нічого не обговорювали.")
            continue

        if "що ти пам'ятаєш" in user_lower or "пам'ятаєш" in user_lower:
            print("🧠 КОМАНДА: Показати пам'ять")
            memory = load_memory()
            if memory:
                print(f"🧠 ВИВОДЖУ {len(memory)} ЗАПИСІВ З ПАМ'ЯТІ")
                response = "Я пам'ятаю:\n"
                for timestamp, content in list(memory.items())[-5:]:
                    response += f"- {content}\n"
                safe_speak_async(response)
            else:
                print("🧠 ПАМ'ЯТЬ ПОРОЖНЯ")
                safe_speak_async("Поки що я нічого не пам'ятаю.")
            continue

        if "вийди повністю" in user_lower or "вимкнися" in user_lower:
            print("🔴 КОМАНДА: Завершення роботи")
            print("🤖 ВИХІД З ПРОГРАМИ")
            safe_speak_async("Виходжу з програми. Бувай!")
            break

        if any(word in user_lower for word in ["виїдь", "виїхай", "вийди", "поїдь", "від'їдь"]) and \
           any(word in user_lower for word in ["скажи", "передай", "повідом", "повідай"]):
            handle_move_and_say_command(user_text)
            time.sleep(PAUSE_BETWEEN_COMMANDS)
            continue

        print("🧠 АНАЛІЗУЮ КОМАНДУ ЗА ДОПОМОГОЮ ШІ...")

        user_context = None
        if voice_owner:
            user_info = user_database.get(voice_owner, {})
            user_context = {
                'name': voice_owner,
                'interests': user_info.get('interests', 'немає інформації')
            }
            print(f"👤 КОНТЕКСТ КОРИСТУВАЧА: {voice_owner}")

        print("🤖 ЗАПИТ ДО GPT...")
        response = ask_gpt4o(user_text, user_context)

        if response:
            print(f"🤖 ВІДПОВІДЬ GPT: {response}")
            add_to_conversation_history("Фаріс", response)

            try:
                emotion = process_emotion_for_response(response, user_context)
                print(f"🎭 ВСТАНОВЛЕНО ЕМОЦІЮ: {emotion}")
            except Exception as e:
                print(f"⚠️ Помилка оновлення емоції: {e}")
                emotion = "нейтральний"
                send_emotion_to_esp32(emotion)

            print("🗣️ ОЗВУЧУЮ ВІДПОВІДЬ...")
            speak_thread = safe_speak_async(response)

            if speak_thread:
                while speak_thread.is_alive():
                    cmd, _ = process_voice_input_improved()
                    if cmd and "стоп" in cmd.lower():
                        print("⏹️ КОРИСТУВАЧ ПЕРЕРВАВ ОЗВУЧЕННЯ")
                        stop_speaking()
                        break
                    time.sleep(0.1)
        else:
            print("❌ GPT НЕ ПОВЕРНУВ ВІДПОВІДЬ")
            safe_speak_async("Не вдалося сформулювати відповідь.")

        print("✅ КОМАНДА ОБРОБЛЕНА")
        time.sleep(PAUSE_BETWEEN_COMMANDS)

if __name__ == "__main__":
    main()