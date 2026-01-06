import re
import requests
from collections import deque

conversation_history = deque(maxlen=20)


def add_to_conversation_history(speaker: str, text: str):
    conversation_history.append(f"{speaker}: {text}")


def get_conversation_history():
    return "\n".join(conversation_history)


def get_weather(location: str = "Київ") -> str:
    try:
        resp = requests.get(f"http://wttr.in/{location}?format=%C+%t", timeout=5)
        if resp.status_code != 200:
            return "Не вдалося отримати погоду."

        weather_data = resp.text.strip()
        parts = weather_data.split(" ")
        temp = parts[-1]
        condition = " ".join(parts[:-1])

        # Спрощений переклад
        condition_uk = condition
        if "sunny" in condition.lower():
            condition_uk = "Сонячно"
        elif "cloudy" in condition.lower():
            condition_uk = "Хмарно"
        elif "rain" in condition.lower():
            condition_uk = "Дощ"

        return f"Погода у {location}: {condition_uk}, {temp}"
    except Exception:
        return "Помилка при отриманні погоди."


def extract_song_name(text):
    text = text.lower().replace("фаріс", "").strip()

    patterns = [
        r"(?:увімкни|включи)\s+музику\s+(.+)",
        r"(?:увімкни|включи)\s+(.+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None