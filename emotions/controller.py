import json
import os
import re
from collections import Counter

current_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(current_dir, "..", "models", "simple_emotion_model.json")

emotion_history = []
MAX_HISTORY = 10
emotion_classifier = None


class SavedEmotionClassifier:
    def __init__(self, model_path):
        with open(model_path, 'r', encoding='utf-8') as f:
            model_data = json.load(f)

        self.emotion_keywords = model_data["emotion_keywords"]
        self.common_words = set(model_data["common_words"])

    def preprocess_text(self, text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        words = [word for word in words if word not in self.common_words and len(word) > 2]
        return words

    def predict(self, text):
        words = self.preprocess_text(text)

        if not words:
            return {"emotion": "нейтральний", "confidence": 0.0}

        emotion_scores = {}

        for emotion, keywords in self.emotion_keywords.items():
            score = 0
            matched_words = 0

            for word in words:
                if word in keywords:
                    score += keywords[word]
                    matched_words += 1

            if len(words) > 0:
                emotion_scores[emotion] = (score / len(words)) * (matched_words / len(words))
            else:
                emotion_scores[emotion] = 0

        if not emotion_scores:
            return {"emotion": "нейтральний", "confidence": 0.0}

        best_emotion = max(emotion_scores.items(), key=lambda x: x[1])
        total_score = sum(emotion_scores.values())
        confidence = best_emotion[1] / total_score if total_score > 0 else 0

        return {
            "emotion": best_emotion[0],
            "confidence": confidence,
            "all_emotions": emotion_scores
        }


def initialize_emotion_classifier():
    global emotion_classifier
    try:
        if os.path.exists(MODEL_PATH):
            emotion_classifier = SavedEmotionClassifier(MODEL_PATH)
            print("✅ Класифікатор емоцій успішно ініціалізовано")
            return True
        else:
            print("❌ Файл моделі не знайдено. Використовуються ключові слова.")
            return False
    except Exception as e:
        print(f"❌ Помилка ініціалізації класифікатора: {e}")
        return False


def update_emotion_based_on_dialog(text: str, user_context=None):
    global emotion_classifier

    if emotion_classifier is not None:
        try:
            prediction = emotion_classifier.predict(text)
            adjusted_emotion = apply_context_rules(prediction['emotion'], user_context, prediction['confidence'])

            emotion_history.append({
                'text': text,
                'predicted_emotion': prediction['emotion'],
                'adjusted_emotion': adjusted_emotion,
                'confidence': prediction['confidence'],
                'timestamp': get_current_timestamp(),
                'method': 'statistical_model'
            })

            if len(emotion_history) > MAX_HISTORY:
                emotion_history.pop(0)

            print(f"🎭 Статистична модель: {adjusted_emotion} (впевненість: {prediction['confidence']:.2f})")
            return adjusted_emotion

        except Exception as e:
            print(f"❌ Помилка статистичної моделі: {e}")

    return fallback_emotion_detection(text)


def apply_context_rules(emotion: str, user_context: dict, confidence: float) -> str:
    if user_context is None:
        return emotion

    if confidence < 0.3:
        pass

    if user_context.get('is_urgent', False) and emotion == "спокій":
        return "цікавість"

    if len(emotion_history) > 0:
        previous_emotion = emotion_history[-1]['adjusted_emotion']
        if previous_emotion == "радість" and emotion == "злість":
            return "сум"

    return emotion


def fallback_emotion_detection(text: str) -> str:
    text_lower = text.lower()

    emotion_keywords = {
        "радість": ["радість", "щастя", "весело", "сміх", "чудово", "прекрасно", "добре", "радий", "рада"],
        "сум": ["сум", "сумно", "печаль", "гірко", "жаль", "туга", "погано", "смуток"],
        "злість": ["злість", "злий", "сердитий", "злюсь", "дратує", "бісить", "гнів", "лютий"],
        "вдячність": ["дякую", "вдячний", "вдячна", "спасибі", "дякувати", "вдячність"],
        "втома": ["втома", "втомився", "втомилась", "стомлений", "стомлена", "втоми", "утома"],
        "вітання": ["привіт", "вітаю", "здоров", "добрий день", "доброго ранку", "добрий вечір"],
        "любов": ["любов", "кохаю", "подобається", "милий", "мила", "кохання", "любий"],
        "спокій": ["спокій", "спокійно", "мир", "тихо", "гармонія", "заспокоєння"],
        "страх": ["страх", "боюсь", "жах", "страшно", "злякався", "злякалась", "переляк"],
        "цікавість": ["цікаво", "дивно", "питання", "чому", "як", "що", "цікавить"],
        "як_справи": ["як справи", "що нового", "як ти", "як почуваєшся", "як життя"],
        "презентація": ["презентація", "представляю", "знайомтесь", "це я", "мене звати"],
        "функція": ["функція", "можеш", "вмієш", "зроби", "зробити", "команда"]
    }

    for emotion, keywords in emotion_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            emotion_history.append({
                'text': text,
                'predicted_emotion': emotion,
                'adjusted_emotion': emotion,
                'confidence': 0.8,
                'timestamp': get_current_timestamp(),
                'method': 'keyword_based'
            })

            if len(emotion_history) > MAX_HISTORY:
                emotion_history.pop(0)

            print(f"🎭 Ключові слова: {emotion}")
            return emotion

    default_emotion = "нейтральний"
    emotion_history.append({
        'text': text,
        'predicted_emotion': default_emotion,
        'adjusted_emotion': default_emotion,
        'confidence': 0.5,
        'timestamp': get_current_timestamp(),
        'method': 'default'
    })

    return default_emotion


def get_emotion_trend(window_size: int = 5):
    if len(emotion_history) < window_size:
        return {"trend": "недостатньо даних", "dominant_emotion": "нейтральний"}

    recent_emotions = [entry['adjusted_emotion'] for entry in emotion_history[-window_size:]]
    emotion_counts = {emotion: recent_emotions.count(emotion) for emotion in set(recent_emotions)}
    dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0]

    return {
        "trend": dominant_emotion,
        "confidence": emotion_counts[dominant_emotion] / window_size,
        "emotion_distribution": emotion_counts,
        "method_used": emotion_history[-1]['method'] if emotion_history else "unknown"
    }


def set_emotion_directly(emotion):
    emotion_history.append({
        'text': 'manual_set',
        'predicted_emotion': emotion,
        'adjusted_emotion': emotion,
        'confidence': 1.0,
        'timestamp': get_current_timestamp(),
        'method': 'manual'
    })
    if len(emotion_history) > MAX_HISTORY:
        emotion_history.pop(0)


def get_current_emotion():
    if emotion_history:
        return emotion_history[-1]['adjusted_emotion']
    return "нейтральний"


def get_emotion_history():
    return emotion_history.copy()


def get_current_timestamp():
    from datetime import datetime
    return datetime.now().isoformat()


def init():
    print("🎭 Ініціалізація системи розпізнавання емоцій...")
    initialize_emotion_classifier()


init()