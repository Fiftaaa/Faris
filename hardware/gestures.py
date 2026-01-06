import cv2
import numpy as np
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

def init_hand_detector():
    return mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

def detect_hand_skeleton(frame, hand_detector):
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hand_detector.process(rgb_frame)
    if results.multi_hand_landmarks and results.multi_handedness:
        hand_landmarks = results.multi_hand_landmarks[0]
        handedness = results.multi_handedness[0].classification[0].label
        return hand_landmarks, handedness
    return None, None

def get_hand_gesture(hand_landmarks, frame_width, frame_height):
    try:
        landmarks = []
        for lm in hand_landmarks.landmark:
            x = int(lm.x * frame_width)
            y = int(lm.y * frame_height)
            landmarks.append((x, y))
        fingers_up = []
        thumb_tip = landmarks[4]
        thumb_mcp = landmarks[2]
        if thumb_tip[0] > thumb_mcp[0]:
            fingers_up.append(1)
        else:
            fingers_up.append(0)
        finger_tips = [8, 12, 16, 20]
        finger_pips = [6, 10, 14, 18]
        for tip, pip in zip(finger_tips, finger_pips):
            if landmarks[tip][1] < landmarks[pip][1]:
                fingers_up.append(1)
            else:
                fingers_up.append(0)
        total_fingers = sum(fingers_up)
        if total_fingers == 0:
            return "fist", fingers_up
        elif total_fingers == 1 and fingers_up[1] == 1:
            return "one_finger", fingers_up
        elif total_fingers >= 2:
            return "open_hand", fingers_up
        else:
            return "unknown", fingers_up
    except Exception as e:
        return "unknown", []

def get_finger_direction(hand_landmarks, frame_width, frame_height):
    try:
        landmarks = []
        for lm in hand_landmarks.landmark:
            x = int(lm.x * frame_width)
            y = int(lm.y * frame_height)
            landmarks.append((x, y))
        index_mcp = landmarks[5]
        index_tip = landmarks[8]
        x_center = index_tip[0] / frame_width
        if x_center < 0.4:
            return "left", 0
        elif x_center > 0.6:
            return "right", 0
        else:
            return "center", 0
    except Exception as e:
        return "center", 0

def draw_hand_skeleton(frame, hand_landmarks, gesture, direction):
    mp_drawing.draw_landmarks(
        frame,
        hand_landmarks,
        mp_hands.HAND_CONNECTIONS,
        mp_drawing_styles.get_default_hand_landmarks_style(),
        mp_drawing_styles.get_default_hand_connections_style()
    )
    cv2.putText(frame, f"Жест: {gesture}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f"Напрямок: {direction}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return frame