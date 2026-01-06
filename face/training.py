import cv2
import numpy as np
import requests
import time
import datetime
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
from face.recognition import extract_face_features, load_face_data, save_face_data
from voice.recognition import recognize_speech
from voice.synthesis import speak_async
from utils.config import ESP32_CAM_URL


def learn_face():
    print("👤 ПОЧАТОК НАВЧАННЯ ОБЛИЧЧЯ")
    speak_async("Режим навчання обличчя. Будь ласка, скажіть ваше ім'я.")

    name = recognize_speech(timeout=10)
    if not name:
        print("❌ Не вдалося розпізнати ім'я")
        speak_async("Не вдалося розпізнати ім'я. Спробуйте ще раз.")
        return False

    name = name.strip().capitalize()
    print(f"👤 ІМ'Я ДЛЯ НАВЧАННЯ: '{name}'")
    speak_async(f"Навчаюся розпізнавати {name}. Покажіть своє обличчя в камеру. Мені потрібно 20 знімків.")

    esp32cam_url = ESP32_CAM_URL
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    features_list = []
    captured_count = 0

    try:
        # Завантажуємо існуючі дані розпізнавання облич
        classifier, le = load_face_data()
        if classifier is None or le is None:
            print("🔧 Створюю нову модель розпізнавання облич")
            classifier = KNeighborsClassifier(n_neighbors=3)
            le = LabelEncoder()


        print("📸 Збір знімків для навчання...")
        while captured_count < 20:
            response = requests.get(esp32cam_url, timeout=2)
            if response.status_code == 200:
                img_array = np.array(bytearray(response.content), dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                frame = cv2.resize(frame, (640, 480))

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)

                for (x, y, w, h) in faces:
                    face_roi = frame[y:y + h, x:x + w]

                    features = extract_face_features(face_roi)
                    if features is not None:
                        features_list.append(features)
                        captured_count += 1
                        print(f"📸 Знімок {captured_count}/20 успішно захоплений")

                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, f"Навчання: {name}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Знімків: {captured_count}/20", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(frame, "Дивіться в камеру", (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.imshow('Навчання обличчя', frame)
                cv2.waitKey(1)

            time.sleep(0.3)

        print("🧠 Навчання моделі розпізнавання...")
        if features_list:
            if hasattr(le, 'classes_'):
                existing_classes = list(le.classes_)
                if name not in existing_classes:
                    existing_classes.append(name)
                    le.fit(existing_classes)
            else:
                le.fit([name])

            encoded_labels = le.transform([name] * len(features_list))
            classifier.fit(features_list, encoded_labels)

            if save_face_data(classifier, le):
                print("✅ Модель обличчя успішно навчена та збережена")

                speak_async(
                    f"Чудово, {name}! Тепер розкажіть трохи про себе. Які у вас інтереси, хобі чи улюблені теми?")
                user_info = recognize_speech(timeout=15)

                if user_info:
                    from face.database import load_user_database, save_user_database

                    user_db = load_user_database()
                    user_db[name] = {
                        "interests": user_info,
                        "learned_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    if save_user_database(user_db):
                        print(f"✅ Інформацію про {name} збережено в базі даних")
                        speak_async(f"Дякую! Я запам'ятав вашу інформацію. Радий знайомству, {name}!")
                    else:
                        print(f"❌ Не вдалося зберегти інформацію про {name}")
                        speak_async(f"Інформацію вдалося розпізнати, але виникли проблеми зі збереженням.")
                else:
                    print(f"ℹ️ Інформацію про інтереси не розпізнано, зберігаю лише обличчя")
                    speak_async(f"Інформацію не вдалося розпізнати, але я запам'ятав ваше обличчя, {name}!")

                success_frame = np.zeros((200, 500, 3), dtype=np.uint8)
                cv2.putText(success_frame, "НАВЧАННЯ УСПІШНЕ!", (50, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(success_frame, f"Обличчя {name} додано", (50, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.imshow('Результат', success_frame)
                cv2.waitKey(2000)

                cv2.destroyAllWindows()
                return True
            else:
                print("❌ Помилка збереження моделі обличчя")
                speak_async("Помилка збереження даних.")
        else:
            print("❌ Не вдалося знайти обличчя для навчання")
            speak_async("Не вдалося знайти обличчя для навчання.")

        cv2.destroyAllWindows()
        return False

    except Exception as e:
        print(f"❌ Помилка навчання обличчя: {e}")
        speak_async("Помилка при навчанні обличчя.")
        cv2.destroyAllWindows()
        return False


def update_face_model(classifier, le, name, training_samples):
    try:

        if hasattr(le, 'classes_'):
            existing_classes = list(le.classes_)
            if name not in existing_classes:
                existing_classes.append(name)
                le.fit(existing_classes)
        else:
            le.fit([name])

        encoded_labels = le.transform([name] * len(training_samples))
        classifier.fit(training_samples, encoded_labels)

        if save_face_data(classifier, le):
            print(f"✅ Модель облич оновлено для {name}")
            return classifier, le
        else:
            print(f"❌ Не вдалося оновити модель для {name}")
            return None, None

    except Exception as e:
        print(f"❌ Помилка оновлення моделі облич: {e}")
        return None, None