import speech_recognition as sr
import numpy as np
import time
from utils.helpers import add_to_conversation_history


def recognize_speech(timeout=None):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            print("🎤 Слухаю...")
            if timeout:
                audio = recognizer.listen(source, timeout=timeout)
            else:
                audio = recognizer.listen(source)
            text = recognizer.recognize_google(audio, language="uk-UA")
            print(f"💬 РОЗПІЗНАНО: '{text}'")
            add_to_conversation_history("Користувач", text)
            return text
        except sr.WaitTimeoutError:
            print("⏰ Час очікування вийшов")
            return ""
        except sr.UnknownValueError:
            print("❌ Не розпізнано мову")
            return ""
        except sr.RequestError as e:
            print(f"❌ Помилка сервісу розпізнавання: {e}")
            return ""


def record_audio_sample(timeout=5):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            print("🎤 Запис голосу...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.listen(source, timeout=timeout, phrase_time_limit=4)
            print("✅ Аудіо записано")
            return audio_data
        except sr.WaitTimeoutError:
            print("⏰ Час запису вийшов")
            return None
        except Exception as e:
            print(f"❌ Помилка запису аудіо: {e}")
            return None


def extract_voice_features(audio_data, sample_rate=16000):
    try:
        if isinstance(audio_data, sr.AudioData):
            audio_array = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
        else:
            audio_array = audio_data
        features = [
            np.mean(audio_array),
            np.std(audio_array),
            np.mean(np.abs(audio_array)),
            np.median(audio_array),
            np.max(audio_array),
            np.min(audio_array)
        ]
        fft = np.fft.fft(audio_array)
        spectral_centroid = np.mean(np.abs(fft))
        features.extend([spectral_centroid])
        return np.array(features)
    except Exception as e:
        print(f"❌ Помилка екстракції голосових особливостей: {e}")
        return None


def process_voice_input():
    print("\n" + "=" * 50)
    print("🎤 ОЧІКУЮ ГОЛОСОВУ КОМАНДУ...")
    audio_data = record_audio_sample(timeout=7)

    if audio_data is None:
        print("❌ Не вдалося записати аудіо")
        return None, None

    from voice.database import recognize_voice
    recognized_name = recognize_voice(audio_data)
    print(f"👤 РОЗПІЗНАНИЙ ГОЛОС: '{recognized_name or 'невідомий'}'")

    try:
        recognizer = sr.Recognizer()
        text = recognizer.recognize_google(audio_data, language="uk-UA")
        print(f"💬 ТЕКСТ КОМАНДИ: '{text}'")
        add_to_conversation_history("Користувач", text)
        return text, recognized_name
    except sr.UnknownValueError:
        print("❌ Не вдалося розпізнати текст з аудіо")
        return None, recognized_name
    except sr.RequestError as e:
        print(f"❌ Помилка сервісу розпізнавання: {e}")
        return None, recognized_name