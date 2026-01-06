import cv2
import numpy as np
import requests
import time
import pickle
import os
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
from utils.config import FACE_CLASSIFIER_FILE, LABEL_ENCODER_FILE, ESP32_CAM_URL

def extract_face_features(face_image):
    try:
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (100, 100))
        normalized = resized / 255.0
        return normalized.flatten()
    except Exception as e:
        return None

def load_face_data():
    if (os.path.exists(FACE_CLASSIFIER_FILE) and
            os.path.exists(LABEL_ENCODER_FILE)):
        try:
            with open(FACE_CLASSIFIER_FILE, 'rb') as f:
                classifier = pickle.load(f)
            with open(LABEL_ENCODER_FILE, 'rb') as f:
                le = pickle.load(f)
            return classifier, le
        except:
            return None, None
    return None, None

def save_face_data(classifier, le):
    try:
        with open(FACE_CLASSIFIER_FILE, 'wb') as f:
            pickle.dump(classifier, f)
        with open(LABEL_ENCODER_FILE, 'wb') as f:
            pickle.dump(le, f)
        return True
    except Exception as e:
        return False

def recognize_face(frame):
    classifier, le = load_face_data()
    if not classifier or not le:
        return None
    try:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face_roi = frame[y:y + h, x:x + w]
            features = extract_face_features(face_roi)
            if features is not None:
                prediction = classifier.predict([features])
                confidence = classifier.predict_proba([features]).max()
                if confidence > 0.6:
                    name = le.inverse_transform(prediction)[0]
                    return name
        return None
    except Exception as e:
        return None