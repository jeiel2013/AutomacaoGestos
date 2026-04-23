#!/usr/bin/env python3
"""
debug_landmarks.py
------------------
Ferramenta visual para descobrir vetores de gestos novos.
Usa a nova API mediapipe.tasks (0.10.13+).

Uso:
  python3 debug_landmarks.py

Faça o gesto na frente da câmera e veja o vetor no terminal e na janela.
Pressione 'q' para sair.
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker
from pathlib import Path
from gestures.static import fingers_up

BASE  = Path(__file__).parent
MODEL = BASE / "hand_landmarker.task"

if not MODEL.exists():
    print("ERRO: hand_landmarker.task não encontrado.")
    print("Execute: wget -q https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task -O hand_landmarker.task")
    exit(1)

# Conexões dos landmarks para desenhar o esqueleto da mão
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

options = HandLandmarkerOptions(
    base_options=mp_tasks.BaseOptions(model_asset_path=str(MODEL)),
    num_hands=1,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.7,
    min_tracking_confidence=0.7,
    running_mode=mp_vision.RunningMode.IMAGE,
)

cap = cv2.VideoCapture(0)
print("=== Debug de gestos ===")
print("Faça o gesto na câmera. Pressione 'q' para sair.\n")

with HandLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame    = cv2.flip(frame, 1)
        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = landmarker.detect(mp_image)

        h, w = frame.shape[:2]

        if result.hand_landmarks:
            lms = result.hand_landmarks[0]

            # Desenhar esqueleto
            for a, b in HAND_CONNECTIONS:
                x1, y1 = int(lms[a].x * w), int(lms[a].y * h)
                x2, y2 = int(lms[b].x * w), int(lms[b].y * h)
                cv2.line(frame, (x1,y1), (x2,y2), (0,200,80), 2)

            # Desenhar pontos
            for lm in lms:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 4, (0, 255, 120), -1)

            # Calcular e mostrar vetor
            f     = fingers_up(lms)
            label = f"Dedos: {f}   Tupla: {tuple(f)}"
            print(f"\r{label}   ", end="", flush=True)
            cv2.putText(frame, label, (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 100), 2)

        cv2.imshow("Debug — pressione Q para sair", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
cv2.destroyAllWindows()
print()
