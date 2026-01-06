import os

ESP32_IP = "192.168.4.1"
ESP32_CAM_URL = f"http://{ESP32_IP}/capture"

OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

VOICE_DATABASE_FILE = "voice_database.pkl"
USER_DB_FILE = "user_database.json"
MEMORY_JSON_FILE = "assistant_memory.json"
REMINDERS_FILE = "reminders.json"
ALARM_CONFIG_FILE = "alarm_config.json"
PLAYLIST_FILE = "playlist.json"

KNOWN_FACES_DIR = "known_faces"
FACE_ENCODINGS_FILE = "face_encodings.pkl"
FACE_CLASSIFIER_FILE = "face_classifier.pkl"
LABEL_ENCODER_FILE = "label_encoder.pkl"

EMOTIONS = [
    "вітання", "вдячність", "сум", "злість", "спокій",
    "страх", "любов", "втома", "цікавість", "радість", "функція", "презентація"
]

LIGHT_THRESHOLD = 50
AUTO_LIGHT_ENABLED = False
DEVELOPER_MODE = False
SLEEP_MODE = False
