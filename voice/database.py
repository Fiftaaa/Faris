import pickle
import os
import datetime
import numpy as np
import speech_recognition as sr
from voice.recognition import extract_voice_features, record_audio_sample, recognize_speech
from voice.synthesis import speak_async
from utils.config import VOICE_DATABASE_FILE
from utils.helpers import add_to_conversation_history

voice_database = {}


def load_voice_database():
    global voice_database
    if os.path.exists(VOICE_DATABASE_FILE):
        try:
            with open(VOICE_DATABASE_FILE, 'rb') as f:
                voice_database = pickle.load(f)
            print(f"✅ Завантажено {len(voice_database)} голосових профілів")
            for name in voice_database.keys():
                print(f"   👤 {name}")
        except Exception as e:
            print(f"❌ Помилка завантаження голосової бази: {e}")
            voice_database = {}
    else:
        print("📁 Файл голосової бази не знайдено, створю нову")
        voice_database = {}
    return voice_database


def save_voice_database():
    try:
        with open(VOICE_DATABASE_FILE, 'wb') as f:
            pickle.dump(voice_database, f)
        print(f"✅ Голосова база збережена ({len(voice_database)} профілів)")
        return True
    except Exception as e:
        print(f"❌ Помилка збереження голосової бази: {e}")
        return False


def recognize_voice(audio_data):
    global voice_database
    if not voice_database:
        print("🔍 База голосів порожня - немає профілів для порівняння")
        return None

    features = extract_voice_features(audio_data)
    if features is None:
        print("❌ Не вдалося отримати особливості голосу")
        return None

    best_match = None
    best_score = 0
    print(f"🔍 Перевіряю {len(voice_database)} голосових профілів...")

    for name, voice_profile in voice_database.items():
        try:
            stored_features = voice_profile['features']
            distance = np.linalg.norm(features - stored_features)
            similarity = 1 / (1 + distance)
            print(f"   {name}: схожість {similarity:.3f}")

            if similarity > best_score and similarity > 0.6:
                best_score = similarity
                best_match = name
        except Exception as e:
            print(f"⚠️ Помилка порівняння з {name}: {e}")
            continue

    if best_match:
        print(f"✅ НАЙКРАЩИЙ ЗБІГ: '{best_match}' (схожість: {best_score:.3f})")
    else:
        print("❌ ЗБІГІВ НЕ ЗНАЙДЕНО (схожість < 0.6)")

    return best_match


def learn_new_voice():
    global voice_database
    print("\n🎓 ПОЧАТОК НАВЧАННЯ НОВОГО ГОЛОСУ")
    print("🗣️ Скажіть ваше ім'я...")
    speak_async("Давайте навчимося вашому голосу. Скажіть ваше ім'я.")

    name = recognize_speech(timeout=10)
    if not name:
        print("❌ Не вдалося розпізнати ім'я")
        speak_async("Не вдалося розпізнати ім'я. Спробуйте ще раз.")
        return False

    name = name.strip().capitalize()
    print(f"👤 ІМ'Я ДЛЯ НАВЧАННЯ: '{name}'")
    speak_async(f"Чудово, {name}! Тепер будь ласка, скажіть фразу для навчання.")

    samples = []
    successful_samples = 0

    for i in range(3):
        print(f"\n📝 ЗРАЗОК {i + 1} З 3...")
        speak_async(f"Зразок {i + 1} з 3. Скажіть фразу.")

        audio_data = record_audio_sample(timeout=5)
        if audio_data:
            features = extract_voice_features(audio_data)
            if features is not None:
                samples.append(features)
                successful_samples += 1
                print(f"✅ Зразок {i + 1} успішно записаний")
                speak_async("Добре, зрозумів.")
            else:
                print(f"❌ Не вдалося обробити аудіо зразка {i + 1}")
                speak_async("Не вдалося обробити аудіо. Спробуйте ще раз.")
        else:
            print(f"❌ Не вдалося записати аудіо зразка {i + 1}")
            speak_async("Не вдалося записати аудіо. Спробуйте ще раз.")

        time.sleep(1)

    print(f"\n📊 ПІДСУМОК: {successful_samples} з 3 зразків успішних")

    if successful_samples >= 2:
        avg_features = np.mean(samples, axis=0)
        voice_database[name] = {
            'features': avg_features,
            'samples_count': successful_samples,
            'learned_date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if save_voice_database():
            print(f"✅ ГОЛОС '{name}' УСПІШНО НАВЧЕНИЙ!")
            print(f"   📅 Дата навчання: {voice_database[name]['learned_date']}")
            print(f"   📝 Зразків: {successful_samples}")
            speak_async(f"Чудово! Я запам'ятав ваш голос, {name}. Тепер я можу розпізнавати вас.")
            return True
        else:
            print("❌ КРИТИЧНА ПОМИЛКА: не вдалося зберегти голосовий профіль")
            speak_async("Помилка збереження голосового профілю. Спробуйте пізніше.")
            return False
    else:
        print("❌ НЕВДАЛЕ НАВЧАННЯ: недостатньо якісних зразків голосу")
        speak_async("Не вдалося зібрати достатньо якісних зразків голосу. Спробуйте ще раз.")
        return False