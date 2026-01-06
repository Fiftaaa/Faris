import cv2
import numpy as np
import requests
import time
import mediapipe as mp
from face.recognition import recognize_face
from voice.recognition import recognize_speech
from voice.synthesis import speak_async
from face.training import learn_face
from hardware.esp32_control import send_command_to_esp, turn_on_light, turn_off_light
from hardware.gestures import init_hand_detector, detect_hand_skeleton, get_hand_gesture, get_finger_direction, \
    draw_hand_skeleton


AUTO_LIGHT_ENABLED = False
_LAST_LIGHT_STATE = None
_BRIGHT_LOW = 70
_BRIGHT_HIGH = 110


def set_auto_light(enabled: bool) -> bool:
    global AUTO_LIGHT_ENABLED
    AUTO_LIGHT_ENABLED = bool(enabled)
    try:
        speak_async(f"Автоматичне світло {'увімкнено' if AUTO_LIGHT_ENABLED else 'вимкнено'}.")
    except Exception:
        pass
    print(f"[AUTO-LIGHT] Enabled = {AUTO_LIGHT_ENABLED}")
    return AUTO_LIGHT_ENABLED


def toggle_auto_light() -> bool:
    return set_auto_light(not AUTO_LIGHT_ENABLED)


def _maybe_adjust_light(frame_gray: np.ndarray):
    global _LAST_LIGHT_STATE
    if not AUTO_LIGHT_ENABLED:
        return

    try:
        mean_luma = float(frame_gray.mean())
    except Exception:
        return

    if _LAST_LIGHT_STATE is None:
        _LAST_LIGHT_STATE = 'on' if mean_luma < (_BRIGHT_LOW + _BRIGHT_HIGH) / 2 else 'off'

    if _LAST_LIGHT_STATE == 'off' and mean_luma < _BRIGHT_LOW:
        try:
            turn_on_light()
            _LAST_LIGHT_STATE = 'on'
            print(f"[AUTO-LIGHT] ON (mean={mean_luma:.1f})")
        except Exception as e:
            print(f"[AUTO-LIGHT] ON failed: {e}")
    elif _LAST_LIGHT_STATE == 'on' and mean_luma > _BRIGHT_HIGH:
        try:
            turn_off_light()
            _LAST_LIGHT_STATE = 'off'
            print(f"[AUTO-LIGHT] OFF (mean={mean_luma:.1f})")
        except Exception as e:
            print(f"[AUTO-LIGHT] OFF failed: {e}")


def start_camera_tracking_with_recognition():

    print("📷 ЗАПУСК КАМЕРИ З РОЗПІЗНАВАННЯМ")

    esp32cam_url = "http://192.168.4.1/capture"
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    hand_detector = init_hand_detector()

    camera_active = True
    last_unknown_face_time = 0
    learn_offered = False

    try:
        while camera_active:
            response = requests.get(esp32cam_url, timeout=2)
            if response.status_code == 200:
                img_array = np.array(bytearray(response.content), dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                frame = cv2.resize(frame, (480, 640))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _maybe_adjust_light(gray)

                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                face_detected = False
                known_face_detected = False
                current_face_name = None

                for (x, y, w, h) in faces:
                    face_detected = True
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    face_roi = frame[y:y + h, x:x + w]
                    name = recognize_face(face_roi)

                    if name:
                        known_face_detected = True
                        current_face_name = name
                        cv2.putText(frame, f"Вітаю, {name}!", (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        learn_offered = False  # Скидаємо пропозицію навчання
                    else:
                        cv2.putText(frame, "Невідоме обличчя", (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                if face_detected and not known_face_detected and not learn_offered:
                    current_time = time.time()
                    if current_time - last_unknown_face_time > 5:  # Чекаємо 5 секунд
                        last_unknown_face_time = current_time
                        learn_offered = True
                        print("👤 НЕВІДОМЕ ОБЛИЧЧЯ - пропоную навчання")
                        send_command_to_esp("stop")
                        cv2.putText(frame, "Нове обличчя! Пропоную навчання...", (50, 300),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                        cv2.imshow('Камера - Відстеження облич та рук', frame)
                        cv2.waitKey(1)

                        speak_async(
                            "Я бачу нове обличчя. Хочете, щоб я навчився його розпізнавати? Скажіть 'так' або 'ні'.")


                        response = recognize_speech(timeout=10)
                        if response and "так" in response.lower():
                            print("✅ КОРИСТУВАЧ ПОГОДИВСЯ НА НАВЧАННЯ")
                            speak_async("Чудово! Починаю навчання.")
                            cv2.destroyAllWindows()
                            learn_face()
                            return
                        elif response and "ні" in response.lower():
                            print("❌ КОРИСТУВАЧ ВІДМОВИВСЯ ВІД НАВЧАННЯ")
                            speak_async("Добре, не буду навчатися.")
                        else:
                            print("❌ НЕ ЗРОЗУМІЛА ВІДПОВІДЬ")
                            speak_async("Не зрозумів вашу відповідь.")


                hand_landmarks, handedness = detect_hand_skeleton(frame, hand_detector)
                if hand_landmarks:
                    gesture, fingers_up = get_hand_gesture(hand_landmarks, frame.shape[1], frame.shape[0])
                    direction, angle = get_finger_direction(hand_landmarks, frame.shape[1], frame.shape[0])


                    if gesture == "fist":
                        send_command_to_esp("forward")
                        status_text = "Їду вперед - кулак"
                    elif gesture == "open_hand":
                        send_command_to_esp("stop")
                        status_text = "Стою - відкрита рука"
                    elif gesture == "one_finger":
                        if direction == "left":
                            send_command_to_esp("left")
                            status_text = "Поворот ліворуч - вказівний палець"
                        elif direction == "right":
                            send_command_to_esp("right")
                            status_text = "Поворот праворуч - вказівний палець"
                        else:
                            send_command_to_esp("forward")
                            status_text = "Їду вперед - вказівний палець"
                    else:
                        send_command_to_esp("stop")
                        status_text = "Стою - інший жест"

                    frame = draw_hand_skeleton(frame, hand_landmarks, gesture, direction)
                    cv2.putText(frame, status_text, (10, frame.shape[0] - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                else:
                    send_command_to_esp("stop")
                    cv2.putText(frame, "Рука не знайдена", (10, frame.shape[0] - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                cv2.putText(frame, "Режим камери: Відстеження облич та рук", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                cv2.putText(frame, f"Auto-light: {'ON' if AUTO_LIGHT_ENABLED else 'OFF'}", (10, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                if current_face_name:
                    cv2.putText(frame, f"Розпізнано: {current_face_name}", (10, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, "Обличчя: не розпізнано", (10, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.putText(frame, "Скажіть 'стоп' для виходу", (10, 105),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                cv2.imshow('Камера - Відстеження облич та рук', frame)
            try:
                voice_command = recognize_speech(timeout=1)
                if voice_command and "стоп" in voice_command.lower():
                    print("📷 КОМАНДА ВИХОДУ З КАМЕРИ")
                    camera_active = False
                    speak_async("Вимикаю камеру.")
                    break
            except:
                pass

            if cv2.waitKey(1) & 0xFF == ord('q'):
                camera_active = False
                break

            time.sleep(0.1)

    except Exception as e:
        print(f"❌ ПОМИЛКА КАМЕРИ: {e}")
        speak_async("Помилка роботи камери.")

    finally:
        cv2.destroyAllWindows()
        send_command_to_esp("stop")
        print("📷 КАМЕРА ВИМКНЕНА")
