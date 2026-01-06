import json
import os
import re
import time
import threading
from datetime import datetime, timedelta
from voice.synthesis import speak_async
from utils.config import REMINDERS_FILE

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {}
    return {}

def save_reminders(reminders):
    try:
        with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        return False

def parse_reminder_time(text):
    now = datetime.now()
    time_match = re.search(r'через\s+(\d+)\s+(хвилин|хвилини|хвилину|годин|години|годину)', text.lower())
    if time_match:
        amount = int(time_match.group(1))
        unit = time_match.group(2)
        if 'хвилин' in unit:
            reminder_time = now + timedelta(minutes=amount)
        else:
            reminder_time = now + timedelta(hours=amount)
        return reminder_time, f"через {amount} {unit}"
    time_match = re.search(r'о\s+(\d{1,2})[:.](\d{2})', text.lower())
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        if 'завтра' in text.lower():
            reminder_time = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=1)
            time_desc = f"завтра о {hour:02d}:{minute:02d}"
        else:
            reminder_time = datetime(now.year, now.month, now.day, hour, minute)
            if reminder_time < now:
                reminder_time += timedelta(days=1)
                time_desc = f"завтра о {hour:02d}:{minute:02d}"
            else:
                time_desc = f"сьогодні о {hour:02d}:{minute:02d}"
        return reminder_time, time_desc
    return now + timedelta(seconds=10), "негайно"

def set_reminder(user_text, voice_owner=None):
    clean_text = re.sub(r'нагадай|нагадування|що|щоб', '', user_text, flags=re.IGNORECASE).strip()
    if not clean_text:
        speak_async("Не вказано, про що нагадати.")
        return False
    reminder_time, time_desc = parse_reminder_time(user_text)
    reminders = load_reminders()
    reminder_id = str(int(time.time()))
    reminders[reminder_id] = {
        'text': clean_text,
        'time': reminder_time.strftime("%Y-%m-%d %H:%M:%S"),
        'owner': voice_owner or 'невідомий',
        'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if save_reminders(reminders):
        speak_async(f"✅ Нагадування встановлено! Нагадаю {time_desc}: {clean_text}")
        threading.Thread(
            target=wait_for_reminder,
            args=(reminder_id, clean_text, reminder_time),
            daemon=True
        ).start()
        return True
    else:
        speak_async("❌ Не вдалося встановити нагадування.")
        return False

def wait_for_reminder(reminder_id, text, reminder_time):
    try:
        now = datetime.now()
        if reminder_time > now:
            wait_seconds = (reminder_time - now).total_seconds()
            time.sleep(wait_seconds)
        speak_async(f"🔔 Нагадування: {text}")
        reminders = load_reminders()
        if reminder_id in reminders:
            del reminders[reminder_id]
            save_reminders(reminders)
    except Exception as e:
        pass

def check_pending_reminders():
    reminders = load_reminders()
    now = datetime.now()
    for reminder_id, reminder in reminders.items():
        reminder_time = datetime.strptime(reminder['time'], "%Y-%m-%d %H:%M:%S")
        if reminder_time <= now:
            threading.Thread(
                target=speak_async,
                args=(f"⏰ Прострочене нагадування: {reminder['text']}",),
                daemon=True
            ).start()
            del reminders[reminder_id]
            save_reminders(reminders)
        else:
            threading.Thread(
                target=wait_for_reminder,
                args=(reminder_id, reminder['text'], reminder_time),
                daemon=True
            ).start()