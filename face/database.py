import json
import os
from utils.config import USER_DB_FILE
from voice.synthesis import speak_async

user_database = {}

def load_user_database():
    global user_database
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, 'r', encoding='utf-8') as f:
                user_database = json.load(f)
        except Exception as e:
            user_database = {}
    return user_database

def save_user_database():
    try:
        with open(USER_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_database, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        return False

def get_user_profile(name):
    from voice.database import voice_database
    voice_profile = voice_database.get(name)
    face_profile = user_database.get(name)
    profile = {
        'name': name,
        'has_voice': voice_profile is not None,
        'has_face': face_profile is not None,
        'interests': face_profile.get('interests', 'не вказано') if face_profile else 'не вказано',
        'voice_learned': voice_profile.get('learned_date', 'не навчений') if voice_profile else 'не навчений',
        'face_learned': face_profile.get('learned_date', 'не навчений') if face_profile else 'не навчений'
    }
    return profile

def list_known_users():
    from voice.database import voice_database
    all_users = set(list(voice_database.keys()) + list(user_database.keys()))
    if not all_users:
        speak_async("Я ще не знаю жодного користувача.")
        return
    speak_async(f"Я знаю {len(all_users)} користувачів:")
    for user in all_users:
        profile = get_user_profile(user)
        status = []
        if profile['has_voice']:
            status.append("голос")
        if profile['has_face']:
            status.append("обличчя")
        speak_async(f"{user} - {', '.join(status)}")