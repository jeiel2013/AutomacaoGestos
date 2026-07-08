#!/usr/bin/env python3
"""
collect_data.py
----------------
Ferramenta de coleta de dados para treinar os classificadores de ML.

Uso — gestos ESTÁTICOS (uma pose por vez):
  python collect_data.py static NOME_DO_GESTO

  Pressione ESPAÇO para capturar uma amostra, ESC para sair.
  Recomenda-se capturar 60-100 amostras por gesto, variando levemente
  o ângulo e a distância da mão em relação à câmera.

Uso — gestos DINÂMICOS (sequência de 30 frames):
  python collect_data.py dynamic NOME_DO_GESTO

  Pressione ESPAÇO para iniciar a gravação de uma sequência de 30
  frames, faça o movimento completo enquanto grava. Repita 30-50
  vezes por gesto, variando um pouco a velocidade e amplitude.

Os dados são salvos em:
  gestures/data/static/NOME_DO_GESTO.csv
  gestures/data/dynamic/NOME_DO_GESTO/000.npy, 001.npy, ...

Depois de coletar, treine com:
  python train_static.py
  python train_dynamic.py
"""

import sys
import csv
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker

from gestures.features import extract_static_features, extract_frame_vector

BASE     = Path(__file__).parent
MODEL    = BASE / "hand_landmarker.task"
DATA_DIR = BASE / "gestures" / "data"

SEQ_LEN = 30


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("static", "dynamic"):
        print(__doc__)
        sys.exit(1)

    if not MODEL.exists():
        print("ERRO: hand_landmarker.task não encontrado na pasta do projeto.")
        sys.exit(1)

    mode  = sys.argv[1]
    label = sys.argv[2]

    options = HandLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(MODEL)),
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
        running_mode=mp_vision.RunningMode.IMAGE,
    )

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if mode == "static":
        _collect_static(cap, options, label)
    else:
        _collect_dynamic(cap, options, label)

    cap.release()
    cv2.destroyAllWindows()


def _collect_static(cap, options, label):
    out_dir = DATA_DIR / "static"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{label}.csv"

    print(f"=== Coleta ESTÁTICA: {label} ===")
    print("ESPAÇO = capturar amostra | ESC = sair\n")

    count = 0
    with open(out_file, "a", newline="", encoding="utf-8") as f, \
         HandLandmarker.create_from_options(options) as landmarker:

        writer = csv.writer(f)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame  = cv2.flip(frame, 1)
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_img)

            if result.hand_landmarks:
                lm = result.hand_landmarks[0]
                for p in lm:
                    cx, cy = int(p.x * frame.shape[1]), int(p.y * frame.shape[0])
                    cv2.circle(frame, (cx, cy), 3, (0, 255, 120), -1)

            cv2.putText(frame, f"{label} | amostras: {count}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 100), 2)
            cv2.imshow("Coleta de dados - ESPACO captura, ESC sai", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            if key == 32 and result.hand_landmarks:
                feats = extract_static_features(result.hand_landmarks[0])
                writer.writerow(list(feats) + [label])
                f.flush()
                count += 1
                print(f"\rAmostras capturadas: {count}", end="", flush=True)

    print(f"\n\nTotal salvo em {out_file}: {count} amostras")


def _collect_dynamic(cap, options, label):
    out_dir = DATA_DIR / "dynamic" / label
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = len(list(out_dir.glob("*.npy")))

    print(f"=== Coleta DINÂMICA: {label} ===")
    print("ESPAÇO = iniciar gravação de 30 frames | ESC = sair\n")

    with HandLandmarker.create_from_options(options) as landmarker:
        recording = False
        buffer    = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame  = cv2.flip(frame, 1)
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_img)

            status = f"GRAVANDO {len(buffer)}/{SEQ_LEN}" if recording else "Pronto (ESPACO p/ iniciar)"
            cv2.putText(frame, f"{label} | seq #{idx} | {status}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 100), 2)
            cv2.imshow("Coleta de dados - ESPACO grava, ESC sai", frame)

            if recording and result.hand_landmarks:
                vec = extract_frame_vector(result.hand_landmarks[0])
                buffer.append(vec)
                if len(buffer) >= SEQ_LEN:
                    arr = np.stack(buffer, axis=0)
                    np.save(out_dir / f"{idx:03d}.npy", arr)
                    print(f"Sequência #{idx} salva.")
                    idx += 1
                    buffer = []
                    recording = False

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            if key == 32 and not recording:
                recording = True
                buffer = []

    print(f"\nTotal de sequências em {out_dir}: {idx}")


if __name__ == "__main__":
    main()
