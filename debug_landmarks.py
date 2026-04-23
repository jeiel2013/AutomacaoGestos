#!/usr/bin/env python3
"""
debug_landmarks.py
------------------
Script auxiliar para descobrir o vetor de dedos de um gesto novo.

Uso:
  python3 debug_landmarks.py

Uma janela abre com a imagem da câmera.
Faça o gesto desejado e veja o vetor impresso no terminal e na tela.
Pressione 'q' para sair.

O vetor exibido é: [polegar, indicador, médio, anelar, mínimo]
  1 = levantado / aberto
  0 = abaixado / fechado

Copie o vetor e adicione em gestures/static.py:
  TABLE[(0,1,0,0,0)] = "NOME_DO_SEU_GESTO"
"""

import cv2
import mediapipe as mp
from gestures.static import fingers_up

mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

print("=== Debug de gestos ===")
print("Faça o gesto na frente da câmera.")
print("O vetor aparecerá no terminal e na janela.")
print("Pressione 'q' para sair.\n")

with mp_hands.Hands(
    static_image_mode        = False,
    max_num_hands            = 1,
    model_complexity         = 0,
    min_detection_confidence = 0.7,
    min_tracking_confidence  = 0.7,
) as hands:

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame  = cv2.flip(frame, 1)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        if result.multi_hand_landmarks:
            for lm in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)
                f = fingers_up(lm.landmark)
                label = f"Dedos: {f}  Tupla: {tuple(f)}"
                print(f"\r{label}   ", end="", flush=True)
                cv2.putText(
                    frame, label, (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 100), 2,
                )

        cv2.imshow("Debug — pressione Q para sair", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
cv2.destroyAllWindows()
print()
